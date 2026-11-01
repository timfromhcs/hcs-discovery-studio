"""Typed scientific evidence and the gates that keep it honest.

An :class:`EvidenceItem` is one measured or predicted number about one candidate
on one endpoint. It carries the unit, the direction, the method and engine
revision, the uncertainty kind, the calibration record and the applicability
domain, because a bare number cannot be interpreted later.

The ledger enforces three rules that matter for HAEL:

1. **No dimension mixing.** An :class:`ObjectiveVector` names one endpoint per
   dimension. There is no method that collapses several dimensions into one
   scalar, so an incomparable sum cannot be computed by accident.
2. **No unearned promotion.** Evidence reaches the validated ranking only when
   it is calibrated, in domain and produced by a method that has a reference
   test. Everything else stays visible but exploratory.
3. **No silent loss.** A failed calculation is recorded as a
   :class:`EvaluationFailure`, never as zero, a mean or a success.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from ..core.errors import ValidationError
from ..core.hashing import stable_json_hash
from .units import dimension_of

EvidenceStatus = Literal["validated", "reference_tested", "exploratory", "blocked"]
UncertaintyKind = Literal["none", "heuristic", "ensemble_spread", "conformal", "credible_interval"]
ApplicabilityDomain = Literal["in_domain", "out_of_domain", "unknown"]

STATUSES: frozenset[str] = frozenset({"validated", "reference_tested", "exploratory", "blocked"})
UNCERTAINTY_KINDS: frozenset[str] = frozenset(
    {"none", "heuristic", "ensemble_spread", "conformal", "credible_interval"}
)
DOMAINS: frozenset[str] = frozenset({"in_domain", "out_of_domain", "unknown"})

#: Uncertainty kinds that are empirically calibrated. Only these may promote
#: evidence into the validated ranking.
CALIBRATED_UNCERTAINTY: frozenset[str] = frozenset({"conformal", "credible_interval"})


class EvidenceError(ValidationError):
    """Raised when evidence is malformed or would be misinterpreted."""

    code = "evidence_invalid"


@dataclass(frozen=True)
class EvidenceItem:
    """One value about one candidate on one endpoint, with its provenance."""

    evidence_id: str
    candidate_id: str
    endpoint: str
    value: float
    unit: str
    direction: Literal["higher", "lower"]
    method: str
    engine: str
    engine_version: str
    status: EvidenceStatus = "exploratory"
    uncertainty_kind: UncertaintyKind = "none"
    uncertainty_low: float | None = None
    uncertainty_high: float | None = None
    calibration_id: str | None = None
    applicability_domain: ApplicabilityDomain = "unknown"
    cost_seconds: float | None = None
    provenance: Mapping[str, Any] = field(default_factory=dict)
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.evidence_id:
            raise EvidenceError("evidence_id must not be empty.")
        if not self.candidate_id:
            raise EvidenceError("candidate_id must not be empty.")
        if not self.endpoint:
            raise EvidenceError("endpoint must not be empty; an unlabelled number is not evidence.")
        if not _is_finite(self.value):
            raise EvidenceError(
                f"Evidence '{self.evidence_id}' has a non-finite value ({self.value!r}).",
                details={"hint": "Record a failure instead of a missing or invalid number."},
            )
        dimension_of(self.unit)
        if self.direction not in {"higher", "lower"}:
            raise EvidenceError(
                f"Evidence '{self.evidence_id}' has direction '{self.direction}'.",
                details={"hint": "Use 'higher' or 'lower'."},
            )
        if self.status not in STATUSES:
            raise EvidenceError(f"Unknown evidence status '{self.status}'.")
        if self.uncertainty_kind not in UNCERTAINTY_KINDS:
            raise EvidenceError(f"Unknown uncertainty kind '{self.uncertainty_kind}'.")
        if self.applicability_domain not in DOMAINS:
            raise EvidenceError(f"Unknown applicability domain '{self.applicability_domain}'.")
        if self.cost_seconds is not None and (not _is_finite(self.cost_seconds) or self.cost_seconds < 0):
            raise EvidenceError(f"Evidence '{self.evidence_id}' has an invalid cost ({self.cost_seconds!r}).")
        self._validate_interval()

    def _validate_interval(self) -> None:
        if self.uncertainty_kind == "none":
            if self.uncertainty_low is not None or self.uncertainty_high is not None:
                raise EvidenceError(
                    f"Evidence '{self.evidence_id}' declares uncertainty_kind='none' but has bounds.",
                    details={"hint": "State the uncertainty kind, or drop the bounds."},
                )
            return
        if self.uncertainty_low is None or self.uncertainty_high is None:
            raise EvidenceError(
                f"Evidence '{self.evidence_id}' declares '{self.uncertainty_kind}' uncertainty without bounds."
            )
        if not (_is_finite(self.uncertainty_low) and _is_finite(self.uncertainty_high)):
            raise EvidenceError(f"Evidence '{self.evidence_id}' has non-finite uncertainty bounds.")
        if self.uncertainty_low > self.uncertainty_high:
            raise EvidenceError(
                f"Evidence '{self.evidence_id}' has low > high ({self.uncertainty_low} > {self.uncertainty_high})."
            )
        if not (self.uncertainty_low <= self.value <= self.uncertainty_high):
            raise EvidenceError(
                f"Evidence '{self.evidence_id}' value {self.value} is outside its own interval "
                f"[{self.uncertainty_low}, {self.uncertainty_high}]."
            )

    @property
    def calibrated(self) -> bool:
        return self.calibration_id is not None and self.uncertainty_kind in CALIBRATED_UNCERTAINTY

    @property
    def standard_error(self) -> float | None:
        """Half-width of the interval, as a rough scale for information gain."""
        if self.uncertainty_low is None or self.uncertainty_high is None:
            return None
        return (self.uncertainty_high - self.uncertainty_low) / 2.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "candidate_id": self.candidate_id,
            "endpoint": self.endpoint,
            "value": self.value,
            "unit": self.unit,
            "direction": self.direction,
            "method": self.method,
            "engine": self.engine,
            "engine_version": self.engine_version,
            "status": self.status,
            "uncertainty_kind": self.uncertainty_kind,
            "uncertainty_low": self.uncertainty_low,
            "uncertainty_high": self.uncertainty_high,
            "calibration_id": self.calibration_id,
            "applicability_domain": self.applicability_domain,
            "cost_seconds": self.cost_seconds,
            "provenance": dict(self.provenance),
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True)
class EvaluationFailure:
    """A computation that did not produce a value. Kept, never converted to zero."""

    candidate_id: str
    endpoint: str
    engine: str
    engine_version: str
    error_code: str
    message: str
    cost_seconds: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "endpoint": self.endpoint,
            "engine": self.engine,
            "engine_version": self.engine_version,
            "error_code": self.error_code,
            "message": self.message,
            "cost_seconds": self.cost_seconds,
        }


@dataclass(frozen=True)
class TaskObjective:
    """One dimension of a task-specific objective vector."""

    task_id: str
    endpoint: str
    metric: str
    unit: str
    direction: Literal["higher", "lower"]
    requires_calibration: bool = True

    def __post_init__(self) -> None:
        if not self.task_id:
            raise EvidenceError("TaskObjective.task_id must not be empty.")
        if not self.endpoint:
            raise EvidenceError("TaskObjective.endpoint must not be empty.")
        if not self.metric:
            raise EvidenceError("TaskObjective.metric must not be empty.")
        dimension_of(self.unit)
        if self.direction not in {"higher", "lower"}:
            raise EvidenceError(f"TaskObjective direction '{self.direction}' is invalid.")

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "endpoint": self.endpoint,
            "metric": self.metric,
            "unit": self.unit,
            "direction": self.direction,
            "requires_calibration": self.requires_calibration,
        }


@dataclass(frozen=True)
class ObjectiveVector:
    """An ordered set of task dimensions.

    Deliberately provides no ``composite``/``score`` method: there is no correct
    way to add a docking energy, a predicted pIC50 and a solubility into one
    number. Callers that need a single ranking choose one dimension.
    """

    task_id: str
    dimensions: tuple[TaskObjective, ...]

    def __post_init__(self) -> None:
        if not self.dimensions:
            raise EvidenceError("An ObjectiveVector needs at least one dimension.")
        if len({d.task_id for d in self.dimensions}) != 1:
            raise EvidenceError(
                "All dimensions of one ObjectiveVector must share a task_id.",
                details={"hint": "Create separate vectors for separate tasks."},
            )
        if self.dimensions[0].task_id != self.task_id:
            raise EvidenceError(f"ObjectiveVector.task_id '{self.task_id}' does not match its dimensions.")
        endpoints = [d.endpoint for d in self.dimensions]
        if len(set(endpoints)) != len(endpoints):
            raise EvidenceError(
                "An ObjectiveVector may not list the same endpoint twice.",
                details={"hint": "Duplicate endpoints would double-count one measurement."},
            )

    @property
    def endpoints(self) -> tuple[str, ...]:
        return tuple(d.endpoint for d in self.dimensions)

    def __len__(self) -> int:
        return len(self.dimensions)

    def as_dict(self) -> dict[str, Any]:
        return {"task_id": self.task_id, "dimensions": [d.as_dict() for d in self.dimensions]}


@dataclass(frozen=True)
class GateDecision:
    """Why a piece of evidence may or may not influence the validated frontier."""

    eligible: bool
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"eligible": self.eligible, "reasons": list(self.reasons)}


class EvidenceLedger:
    """Evidence plus failures for one project or run, with gating and a frontier."""

    def __init__(self) -> None:
        self._items: dict[str, EvidenceItem] = {}
        self._failures: list[EvaluationFailure] = []

    # ---------------------------------------------------------------- mutation
    def add(self, item: EvidenceItem) -> EvidenceItem:
        existing = self._items.get(item.evidence_id)
        if existing is not None and existing != item:
            raise EvidenceError(
                f"Evidence id '{item.evidence_id}' already exists with different content.",
                details={"hint": "Evidence is immutable; use a new id for a new measurement."},
            )
        self._items[item.evidence_id] = item
        return item

    def add_failure(self, failure: EvaluationFailure) -> EvaluationFailure:
        self._failures.append(failure)
        return failure

    # ----------------------------------------------------------------- reading
    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[EvidenceItem]:
        return iter(self._items.values())

    @property
    def failures(self) -> tuple[EvaluationFailure, ...]:
        return tuple(self._failures)

    def get(self, evidence_id: str) -> EvidenceItem:
        return self._items[evidence_id]

    def for_candidate(self, candidate_id: str, endpoint: str | None = None) -> tuple[EvidenceItem, ...]:
        return tuple(
            item
            for item in self._items.values()
            if item.candidate_id == candidate_id and (endpoint is None or item.endpoint == endpoint)
        )

    def candidates(self) -> tuple[str, ...]:
        return tuple(sorted({item.candidate_id for item in self._items.values()}))

    # ------------------------------------------------------------------- gates
    def gate(self, item: EvidenceItem, dimension: TaskObjective) -> GateDecision:
        """Decide whether ``item`` may enter the validated frontier for ``dimension``."""
        reasons: list[str] = []
        if item.endpoint != dimension.endpoint:
            reasons.append(
                f"endpoint_mismatch: evidence is '{item.endpoint}', task dimension is '{dimension.endpoint}'"
            )
        if item.unit != dimension.unit:
            reasons.append(f"unit_mismatch: evidence is in '{item.unit}', task expects '{dimension.unit}'")
        else:
            # Same label is necessary; confirm the registry agrees the label is sane.
            dimension_of(item.unit)
        if item.direction != dimension.direction:
            reasons.append(f"direction_mismatch: evidence is '{item.direction}', task expects '{dimension.direction}'")
        if item.status == "blocked":
            reasons.append("blocked: the method is blocked by policy or validation")
        elif item.status == "exploratory":
            reasons.append("exploratory: the method has no reference evidence for this endpoint")
        if dimension.requires_calibration and not item.calibrated:
            reasons.append("not_calibrated: needs a calibration record and a conformal or credible interval")
        if item.applicability_domain != "in_domain":
            reasons.append(f"applicability_domain: '{item.applicability_domain}', needs 'in_domain'")
        return GateDecision(eligible=not reasons, reasons=tuple(reasons))

    def validated_items(self, dimension: TaskObjective) -> tuple[EvidenceItem, ...]:
        return tuple(item for item in self._items.values() if self.gate(item, dimension).eligible)

    # ----------------------------------------------------------------- frontier
    def frontier(self, vector: ObjectiveVector) -> tuple[str, ...]:
        """Candidates on the Pareto frontier, using validated evidence only.

        A candidate is described only when every dimension has exactly one
        eligible value; candidates with gaps are omitted rather than imputed.
        """
        points = self._validated_points(vector)
        if not points:
            return ()
        ordered = sorted(points.items())
        front: list[str] = []
        for candidate_id, values in ordered:
            dominated = False
            for other_id, other in ordered:
                if other_id == candidate_id:
                    continue
                if _dominates(vector, other, values):
                    dominated = True
                    break
            if not dominated:
                front.append(candidate_id)
        return tuple(front)

    def objective_table(self, vector: ObjectiveVector) -> dict[str, dict[str, float]]:
        """Validated values per candidate and dimension. Gaps are absent, not zero."""
        return {
            cid: dict(zip(vector.endpoints, vals, strict=True)) for cid, vals in self._validated_points(vector).items()
        }

    def validated_points(self, vector: ObjectiveVector) -> tuple[tuple[float, ...], ...]:
        """Points usable for a Pareto or hypervolume calculation, in vector order."""
        return tuple(self._validated_points(vector).values())

    def _validated_points(self, vector: ObjectiveVector) -> dict[str, tuple[float, ...]]:
        points: dict[str, tuple[float, ...]] = {}
        for candidate_id in self.candidates():
            values: list[float] = []
            for dimension in vector.dimensions:
                eligible = [
                    item
                    for item in self.for_candidate(candidate_id, dimension.endpoint)
                    if self.gate(item, dimension).eligible
                ]
                if len(eligible) != 1:
                    # Zero (unknown) or several (ambiguous) validated values: omit.
                    values = []
                    break
                values.append(eligible[0].value)
            if values:
                points[candidate_id] = tuple(values)
        return points

    # ------------------------------------------------------------------ digest
    def digest(self) -> str:
        """Content hash of the evidence, stable across processes."""
        return stable_json_hash(
            {
                "items": [item.as_dict() for item in sorted(self._items.values(), key=lambda i: i.evidence_id)],
                "failures": [failure.as_dict() for failure in self._failures],
            }
        )


def _is_finite(value: float | None) -> bool:
    return value is not None and isinstance(value, (int, float)) and math.isfinite(float(value))


def _dominates(vector: ObjectiveVector, left: Sequence[float], right: Sequence[float]) -> bool:
    """True when ``left`` is at least as good everywhere and better somewhere."""
    better = False
    for dimension, left_value, right_value in zip(vector.dimensions, left, right, strict=True):
        if dimension.direction == "higher":
            if left_value < right_value:
                return False
            better = better or left_value > right_value
        else:
            if left_value > right_value:
                return False
            better = better or left_value < right_value
    return better


def dimension_of_endpoint(items: Iterable[EvidenceItem], endpoint: str) -> str | None:
    """Return the first unit seen for ``endpoint``, for diagnostics and UI labels."""
    for item in items:
        if item.endpoint == endpoint:
            return item.unit
    return None
