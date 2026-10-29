"""Molecular parsing and standardisation built on RDKit.

The policy is explicit and recorded per dataset so that results can be explained:
canonical isomeric SMILES for identity, an optional (default on) largest-fragment
step to drop salts, and optional neutralisation/tautomer canonicalisation that is
off by default because it changes the scientific object.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rdkit import Chem, RDLogger
from rdkit.Chem import rdMolDescriptors
from rdkit.Chem.MolStandardize import rdMolStandardize

from ..core.errors import ValidationError

# RDKit writes parser diagnostics to stderr; we surface row-level errors ourselves.
RDLogger.DisableLog("rdApp.*")

MAX_ATOMS = 400
MAX_SMILES_LENGTH = 4000


class MoleculeError(ValidationError):
    code = "invalid_molecule"


_RDKIT_ERRORS = (ValueError, RuntimeError)


def _describe(exc: Exception) -> str:
    message = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
    return f"{type(exc).__name__}: {message[:200]}" if message else type(exc).__name__


@dataclass(frozen=True)
class StandardizeOptions:
    strip_salts: bool = True
    neutralize: bool = False
    canonical_tautomer: bool = False
    max_atoms: int = MAX_ATOMS

    def as_dict(self) -> dict[str, Any]:
        return {
            "strip_salts": self.strip_salts,
            "neutralize": self.neutralize,
            "canonical_tautomer": self.canonical_tautomer,
            "max_atoms": self.max_atoms,
        }


@dataclass
class StandardizedMolecule:
    input_smiles: str
    canonical_smiles: str
    isomeric_smiles: str
    inchi: str | None
    inchikey: str | None
    formula: str | None
    formal_charge: int
    heavy_atoms: int
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "input_smiles": self.input_smiles,
            "canonical_smiles": self.canonical_smiles,
            "isomeric_smiles": self.isomeric_smiles,
            "inchi": self.inchi,
            "inchikey": self.inchikey,
            "formula": self.formula,
            "formal_charge": self.formal_charge,
            "heavy_atoms": self.heavy_atoms,
            "warnings": list(self.warnings),
        }


def parse_smiles(smiles: str) -> Chem.Mol:
    if not smiles or not smiles.strip():
        raise MoleculeError("Empty SMILES string.")
    if len(smiles) > MAX_SMILES_LENGTH:
        raise MoleculeError(
            "SMILES string exceeds the configured length limit.",
            details={"length": len(smiles), "limit": MAX_SMILES_LENGTH},
        )
    mol = Chem.MolFromSmiles(smiles.strip())
    if mol is None:
        raise MoleculeError("RDKit could not parse this SMILES string.")
    if mol.GetNumAtoms() == 0:
        raise MoleculeError("Structure contains no atoms.")
    return mol


def standardize(smiles: str, options: StandardizeOptions | None = None) -> StandardizedMolecule:
    options = options or StandardizeOptions()
    mol = parse_smiles(smiles)
    warnings: list[str] = []

    if mol.GetNumAtoms() > options.max_atoms:
        raise MoleculeError(
            "Structure exceeds the configured atom limit.",
            details={"atoms": mol.GetNumAtoms(), "limit": options.max_atoms},
        )

    # RDKit reports per-molecule chemistry failures as ValueError (including
    # sanitisation errors) or RuntimeError. Those become recorded warnings; any
    # other exception is a defect and propagates.
    if options.strip_salts:
        try:
            components = Chem.GetMolFrags(mol)
            largest = rdMolStandardize.LargestFragmentChooser().choose(mol)
            if largest is not None and largest.GetNumAtoms() > 0 and len(components) > 1:
                mol = largest
                warnings.append(
                    f"Salt/solvent counter-ions removed ({len(components)} components -> 1); "
                    "the original record is preserved."
                )
        except _RDKIT_ERRORS as exc:
            warnings.append(f"Salt stripping skipped: {_describe(exc)}")

    if options.neutralize:
        try:
            before = Chem.MolToSmiles(mol)
            mol = rdMolStandardize.Uncharger().uncharge(mol)
            if Chem.MolToSmiles(mol) != before:
                warnings.append("Formal charges neutralised where chemically valid.")
        except _RDKIT_ERRORS as exc:
            warnings.append(f"Neutralisation skipped: {_describe(exc)}")

    if options.canonical_tautomer:
        try:
            before = Chem.MolToSmiles(mol)
            mol = rdMolStandardize.TautomerEnumerator().Canonicalize(mol)
            if Chem.MolToSmiles(mol) != before:
                warnings.append("Canonical tautomer applied.")
        except _RDKIT_ERRORS as exc:
            warnings.append(f"Tautomer canonicalisation skipped: {_describe(exc)}")

    isomeric = Chem.MolToSmiles(mol, isomericSmiles=True, canonical=True)
    canonical = Chem.MolToSmiles(mol, isomericSmiles=False, canonical=True)

    inchi = inchikey = None
    try:
        inchi = Chem.MolToInchi(mol) or None
        inchikey = (Chem.MolToInchiKey(mol) or None) if inchi else None
    except _RDKIT_ERRORS as exc:
        warnings.append(f"InChI generation failed: {_describe(exc)}")
    else:
        if inchi is None:
            warnings.append("InChI generation returned no identifier for this structure.")

    formula = rdMolDescriptors.CalcMolFormula(mol)

    if not isomeric:
        raise MoleculeError("Standardisation produced an empty structure.")

    return StandardizedMolecule(
        input_smiles=smiles.strip(),
        canonical_smiles=canonical,
        isomeric_smiles=isomeric,
        inchi=inchi,
        inchikey=inchikey,
        formula=formula,
        formal_charge=Chem.GetFormalCharge(mol),
        heavy_atoms=mol.GetNumHeavyAtoms(),
        warnings=warnings,
    )
