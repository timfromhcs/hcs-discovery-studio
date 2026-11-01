"""Structure parsing and inspection helpers."""

from __future__ import annotations

from .pdb import (
    MAX_STRUCTURE_BYTES,
    ChainSummary,
    ResidueGap,
    StructureFormatError,
    StructureInspection,
    detect_format,
    inspect_pdb,
)

__all__ = [
    "MAX_STRUCTURE_BYTES",
    "ChainSummary",
    "ResidueGap",
    "StructureFormatError",
    "StructureInspection",
    "detect_format",
    "inspect_pdb",
]
