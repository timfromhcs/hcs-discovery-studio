"""Ligand PDBQT preparation: torsion tree, typing, charges and pose round-trip.

Expected values follow Meeko 0.8.0 defaults; see docs/validation/ligand-prep-meeko.md
for the full comparison run against Meeko itself.
"""

from __future__ import annotations

import re

import pytest
from rdkit import Chem

from hcs_discovery.plugins.science.docking.prep import (
    LigandPreparationError,
    pose_pdbqt_to_sdf,
    prepare_ligand,
)


def _atoms(pdbqt: str) -> list[tuple[int, str, float]]:
    return [
        (int(line[6:11]), line[77:79].strip(), float(line[70:76]))
        for line in pdbqt.splitlines()
        if line.startswith("ATOM")
    ]


def _branches(pdbqt: str) -> list[tuple[int, int]]:
    return [(int(a), int(b)) for a, b in re.findall(r"^BRANCH\s+(\d+)\s+(\d+)$", pdbqt, re.MULTILINE)]


def _torsdof(pdbqt: str) -> int:
    match = re.search(r"^TORSDOF (\d+)$", pdbqt, re.MULTILINE)
    assert match is not None
    return int(match.group(1))


def _root_size(pdbqt: str) -> int:
    body = pdbqt.split("ROOT\n", 1)[1].split("ENDROOT", 1)[0]
    return sum(line.startswith("ATOM") for line in body.splitlines())


def test_ibuprofen_has_a_flexible_torsion_tree_matching_meeko() -> None:
    prepared = prepare_ligand("CC(C)Cc1ccc(C(C)C(=O)O)cc1", seed=1)
    pdbqt = prepared.pdbqt

    # Ring as ROOT; CH2, CH, C(=O) and the hydroxyl O-H rotate (Meeko: TORSDOF 5).
    assert _root_size(pdbqt) == 6
    assert _torsdof(pdbqt) == prepared.torsions == 5
    assert len(_branches(pdbqt)) == 5
    lines = pdbqt.splitlines()
    assert sum(x.startswith("BRANCH") for x in lines) == sum(x.startswith("ENDBRANCH") for x in lines) == 5
    # Non-polar hydrogens are merged; only the acid proton remains, typed HD.
    atoms = _atoms(pdbqt)
    assert len(atoms) == 16
    assert [t for _s, t, _q in atoms if t.startswith("H")] == ["HD"]
    assert sorted(t for _s, t, _q in atoms).count("A") == 6
    assert prepared.warnings == ()


def test_branch_records_reference_existing_atoms_in_tree_order() -> None:
    pdbqt = prepare_ligand("CCOC(=O)c1ccc(NC(=O)CCN(C)C)cc1", seed=3).pdbqt
    declared: set[int] = set()
    stack: list[tuple[int, int]] = []
    for line in pdbqt.splitlines():
        if line.startswith("ATOM"):
            declared.add(int(line[6:11]))
        elif line.startswith("BRANCH"):
            parent, child = (int(x) for x in line.split()[1:3])
            assert parent in declared, "branch parent must already be placed"
            assert child == max(declared) + 1, "first atom of a branch is the rotor's child atom"
            stack.append((parent, child))
        elif line.startswith("ENDBRANCH"):
            assert tuple(int(x) for x in line.split()[1:3]) == stack.pop()
    assert not stack
    assert sorted(declared) == list(range(1, len(declared) + 1))


def test_gasteiger_charges_are_conserved_after_hydrogen_merging() -> None:
    for smiles, formal in (("CC(=O)Oc1ccccc1C(=O)O", 0), ("C[NH3+]", 1), ("CC(=O)[O-]", -1)):
        total = sum(q for _s, _t, q in _atoms(prepare_ligand(smiles).pdbqt))
        assert total == pytest.approx(formal, abs=0.02), smiles


@pytest.mark.parametrize(
    ("smiles", "torsions"),
    [
        ("CC(=O)NC", 0),  # secondary amide stays rigid
        ("CC(=O)N(C)C", 0),  # tertiary amide with identical substituents stays rigid
        ("CC(=O)N(C)CC", 2),  # tertiary amide with distinct substituents rotates, plus N-ethyl
        ("CCC#N", 0),  # nitrile and the bond to it are rigid; ethyl C-C is terminal
        ("CCC#CCC", 1),  # one rotor across the linear alkyne, flanking singles rigid
        ("C1CCCCC1C", 0),  # ring bonds never rotate; methyl is terminal
        ("Nc1ccccc1", 1),  # aniline N-H2 rotates (polar hydrogens kept)
    ],
)
def test_rotatable_bond_rules(smiles: str, torsions: int) -> None:
    assert prepare_ligand(smiles).torsions == torsions


def test_atom_typing_uses_original_aromaticity() -> None:
    # MMFF setup rewrites aromatic flags; typing must not see that.
    atoms = _atoms(prepare_ligand("Cn1c(=O)c2c(ncn2C)n(C)c1=O").pdbqt)
    types = [t for _s, t, _q in atoms]
    # Meeko 0.8.0 types caffeine with five aromatic carbons, including both ring
    # carbonyl carbons that an MMFF-perceived molecule would type as aliphatic "C".
    assert types.count("A") == 5
    assert types.count("NA") == 1  # only the imidazole N without substituent accepts


def test_transformations_are_reported_and_unsupported_input_refused() -> None:
    salt = prepare_ligand("CC(=O)Oc1ccccc1C(=O)[O-].[Na+]")
    assert any("2 disconnected fragments" in w for w in salt.warnings)
    macrocycle = prepare_ligand("C1CCCCCCC1")
    assert any(w.startswith("Macrocycle kept rigid") for w in macrocycle.warnings)
    for bad in ("not a smiles", "C[Si](C)(C)C", "[Na+]"):
        with pytest.raises(LigandPreparationError):
            prepare_ligand(bad)


def test_pose_round_trip_rebuilds_bonds_from_smiles_remarks() -> None:
    smiles = "CC(C)Cc1ccc([C@@H](C)C(=O)O)cc1"
    pdbqt = prepare_ligand(smiles, seed=5).pdbqt
    pose = f"MODEL 1\nREMARK VINA RESULT:    -6.100      0.000      0.000\n{pdbqt}ENDMDL\n"
    sdf = pose_pdbqt_to_sdf(pose)

    mol = Chem.MolFromMolBlock(sdf.split("$$$$")[0])
    assert mol is not None
    assert mol.GetNumBonds() == mol.GetNumAtoms()  # one ring: bonds = atoms
    assert Chem.MolToSmiles(mol) == Chem.MolToSmiles(Chem.MolFromSmiles(smiles))
    assert "> <VINA_AFFINITY_KCAL_MOL>\n-6.100" in sdf
