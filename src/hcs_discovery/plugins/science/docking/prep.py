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


def _autodock_atom_type(atom: Chem.Atom) -> str:
    elem = atom.GetSymbol()
    if elem == "C":
        return "A" if atom.GetIsAromatic() else "C"
    if elem == "N":
        # NA for hydrogen bond acceptors (tertiary or pyridine-like), N for donors
        if atom.GetTotalNumHs() == 0 and not atom.GetFormalCharge() > 0:
            return "NA"
        return "N"
    if elem == "O":
        return "OA"
    if elem == "S":
        return "SA" if atom.GetIsAromatic() else "S"
    if elem == "P":
        return "P"
    if elem in ("F", "Cl", "Br", "I"):
        return elem
    if elem == "H":
        neighbors = atom.GetNeighbors()
        if neighbors and neighbors[0].GetSymbol() in ("N", "O", "S"):
            return "HD"
        return "H"
    # Fallback to uppercase element
    return elem[:2].upper()


def prepare_ligand_pdbqt(smiles_or_mol: str | Chem.Mol, *, seed: int = 42) -> str:
    """Prepare a 3D PDBQT representation of a ligand from SMILES or RDKit Mol."""
    if isinstance(smiles_or_mol, str):
        mol = Chem.MolFromSmiles(smiles_or_mol)
        if mol is None:
            raise LigandPreparationError(f"Cannot parse ligand SMILES: '{smiles_or_mol}'")
    else:
        mol = Chem.Mol(smiles_or_mol)

    # Check for disconnected components (salts/mixtures)
    frags = Chem.GetMolFrags(mol, asMols=True)
    if len(frags) > 1:
        # Pick largest fragment
        mol = max(frags, key=lambda m: m.GetNumHeavyAtoms())

    if mol.GetNumHeavyAtoms() == 0:
        raise LigandPreparationError("Ligand has zero heavy atoms.")

    mol = Chem.AddHs(mol)

    # Generate 3D coordinates
    embed_code = AllChem.EmbedMolecule(mol, randomSeed=seed)
    if embed_code != 0:
        # Fallback to random coordinate embedding if standard distance geometry fails
        embed_code = AllChem.EmbedMolecule(mol, useRandomCoords=True, randomSeed=seed)
        if embed_code != 0:
            raise LigandPreparationError("3D coordinate generation failed for ligand.")

    import contextlib

    with contextlib.suppress(Exception):
        AllChem.MMFFOptimizeMolecule(mol, maxIters=500)

    with contextlib.suppress(Exception):
        AllChem.ComputeGasteigerCharges(mol)

    conf = mol.GetConformer()
    lines: list[str] = ["REMARK  Prepared by HCS Discovery Studio\n", "ROOT\n"]

    for atom in mol.GetAtoms():
        idx = atom.GetIdx()
        pos = conf.GetAtomPosition(idx)
        elem = atom.GetSymbol()

        charge = 0.0
        if atom.HasProp("_GasteigerCharge"):
            try:
                val = float(atom.GetProp("_GasteigerCharge"))
                if not math.isnan(val) and not math.isinf(val):
                    charge = val
            except (ValueError, TypeError):
                charge = 0.0

        ad_type = _autodock_atom_type(atom)
        atom_name = f"{elem}{idx + 1}"[:4].ljust(4)
        line = (
            f"ATOM  {idx + 1:5d} {atom_name} LIG     1    "
            f"{pos.x:8.3f}{pos.y:8.3f}{pos.z:8.3f}  1.00  0.00    "
            f"{charge:+6.3f} {ad_type:<2s}\n"
        )
        lines.append(line)

    lines.append("ENDROOT\n")
    rot_bonds = AllChem.CalcNumRotatableBonds(mol)
    lines.append(f"TORSDOF {rot_bonds}\n")

    return "".join(lines)


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

    if ref_mol is not None and ref_mol.GetNumAtoms() == len(coords):
        mol = Chem.Mol(ref_mol)
    else:
        # Build raw molecule from symbols
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
