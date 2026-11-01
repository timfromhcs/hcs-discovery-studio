"""Unit registry for evidence values.

The registry exists to make one mistake impossible: combining numbers whose units
mean different things. It deliberately performs **no implicit conversion**. A
caller that wants a converted value must state the factor and record it in the
evidence provenance.

Two values can share a dimension (``kcal/mol`` and ``kJ/mol`` are both molar
energy) and still come from different endpoints. Dimension compatibility is a
necessary condition for comparison, never a sufficient one: endpoints are gated
separately in :mod:`hcs_discovery.hael.evidence`.
"""

from __future__ import annotations

from typing import Final

from ..core.errors import ValidationError

#: Unit -> physical dimension. Only units the product actually emits belong here.
UNIT_DIMENSIONS: Final[dict[str, str]] = {
    "dimensionless": "dimensionless",
    "fraction": "fraction",
    "g/mol": "molar_mass",
    "A^2": "area",
    "A^3": "volume",
    "kcal/mol": "molar_energy",
    "kJ/mol": "molar_energy",
    "log10(mol/L)": "log_molar_concentration",
    "log10(ug/mL)": "log_mass_concentration",
    "mol/L": "molar_concentration",
    "s": "time",
    "A": "length",
    "K": "temperature",
    "e": "elementary_charge",
}


class UnknownUnitError(ValidationError):
    """Raised when a unit is not declared in the registry."""

    code = "unknown_unit"

    def __init__(self, unit: str) -> None:
        super().__init__(
            f"Unknown unit '{unit}'. Declared units: {', '.join(sorted(UNIT_DIMENSIONS))}.",
            details={
                "unit": unit,
                "hint": "Add the unit to hael.units.UNIT_DIMENSIONS only when the product really emits it.",
            },
        )
        self.unit = unit


def dimension_of(unit: str) -> str:
    """Return the physical dimension of ``unit`` or raise :class:`UnknownUnitError`."""
    try:
        return UNIT_DIMENSIONS[unit]
    except KeyError:  # pragma: no cover - exercised through the public helpers
        raise UnknownUnitError(unit) from None


def is_known(unit: str) -> bool:
    return unit in UNIT_DIMENSIONS


def require_same_dimension(left: str, right: str) -> None:
    """Raise ``unit_mismatch`` unless both units share a dimension."""
    left_dimension = dimension_of(left)
    right_dimension = dimension_of(right)
    if left_dimension != right_dimension:
        raise UnitMismatchError(left, right)


class UnitMismatchError(ValidationError):
    """Raised when two incompatible units would be compared or combined."""

    code = "unit_mismatch"

    def __init__(self, left: str, right: str) -> None:
        super().__init__(
            f"Unit '{left}' ({dimension_of(left)}) is not comparable with '{right}' ({dimension_of(right)}).",
            details={
                "left": left,
                "right": right,
                "hint": "Keep incomparable units as separate dimensions; never sum them into one score.",
            },
        )
        self.left = left
        self.right = right
