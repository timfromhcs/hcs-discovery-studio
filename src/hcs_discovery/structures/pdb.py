"""Minimal, dependency-free inspection of PDB coordinate files.

This module answers the questions a docking setup actually needs before anything is
computed: which chains exist, which residues are missing, what is a ligand versus a
water or an ion, whether alternate conformations are present, and how big the file
is. It does not build a molecular model, guess protonation, or decide what may be
stripped — a caller must state that explicitly, and the answer is recorded.

Only the legacy PDB format is parsed. mmCIF raises ``unsupported_format`` rather
than being half-parsed, because a silently incomplete structure is worse than a
refused one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path
from typing import Any

from ..core.errors import ValidationError

#: Refuse very large uploads before reading them into memory.
MAX_STRUCTURE_BYTES = 64 * 1024 * 1024

WATER_RESIDUES = frozenset({"HOH", "WAT", "DOD", "H2O", "TIP", "TIP3", "SOL"})
#: Single-atom or small inorganic species treated as ions, not as ligands.
ION_RESIDUES = frozenset(
    {
        "NA",
        "CL",
        "K",
        "MG",
        "CA",
        "ZN",
        "MN",
        "FE",
        "FE2",
        "CU",
        "CO",
        "NI",
        "CD",
        "HG",
        "CS",
        "RB",
        "SR",
        "BA",
        "LI",
        "AL",
        "BR",
        "IOD",
        "F",
    }
)


class StructureFormatError(ValidationError):
    code = "unsupported_format"


@dataclass(frozen=True)
class ResidueGap:
    """A run of missing residue numbers inside a chain."""

    after_residue: int
    missing_from: int
    missing_to: int

    @property
    def count(self) -> int:
        return self.missing_to - self.missing_from + 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "after_residue": self.after_residue,
            "missing_from": self.missing_from,
            "missing_to": self.missing_to,
            "count": self.count,
        }


@dataclass(frozen=True)
class ChainSummary:
    chain_id: str
    residue_count: int
    atom_count: int
    hetero_residues: tuple[str, ...] = ()
    gaps: tuple[ResidueGap, ...] = ()

    @property
    def missing_residue_count(self) -> int:
        return sum(gap.count for gap in self.gaps)

    def as_dict(self) -> dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "residue_count": self.residue_count,
            "atom_count": self.atom_count,
            "hetero_residues": list(self.hetero_residues),
            "missing_residue_count": self.missing_residue_count,
            "gaps": [gap.as_dict() for gap in self.gaps],
        }


@dataclass(frozen=True)
class StructureInspection:
    """Everything the product may show about a coordinate file, and nothing more."""

    filename: str
    format: str
    size_bytes: int
    model_count: int
    atom_count: int
    chains: tuple[ChainSummary, ...]
    ligands: tuple[str, ...]
    waters: int
    ions: tuple[str, ...]
    alternate_locations: tuple[str, ...]
    pdb_id: str | None = None
    title: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "format": self.format,
            "size_bytes": self.size_bytes,
            "model_count": self.model_count,
            "atom_count": self.atom_count,
            "chains": [chain.as_dict() for chain in self.chains],
            "ligands": list(self.ligands),
            "waters": self.waters,
            "ions": list(self.ions),
            "alternate_locations": list(self.alternate_locations),
            "pdb_id": self.pdb_id,
            "title": self.title,
            "warnings": list(self.warnings),
        }


def detect_format(filename: str) -> str:
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix in {"pdb", "ent"}:
        return "pdb"
    if suffix in {"cif", "mmcif"}:
        raise StructureFormatError(
            "mmCIF structures are not supported yet.",
            details={
                "filename": filename,
                "hint": "Convert to PDB, or import the PDB entry instead. No partial parse is attempted.",
            },
        )
    raise StructureFormatError(
        f"Unsupported structure format '{suffix or 'none'}'.",
        details={"filename": filename, "supported": ["pdb", "ent"]},
    )


def inspect_pdb(path: Path, *, filename: str | None = None) -> StructureInspection:
    """Parse a PDB file and summarise what it contains."""
    size = path.stat().st_size
    if size == 0:
        raise ValidationError("The structure file is empty.")
    if size > MAX_STRUCTURE_BYTES:
        raise ValidationError(
            f"The structure file is too large ({size} bytes; limit {MAX_STRUCTURE_BYTES}).",
            details={"size_bytes": size, "limit_bytes": MAX_STRUCTURE_BYTES},
        )

    name = filename or path.name
    detect_format(name)

    models = 0
    atoms = 0
    waters: set[tuple[str, int, str]] = set()
    ions: set[str] = set()
    ligands: set[str] = set()
    altlocs: set[str] = set()
    pdb_id: str | None = None
    title: str | None = None

    chain_residues: dict[str, set[tuple[int, str]]] = {}
    chain_atoms: dict[str, int] = {}
    chain_hetero: dict[str, set[str]] = {}
    chain_numbers: dict[str, list[int]] = {}

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            record = raw[:6].strip().upper()
            if record == "HEADER":
                candidate = raw[62:66].strip()
                if candidate and candidate.isalnum():
                    pdb_id = candidate.upper()
            elif record == "TITLE":
                piece = raw[10:].strip()
                title = f"{title} {piece}".strip() if title else piece
            elif record == "MODEL":
                models += 1
            elif record in {"ATOM", "HETATM"}:
                if len(raw) < 54:
                    continue
                atoms += 1
                chain_id = raw[21].strip() or "_"
                residue_name = raw[17:20].strip().upper()
                try:
                    residue_number = int(raw[22:26])
                except ValueError:
                    continue
                insertion = raw[26].strip()
                altloc = raw[16].strip()
                if altloc:
                    altlocs.add(altloc)

                if record == "ATOM":
                    chain_residues.setdefault(chain_id, set()).add((residue_number, insertion))
                    chain_numbers.setdefault(chain_id, []).append(residue_number)
                    chain_atoms[chain_id] = chain_atoms.get(chain_id, 0) + 1
                else:
                    chain_hetero.setdefault(chain_id, set()).add(residue_name)
                    key = (chain_id, residue_number, residue_name)
                    if residue_name in WATER_RESIDUES:
                        waters.add(key)
                    elif residue_name in ION_RESIDUES:
                        ions.add(residue_name)
                    else:
                        ligands.add(residue_name)

    if atoms == 0:
        raise ValidationError(
            "The file contains no ATOM or HETATM records.",
            details={"filename": name, "hint": "Is this really a PDB coordinate file?"},
        )

    chains = tuple(
        ChainSummary(
            chain_id=chain_id,
            residue_count=len(residues),
            atom_count=chain_atoms.get(chain_id, 0),
            hetero_residues=tuple(sorted(chain_hetero.get(chain_id, set()))),
            gaps=_gaps(chain_numbers.get(chain_id, [])),
        )
        for chain_id, residues in sorted(chain_residues.items())
    )

    warnings: list[str] = []
    if models > 1:
        warnings.append(f"{models} models are present; only the first model is used by the current workflow nodes.")
    if altlocs:
        warnings.append(f"Alternate locations present ({', '.join(sorted(altlocs))}); occupancy is not resolved here.")
    if any(chain.missing_residue_count for chain in chains):
        warnings.append("Residue-numbering gaps were found; missing loops are not modelled.")

    return StructureInspection(
        filename=name,
        format="pdb",
        size_bytes=size,
        model_count=max(models, 1),
        atom_count=atoms,
        chains=chains,
        ligands=tuple(sorted(ligands)),
        waters=len(waters),
        ions=tuple(sorted(ions)),
        alternate_locations=tuple(sorted(altlocs)),
        pdb_id=pdb_id,
        title=title,
        warnings=tuple(warnings),
    )


def _gaps(residue_numbers: list[int]) -> tuple[ResidueGap, ...]:
    """Runs of missing residue numbers between the observed minimum and maximum."""
    if not residue_numbers:
        return ()
    ordered = sorted(set(residue_numbers))
    gaps: list[ResidueGap] = []
    for previous, current in pairwise(ordered):
        if current - previous > 1:
            gaps.append(ResidueGap(after_residue=previous, missing_from=previous + 1, missing_to=current - 1))
    return tuple(gaps)
