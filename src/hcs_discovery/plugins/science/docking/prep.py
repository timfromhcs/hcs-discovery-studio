"""Ligand and receptor preparation and PDBQT parsing for molecular docking."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rdkit import Chem
from rdkit.Chem import AllChem

from ....core.errors import ValidationError


class LigandPreparationError(ValidationError):
    code = "ligand_prep_failed"


class ReceptorValidationError(ValidationError):
    code = "receptor_invalid"


@dataclass(frozen=True)
class VinaPose:
    mode: int
    affinity: float
    rmsd_lb: float
    rmsd_ub: float
    pdbqt: str


PREPARATION_METHOD = "hcs-pdbqt-1"
"""Identifier of the ligand preparation conventions below, recorded in provenance.

The conventions follow Meeko's defaults (AutoDock 4 atom types, Gasteiger charges,
non-polar hydrogens merged, rigid rings, rigid primary/secondary amides) so the
torsion tree matches what the AutoDock tooling would produce. Macrocycles are kept
rigid rather than opened with pseudo-atoms.
"""

SUPPORTED_ELEMENTS = frozenset({"H", "C", "N", "O", "S", "P", "F", "Cl", "Br", "I"})
_POLAR_H_PARENTS = frozenset({"N", "O", "F", "P", "S"})

# AutoDock 4 atom typing, later rules override earlier ones (Meeko ad4_types.json).
_AD4_RULES: tuple[tuple[str, str], ...] = (
    ("[#1]", "H"),
    ("[#1][#7,#8,#9,#15,#16]", "HD"),
    ("[C]", "C"),
    ("[c]", "A"),
    ("[#7]", "NA"),
    ("[#8]", "OA"),
    ("[#9]", "F"),
    ("[#15]", "P"),
    ("[#16]", "S"),
    ("[#17]", "Cl"),
    ("[#35]", "Br"),
    ("[#53]", "I"),
    ("[#7X3v3][a]", "N"),
    ("[#7X3v3][#6X3v4]", "N"),
    ("[#7X3v3][NX2]=[*]", "N"),
    ("[#7+1]", "N"),
    ("[SX2]", "SA"),
)
_AD4_PATTERNS = tuple((Chem.MolFromSmarts(smarts), atype) for smarts, atype in _AD4_RULES)
_AMIDE = Chem.MolFromSmarts("[NX3]-[CX3]=[O,N,S]")
_TERTIARY_AMIDE = Chem.MolFromSmarts("[NX3]([!#1])([!#1])-[CX3]=[O,N,S]")
_SINGLE_TRIPLE_SINGLE = Chem.MolFromSmarts("[*]-[*]#[*]-[*]")
_TERMINAL_TRIPLE = Chem.MolFromSmarts("[*]-[*]#[*X1]")


@dataclass(frozen=True)
class PreparedLigand:
    pdbqt: str
    torsions: int
    warnings: tuple[str, ...]
    method: str = PREPARATION_METHOD


def _ad4_types(mol: Chem.Mol) -> list[str]:
    types = [""] * mol.GetNumAtoms()
    for pattern, atype in _AD4_PATTERNS:
        for match in mol.GetSubstructMatches(pattern, uniquify=False):
            types[match[0]] = atype
    return types


def _bond_key(i: int, j: int) -> tuple[int, int]:
    return (i, j) if i < j else (j, i)


def _rotatable_bonds(mol: Chem.Mol, kept: set[int]) -> set[tuple[int, int]]:
    """Rotatable bonds between kept atoms, using Meeko's default rules."""
    amides = {_bond_key(m[0], m[1]) for m in mol.GetSubstructMatches(_AMIDE)}
    ranks = list(Chem.CanonicalRankAtoms(mol, breakTies=False))
    for n, r1, r2, c, _x in mol.GetSubstructMatches(_TERTIARY_AMIDE):
        if ranks[r1] != ranks[r2]:
            amides.discard(_bond_key(n, c))
    rigid: set[tuple[int, int]] = set()
    triple_rotors: set[tuple[int, int]] = set()
    for i, j, k, m in mol.GetSubstructMatches(_SINGLE_TRIPLE_SINGLE):
        triple_rotors.add(_bond_key(j, k))
        rigid.update({_bond_key(i, j), _bond_key(k, m)})
    rigid.update(_bond_key(i, j) for i, j, _k in mol.GetSubstructMatches(_TERMINAL_TRIPLE))

    rotatable: set[tuple[int, int]] = set()
    for bond in mol.GetBonds():
        key = _bond_key(bond.GetBeginAtomIdx(), bond.GetEndAtomIdx())
        if key[0] not in kept or key[1] not in kept or bond.IsInRing():
            continue
        if key in triple_rotors or (
            bond.GetBondType() == Chem.BondType.SINGLE and key not in rigid and key not in amides
        ):
            rotatable.add(key)
    return rotatable


def _rigid_groups(mol: Chem.Mol, kept: list[int], rotatable: set[tuple[int, int]]) -> list[list[int]]:
    """Connected components of kept atoms once rotatable bonds are cut."""
    kept_set = set(kept)
    group_of: dict[int, int] = {}
    groups: list[list[int]] = []
    for start in kept:
        if start in group_of:
            continue
        stack, members = [start], []
        group_of[start] = len(groups)
        while stack:
            atom = stack.pop()
            members.append(atom)
            for neighbor in mol.GetAtomWithIdx(atom).GetNeighbors():
                other = neighbor.GetIdx()
                if other in kept_set and other not in group_of and _bond_key(atom, other) not in rotatable:
                    group_of[other] = len(groups)
                    stack.append(other)
        groups.append(sorted(members))
    return groups


def _choose_root(graph: dict[int, set[int]], groups: list[list[int]]) -> int:
    """Graph centre of the rigid-group tree (Meeko's leaf-pruning rule)."""
    remaining = {node: set(edges) for node, edges in graph.items()}
    while len(remaining) > 2:
        leaves = [node for node, edges in remaining.items() if len(edges) <= 1]
        for leaf in leaves:
            for other in remaining.pop(leaf):
                remaining[other].discard(leaf)
    candidates = sorted(remaining)
    return max(candidates, key=lambda node: (len(groups[node]), -node))


def prepare_ligand(smiles_or_mol: str | Chem.Mol, *, seed: int = 42) -> PreparedLigand:
    """Prepare a flexible-ligand PDBQT (ROOT/BRANCH torsion tree) from SMILES or an RDKit Mol.

    Expected chemistry problems (unparseable input, unsupported elements, failed
    embedding, undefined charges) raise :class:`LigandPreparationError`.
    Transformations that change the docked species, such as keeping only the
    largest fragment, are returned as warnings.
    """
    warnings: list[str] = []
    if isinstance(smiles_or_mol, str):
        mol = Chem.MolFromSmiles(smiles_or_mol)
        if mol is None:
            raise LigandPreparationError(f"Cannot parse ligand SMILES: '{smiles_or_mol}'")
    else:
        mol = Chem.Mol(smiles_or_mol)

    frags = Chem.GetMolFrags(mol, asMols=True)
    if len(frags) > 1:
        mol = max(frags, key=lambda m: m.GetNumHeavyAtoms())
        warnings.append(
            f"Input has {len(frags)} disconnected fragments; docked only the largest "
            f"({mol.GetNumHeavyAtoms()} heavy atoms)."
        )
    if mol.GetNumHeavyAtoms() == 0:
        raise LigandPreparationError("Ligand has zero heavy atoms.")
    unsupported = sorted({a.GetSymbol() for a in mol.GetAtoms()} - SUPPORTED_ELEMENTS)
    if unsupported:
        raise LigandPreparationError(f"Unsupported element(s) for ligand preparation: {', '.join(unsupported)}.")
    if any(len(ring) >= 7 for ring in mol.GetRingInfo().AtomRings()):
        warnings.append("Macrocycle kept rigid: rings of 7+ atoms are not conformationally sampled.")

    mol = Chem.AddHs(mol)
    # MMFF setup rewrites aromaticity flags in place (MMFF aromaticity model), so
    # atom typing and rotor detection use an untouched copy of the topology.
    topology = Chem.Mol(mol)
    params = AllChem.ETKDGv3()
    params.randomSeed = seed
    if AllChem.EmbedMolecule(mol, params) != 0:
        params.useRandomCoords = True
        if AllChem.EmbedMolecule(mol, params) != 0:
            raise LigandPreparationError("3D coordinate generation failed for ligand.")
        warnings.append("Distance-geometry embedding failed; used random-coordinate embedding.")

    if AllChem.MMFFHasAllMoleculeParams(mol):
        if AllChem.MMFFOptimizeMolecule(mol, maxIters=500) != 0:
            warnings.append("MMFF94 optimisation did not converge in 500 iterations.")
    else:
        warnings.append("MMFF94 parameters unavailable; using the unoptimised ETKDG geometry.")

    AllChem.ComputeGasteigerCharges(mol)
    charges = [float(atom.GetProp("_GasteigerCharge")) for atom in mol.GetAtoms()]
    if not all(math.isfinite(charge) for charge in charges):
        raise LigandPreparationError("Gasteiger charges are undefined for this ligand.")

    # Merge non-polar hydrogens into their heavy atom, as AutoDock expects.
    kept: list[int] = []
    for atom in mol.GetAtoms():
        idx = atom.GetIdx()
        if atom.GetAtomicNum() == 1:
            parent = atom.GetNeighbors()[0]
            if parent.GetSymbol() not in _POLAR_H_PARENTS:
                charges[parent.GetIdx()] += charges[idx]
                continue
        kept.append(idx)
    kept_set = set(kept)

    rotatable = _rotatable_bonds(topology, kept_set)
    groups = _rigid_groups(topology, kept, rotatable)
    group_of = {atom: g for g, members in enumerate(groups) for atom in members}
    graph: dict[int, set[int]] = {g: set() for g in range(len(groups))}
    for i, j in rotatable:
        graph[group_of[i]].add(group_of[j])
        graph[group_of[j]].add(group_of[i])

    # Like Meeko, choose the root before folding terminal atoms, then fold: a rotor
    # to a single atom moves nothing, so that atom joins its neighbour's group.
    root = _choose_root(graph, groups)
    for g in range(len(groups)):
        if g != root and len(groups[g]) == 1 and len(graph[g]) == 1:
            (host,) = graph.pop(g)
            graph[host].discard(g)
            rotatable = {bond for bond in rotatable if groups[g][0] not in bond}
            groups[host] = sorted([*groups[host], *groups[g]])
            groups[g] = []
    live = [g for g in graph if groups[g]]

    types = _ad4_types(topology)
    conf = mol.GetConformer()
    serial: dict[int, int] = {}
    lines: list[str] = [f"REMARK  Prepared by HCS Discovery Studio ({PREPARATION_METHOD})\n"]

    def atom_line(idx: int) -> str:
        serial[idx] = len(serial) + 1
        pos = conf.GetAtomPosition(idx)
        name = mol.GetAtomWithIdx(idx).GetSymbol()[:4].ljust(4)
        return (
            f"ATOM  {serial[idx]:5d} {name} LIG     1    "
            f"{pos.x:8.3f}{pos.y:8.3f}{pos.z:8.3f}  1.00  0.00    "
            f"{charges[idx]:+6.3f} {types[idx]:<2s}\n"
        )

    body: list[str] = ["ROOT\n", *(atom_line(i) for i in groups[root]), "ENDROOT\n"]

    def emit_children(parent: int, visited: set[int]) -> None:
        for child in sorted(graph[parent] - visited):
            parent_atom, child_atom = next(
                (i, j) if group_of[i] == parent else (j, i)
                for i, j in sorted(rotatable)
                if {group_of[i], group_of[j]} == {parent, child}
            )
            visited.add(child)
            members = [child_atom, *(a for a in groups[child] if a != child_atom)]
            body.append(f"BRANCH {serial[parent_atom]:3d} {len(serial) + 1:3d}\n")
            child_serial = len(serial) + 1
            body.extend(atom_line(a) for a in members)
            emit_children(child, visited)
            body.append(f"ENDBRANCH {serial[parent_atom]:3d} {child_serial:3d}\n")

    # Group membership changed for folded atoms; refresh the lookup.
    group_of = {atom: g for g in live for atom in groups[g]}
    emit_children(root, {root})
    torsions = len(live) - 1

    # Heavy-atom SMILES with the PDBQT serial of each SMILES atom, so a docked pose
    # can be rebuilt with its bonds. AddHs appends hydrogens, so heavy-atom indices
    # are unchanged by RemoveHs.
    heavy = Chem.RemoveHs(mol)
    smiles = Chem.MolToSmiles(heavy)
    output_order = list(heavy.GetPropsAsDict(includePrivate=True, includeComputed=True)["_smilesAtomOutputOrder"])
    pairs = " ".join(f"{n + 1} {serial[idx]}" for n, idx in enumerate(output_order))
    lines.append(f"REMARK SMILES {smiles}\n")
    lines.append(f"REMARK SMILES IDX {pairs}\n")
    lines.extend(body)
    lines.append(f"TORSDOF {torsions}\n")
    return PreparedLigand(pdbqt="".join(lines), torsions=torsions, warnings=tuple(warnings))


def prepare_ligand_pdbqt(smiles_or_mol: str | Chem.Mol, *, seed: int = 42) -> str:
    """Prepare a flexible-ligand PDBQT string; see :func:`prepare_ligand`."""
    return prepare_ligand(smiles_or_mol, seed=seed).pdbqt


def validate_receptor_pdbqt(pdbqt_text_or_path: str | Path) -> dict[str, Any]:
    """Validate receptor PDBQT structure and compute spatial bounds."""
    if isinstance(pdbqt_text_or_path, Path):
        if not pdbqt_text_or_path.is_file():
            raise ReceptorValidationError(f"Receptor file not found: {pdbqt_text_or_path}")
        content = pdbqt_text_or_path.read_text(encoding="utf-8", errors="replace")
    else:
        content = pdbqt_text_or_path

    lines = content.splitlines()
    atom_count = 0
    has_polar_h = False
    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")
    atom_types: set[str] = set()

    for line in lines:
        if line.startswith(("ATOM  ", "HETATM")):
            atom_count += 1
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)
                min_z = min(min_z, z)
                max_z = max(max_z, z)
            except (ValueError, IndexError):
                pass

            # PDBQT atom type is in columns 78-79
            atype = line[77:79].strip() if len(line) >= 79 else ""
            if atype:
                atom_types.add(atype)
                if atype == "HD":
                    has_polar_h = True

    if atom_count == 0:
        raise ReceptorValidationError("Receptor PDBQT contains no ATOM or HETATM records.")

    warnings: list[str] = []
    if not has_polar_h:
        warnings.append("Receptor does not appear to contain polar hydrogens (HD atom type).")

    center = (
        round((min_x + max_x) / 2.0, 3),
        round((min_y + max_y) / 2.0, 3),
        round((min_z + max_z) / 2.0, 3),
    )
    dimensions = (
        round(max_x - min_x, 3),
        round(max_y - min_y, 3),
        round(max_z - min_z, 3),
    )

    return {
        "atom_count": atom_count,
        "has_polar_h": has_polar_h,
        "atom_types": sorted(atom_types),
        "bounding_box": {
            "min": (min_x, min_y, min_z),
            "max": (max_x, max_y, max_z),
            "center": center,
            "dimensions": dimensions,
        },
        "warnings": warnings,
    }


_RESULT_RE = re.compile(r"REMARK\s+VINA\s+RESULT:\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)")


def parse_vina_poses(pdbqt_content: str) -> list[VinaPose]:
    """Parse output PDBQT poses generated by AutoDock Vina."""
    poses: list[VinaPose] = []
    current_lines: list[str] = []
    current_mode = 1
    current_affinity: float | None = None
    current_rmsd_lb = 0.0
    current_rmsd_ub = 0.0

    for line in pdbqt_content.splitlines(keepends=True):
        if line.startswith("MODEL"):
            current_lines = [line]
            match = re.search(r"MODEL\s+(\d+)", line)
            if match:
                current_mode = int(match.group(1))
            current_affinity = None
            continue

        match = _RESULT_RE.search(line)
        if match:
            current_affinity = float(match.group(1))
            current_rmsd_lb = float(match.group(2))
            current_rmsd_ub = float(match.group(3))

        current_lines.append(line)

        if line.startswith("ENDMDL"):
            if current_affinity is not None:
                poses.append(
                    VinaPose(
                        mode=current_mode,
                        affinity=current_affinity,
                        rmsd_lb=current_rmsd_lb,
                        rmsd_ub=current_rmsd_ub,
                        pdbqt="".join(current_lines),
                    )
                )
            current_lines = []

    # If file had no MODEL tags but had REMARK VINA RESULT
    if not poses and current_lines and current_affinity is not None:
        poses.append(
            VinaPose(
                mode=1,
                affinity=current_affinity,
                rmsd_lb=current_rmsd_lb,
                rmsd_ub=current_rmsd_ub,
                pdbqt="".join(current_lines),
            )
        )

    return poses


def _pose_from_smiles_remarks(pose_pdbqt: str, coords: list[tuple[float, float, float]]) -> Chem.Mol | None:
    """Rebuild a heavy-atom pose with bonds from ``REMARK SMILES`` / ``SMILES IDX`` lines.

    Returns ``None`` when the remarks are absent or do not match the atoms, so the
    caller can fall back to an atoms-only representation.
    """
    smiles = None
    pairs: list[int] = []
    for line in pose_pdbqt.splitlines():
        if line.startswith("REMARK SMILES IDX"):
            pairs.extend(int(token) for token in line.split()[3:])
        elif line.startswith("REMARK SMILES "):
            smiles = line.split()[2]
    if smiles is None or not pairs or len(pairs) % 2:
        return None
    mol = Chem.MolFromSmiles(smiles)
    mapping = dict(zip(pairs[0::2], pairs[1::2], strict=True))
    if mol is None or sorted(mapping) != list(range(1, mol.GetNumAtoms() + 1)):
        return None
    if any(not 1 <= serial <= len(coords) for serial in mapping.values()):
        return None
    conf = Chem.Conformer(mol.GetNumAtoms())
    for smiles_index, serial in mapping.items():
        conf.SetAtomPosition(smiles_index - 1, coords[serial - 1])
    mol.AddConformer(conf, assignId=True)
    Chem.AssignStereochemistryFrom3D(mol)
    return mol


def pose_pdbqt_to_sdf(pose_pdbqt: str, ref_mol: Chem.Mol | None = None) -> str:
    """Convert a single PDBQT pose into an SDF representation with Vina result properties."""
    # Extract coordinates and atoms from PDBQT
    coords: list[tuple[float, float, float]] = []
    atom_symbols: list[str] = []
    affinity = None
    mode = 1
    rmsd_lb = 0.0
    rmsd_ub = 0.0

    for line in pose_pdbqt.splitlines():
        res_m = _RESULT_RE.search(line)
        if res_m:
            affinity = float(res_m.group(1))
            rmsd_lb = float(res_m.group(2))
            rmsd_ub = float(res_m.group(3))
        mod_m = re.search(r"MODEL\s+(\d+)", line)
        if mod_m:
            mode = int(mod_m.group(1))

        if line.startswith(("ATOM  ", "HETATM")):
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
                atype = line[77:79].strip() if len(line) >= 79 else ""
                # Strip AutoDock type modifiers: OA->O, NA->N, SA->S, HD->H, A->C
                elem = atype
                if atype in ("OA", "O"):
                    elem = "O"
                elif atype in ("NA", "N"):
                    elem = "N"
                elif atype in ("SA", "S"):
                    elem = "S"
                elif atype in ("HD", "H"):
                    elem = "H"
                elif atype in ("A", "C"):
                    elem = "C"
                elif not elem:
                    elem = line[12:14].strip()
                coords.append((x, y, z))
                atom_symbols.append(elem)
            except (ValueError, IndexError):
                pass

    if not coords:
        return ""

    rebuilt = _pose_from_smiles_remarks(pose_pdbqt, coords)
    if rebuilt is not None:
        mol = rebuilt
    else:
        if ref_mol is not None and ref_mol.GetNumAtoms() == len(coords):
            mol = Chem.Mol(ref_mol)
        else:
            # No bond information available: atoms only.
            editable = Chem.EditableMol(Chem.Mol())
            for sym in atom_symbols:
                editable.AddAtom(Chem.Atom(sym))
            mol = editable.GetMol()
        conf = Chem.Conformer(len(coords))
        for i, (x, y, z) in enumerate(coords):
            conf.SetAtomPosition(i, (x, y, z))
        mol.RemoveAllConformers()
        mol.AddConformer(conf)

    block = Chem.MolToMolBlock(mol).rstrip()
    sd_tags: list[str] = []
    if affinity is not None:
        sd_tags.append(f"> <VINA_AFFINITY_KCAL_MOL>\n{affinity:.3f}\n")
        sd_tags.append(f"> <VINA_MODE>\n{mode}\n")
        sd_tags.append(f"> <VINA_RMSD_LB>\n{rmsd_lb:.3f}\n")
        sd_tags.append(f"> <VINA_RMSD_UB>\n{rmsd_ub:.3f}\n")
    if sd_tags:
        return f"{block}\n\n{'\n'.join(sd_tags)}\n$$$$\n"
    return f"{block}\n$$$$\n"
