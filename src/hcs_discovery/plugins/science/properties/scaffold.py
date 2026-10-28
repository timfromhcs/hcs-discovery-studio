"""Bemis-Murcko scaffold analysis and scaffold-based dataset splitting."""

from __future__ import annotations

import random
from typing import Any

from rdkit import Chem
from rdkit.Chem.Scaffolds import MurckoScaffold


def bemis_murcko_scaffold(mol_or_smiles: str | Chem.Mol, *, generic: bool = False) -> str:
    """Extract canonical Bemis-Murcko scaffold SMILES from a molecule.

    If generic is True, all heteroatoms are converted to carbon and all bonds to single bonds.
    Returns empty string for acyclic molecules.
    """
    if isinstance(mol_or_smiles, str):
        mol = Chem.MolFromSmiles(mol_or_smiles)
        if mol is None:
            return ""
    else:
        mol = Chem.Mol(mol_or_smiles)

    try:
        core = MurckoScaffold.GetScaffoldForMol(mol)
        if core is None or core.GetNumAtoms() == 0:
            return ""
        if generic:
            core = MurckoScaffold.MakeScaffoldGeneric(core)
        return Chem.MolToSmiles(core, isomericSmiles=False)
    except Exception:
        return ""


def scaffold_split(
    items: list[dict[str, Any]],
    *,
    smiles_key: str = "smiles",
    train_ratio: float = 0.8,
    seed: int = 42,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Partition items into train and held-out test sets using Bemis-Murcko scaffolds.

    Prevents structural data leakage between splits. Acyclic compounds with no
    ring scaffolds are grouped under an empty key and split randomly.
    """
    if not items:
        return ([], [])

    if train_ratio <= 0.0 or train_ratio >= 1.0:
        raise ValueError(f"train_ratio must be between 0 and 1, got {train_ratio}")

    # Group items by scaffold
    scaffold_groups: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        smi = item.get(smiles_key, "")
        scaf = bemis_murcko_scaffold(smi) if smi else ""
        scaffold_groups.setdefault(scaf, []).append(item)

    # Sort scaffold groups by size descending for deterministic, balanced packing
    rng = random.Random(seed)
    sorted_scaffolds = sorted(scaffold_groups.keys(), key=lambda s: len(scaffold_groups[s]), reverse=True)
    # Shuffle equal-size groups deterministically
    equal_groups: list[list[str]] = []
    current_size: int | None = None
    batch: list[str] = []
    for scaf in sorted_scaffolds:
        sz = len(scaffold_groups[scaf])
        if sz == current_size:
            batch.append(scaf)
        else:
            if batch:
                rng.shuffle(batch)
                equal_groups.append(batch)
            batch = [scaf]
            current_size = sz
    if batch:
        rng.shuffle(batch)
        equal_groups.append(batch)

    flat_scaffolds = [s for sublist in equal_groups for s in sublist]

    total_target = len(items)
    train_target = round(total_target * train_ratio)

    train: list[dict[str, Any]] = []
    test: list[dict[str, Any]] = []

    for scaf in flat_scaffolds:
        group = scaffold_groups[scaf]
        if len(train) + len(group) <= train_target or (
            len(train) < train_target and (len(train) + len(group) - train_target) < (train_target - len(train))
        ):
            train.extend(group)
        else:
            test.extend(group)

    # Edge case: if test ended up empty, move last group to test
    if not test and train:
        last_group = scaffold_groups[flat_scaffolds[-1]]
        test = last_group
        train = [it for it in train if it not in last_group]

    return (train, test)
