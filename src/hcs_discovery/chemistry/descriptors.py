"""Deterministic RDKit descriptors and fingerprints with explicit metadata.

Descriptors are pure functions of a molecule, canonical SMILES and the pinned RDKit
version. Metadata (units, direction, method) travels with the numbers so the UI and
reports never show an unqualified value.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import rdkit
from rdkit import Chem, DataStructs
from rdkit.Chem import QED, Crippen, Descriptors, Lipinski, rdFingerprintGenerator

DESCRIPTOR_VERSION = f"rdkit-{rdkit.__version__}"


@dataclass(frozen=True)
class DescriptorSpec:
    key: str
    label: str
    unit: str | None
    direction: str
    method: str
    description: str
    fn: Callable[[Chem.Mol], float]


def _qed(mol: Chem.Mol) -> float:
    return float(QED.qed(mol))


DESCRIPTORS: dict[str, DescriptorSpec] = {
    spec.key: spec
    for spec in (
        DescriptorSpec(
            "mw",
            "Molecular weight",
            "g/mol",
            "neutral",
            "RDKit Descriptors.MolWt",
            "Average molecular weight including implicit hydrogens.",
            Descriptors.MolWt,
        ),
        DescriptorSpec(
            "logp",
            "cLogP",
            "log10",
            "lower",
            "RDKit Crippen.MolLogP",
            "Wildman-Crippen estimated octanol/water partition coefficient.",
            Crippen.MolLogP,
        ),
        DescriptorSpec(
            "tpsa",
            "TPSA",
            "\u00c5\u00b2",
            "lower",
            "RDKit Descriptors.TPSA",
            "Topological polar surface area (Ertl et al.).",
            Descriptors.TPSA,
        ),
        DescriptorSpec(
            "hbd",
            "H-bond donors",
            "count",
            "lower",
            "RDKit Lipinski.NumHDonors",
            "Number of hydrogen-bond donors (Lipinski definition).",
            Lipinski.NumHDonors,
        ),
        DescriptorSpec(
            "hba",
            "H-bond acceptors",
            "count",
            "lower",
            "RDKit Lipinski.NumHAcceptors",
            "Number of hydrogen-bond acceptors (Lipinski definition).",
            Lipinski.NumHAcceptors,
        ),
        DescriptorSpec(
            "rotb",
            "Rotatable bonds",
            "count",
            "lower",
            "RDKit Lipinski.NumRotatableBonds",
            "Number of rotatable bonds.",
            Lipinski.NumRotatableBonds,
        ),
        DescriptorSpec(
            "rings",
            "Ring count",
            "count",
            "neutral",
            "RDKit Descriptors.RingCount",
            "Total number of rings.",
            Descriptors.RingCount,
        ),
        DescriptorSpec(
            "aromatic_rings",
            "Aromatic rings",
            "count",
            "neutral",
            "RDKit Descriptors.NumAromaticRings",
            "Number of aromatic rings.",
            Descriptors.NumAromaticRings,
        ),
        DescriptorSpec(
            "heavy_atoms",
            "Heavy atoms",
            "count",
            "neutral",
            "RDKit Descriptors.HeavyAtomCount",
            "Number of non-hydrogen atoms.",
            Descriptors.HeavyAtomCount,
        ),
        DescriptorSpec(
            "fsp3",
            "Fraction sp3",
            "fraction",
            "higher",
            "RDKit Descriptors.FractionCSP3",
            "Fraction of carbon atoms that are sp3 hybridised.",
            Descriptors.FractionCSP3,
        ),
        DescriptorSpec(
            "qed",
            "QED",
            "score (0-1)",
            "higher",
            "RDKit QED.qed",
            "Quantitative estimate of drug-likeness (Bickerton et al.). A heuristic, not a law.",
            _qed,
        ),
        DescriptorSpec(
            "formal_charge",
            "Formal charge",
            "e",
            "neutral",
            "RDKit Chem.GetFormalCharge",
            "Net formal charge of the standardised structure.",
            lambda m: float(Chem.GetFormalCharge(m)),
        ),
        DescriptorSpec(
            "mr",
            "Molar refractivity",
            "cm\u00b3/mol",
            "neutral",
            "RDKit Crippen.MolMR",
            "Wildman-Crippen estimated molar refractivity.",
            Crippen.MolMR,
        ),
    )
}

DEFAULT_DESCRIPTORS = ("mw", "logp", "tpsa", "hbd", "hba", "rotb", "qed")


def compute_descriptors(smiles: str, keys: list[str] | tuple[str, ...] | None = None) -> dict[str, dict[str, Any]]:
    """Return ``{key: {"value": float, "unit": ..., "method": ...}}`` for a SMILES."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError("Invalid SMILES")
    selected = list(keys) if keys else list(DEFAULT_DESCRIPTORS)
    unknown = [key for key in selected if key not in DESCRIPTORS]
    if unknown:
        raise ValueError(f"Unknown descriptor(s): {', '.join(unknown)}")
    result: dict[str, dict[str, Any]] = {}
    for key in selected:
        spec = DESCRIPTORS[key]
        value = spec.fn(mol)
        if value is None:
            continue
        result[key] = {
            "value": float(value),
            "label": spec.label,
            "unit": spec.unit,
            "direction": spec.direction,
            "method": spec.method,
            "description": spec.description,
        }
    return result


def descriptor_columns(keys: list[str] | tuple[str, ...]) -> list[Any]:
    # Imported lazily to keep the chemistry layer independent of the workflow package.
    from ..workflow.table import Column

    return [
        Column(
            name=key,
            label=DESCRIPTORS[key].label,
            type="number",
            unit=DESCRIPTORS[key].unit,
            direction=DESCRIPTORS[key].direction,  # type: ignore[arg-type]
            method=DESCRIPTORS[key].method,
            description=DESCRIPTORS[key].description,
        )
        for key in keys
        if key in DESCRIPTORS
    ]


_morgan_cache: dict[tuple[int, int], Any] = {}


def morgan_fingerprint(mol: Chem.Mol, radius: int = 2, bits: int = 2048) -> Any:
    key = (radius, bits)
    generator = _morgan_cache.get(key)
    if generator is None:
        generator = rdFingerprintGenerator.GetMorganGenerator(radius=radius, fpSize=bits)
        _morgan_cache[key] = generator
    return generator.GetFingerprint(mol)


def tanimoto_to_query(mol: Chem.Mol, query: Chem.Mol, *, radius: int = 2, bits: int = 2048) -> float:
    return float(
        DataStructs.TanimotoSimilarity(morgan_fingerprint(mol, radius, bits), morgan_fingerprint(query, radius, bits))
    )


def fingerprint_hex(mol: Chem.Mol, *, radius: int = 2, bits: int = 2048) -> str:
    fp = morgan_fingerprint(mol, radius, bits)
    return fp.ToBitString()
