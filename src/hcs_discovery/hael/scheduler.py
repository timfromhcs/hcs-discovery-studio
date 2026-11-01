"""Deterministic, auditable scheduling of the next calculation.

The scheduler is a normal Python service, not a UI concern. It enumerates legal
``(candidate, fidelity)`` actions, scores them with the HAEL rule, executes the
best one through an injected :class:`Executor`, updates the evidence ledger and
repeats until a stop condition is reached.

Two integrity properties are structural rather than aspirational:

* An action may only influence the validated frontier when its evidence passes
  :meth:`EvidenceLedger.gate`. Actions without a calibrated distribution are
  scored by the exploratory policy and are never allowed to change the validated
  frontier (they are additive evidence with ``status='exploratory'``).
* Every considered and skipped action is written to the trace with its reason
  and the features the score used, so a decision can be re-derived later.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from ..core.errors import ValidationError
from ..core.hashing import stable_json_hash
from .acquisition import (
    AcquisitionConfig,
    DiversityContext,
    PredictiveDistribution,
    UnsupportedObjectiveDimensionError,
    score_action,
)
from .cost import CostModel, UnknownCostError
from .evidence import (
    EvaluationFailure,
    EvidenceItem,
    EvidenceLedger,
    ObjectiveVector,
)

StopReason = Literal[
    "budget_exhausted",
    "no_legal_action",
    "max_steps_reached",
    "cancelled",
    "unsupported_objective",
]


class SchedulerError(ValidationError):
    code = "scheduler_invalid"


@dataclass(frozen=True)
class Candidate:
    """A compound (optionally bound to a target/pocket) that can be computed on."""

    candidate_id: str
    scaffold_id: str | None = None
    pocket_id: str | None = None

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise SchedulerError("Candidate.candidate_id must not be empty.")

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "scaffold_id": self.scaffold_id,
            "pocket_id": self.pocket_id,
        }


@dataclass(frozen=True)
class Fidelity:
    """One rung of the evidence ladder as this host can actually run it."""

    fidelity_id: str
    name: str
    rank: int
    available: bool = True
    unavailable_reason: str | None = None
    validated: bool = True

    def __post_init__(self) -> None:
        if not self.fidelity_id:
            raise SchedulerError("Fidelity.fidelity_id must not be empty.")
        if not self.available and not self.unavailable_reason:
            raise SchedulerError(
                f"Fidelity '{self.fidelity_id}' is unavailable without a reason.",
                details={"hint": "Say why it cannot run, so the UI can show an honest state."},
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "fidelity_id": self.fidelity_id,
            "name": self.name,
            "rank": self.rank,
            "available": self.available,
            "unavailable_reason": self.unavailable_reason,
            "validated": self.validated,
        }


@dataclass(frozen=True)
class ActionResult:
    """What executing one action produced."""

    evidence: tuple[EvidenceItem, ...] = ()
    failures: tuple[EvaluationFailure, ...] = ()
    cost_seconds: float | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if self.cost_seconds is not None and (not math.isfinite(self.cost_seconds) or self.cost_seconds < 0):
            raise SchedulerError(f"ActionResult.cost_seconds is invalid ({self.cost_seconds!r}).")


class Executor(Protocol):
    """Injected execution boundary. Implementations live in the run/worker layer."""

    def __call__(self, candidate: Candidate, fidelity: Fidelity) -> ActionResult: ...


@dataclass(frozen=True)
class SchedulerConfig:
    """Budgets and weights, recorded in the trace so a decision can be replayed."""

    budget_seconds: float
    acquisition: AcquisitionConfig = field(default_factory=AcquisitionConfig)
    min_acquisition: float = 0.0
    max_steps: int = 100
    allow_exploratory: bool = True
    cost_percentile: float = 0.9
    cost_window: int = 20

    def __post_init__(self) -> None:
        if not math.isfinite(self.budget_seconds) or self.budget_seconds < 0:
            raise SchedulerError("budget_seconds must be finite and >= 0.")
        if self.max_steps < 1:
            raise SchedulerError("max_steps must be >= 1.")

    def as_dict(self) -> dict[str, Any]:
        return {
            "budget_seconds": self.budget_seconds,
            "acquisition": self.acquisition.as_dict(),
            "min_acquisition": self.min_acquisition,
            "max_steps": self.max_steps,
            "allow_exploratory": self.allow_exploratory,
            "cost_percentile": self.cost_percentile,
            "cost_window": self.cost_window,
        }


@dataclass(frozen=True)
class Step:
    """One scheduler decision and its observed consequences."""

    index: int
    selected_candidate: str
    selected_fidelity: str
    acquisition: float
    mode: str
    budget_before: float
    cost_recorded: float | None
    budget_after: float
    rationale: tuple[str, ...]
    considered: tuple[dict[str, Any], ...]
    skipped: tuple[dict[str, Any], ...]
    error: str | None = None
    evidence_ids: tuple[str, ...] = ()
    failure_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "selected": {"candidate_id": self.selected_candidate, "fidelity_id": self.selected_fidelity},
            "acquisition": self.acquisition,
            "mode": self.mode,
            "budget_before": self.budget_before,
            "cost_recorded": self.cost_recorded,
            "budget_after": self.budget_after,
            "rationale": list(self.rationale),
            "considered": list(self.considered),
            "skipped": list(self.skipped),
            "error": self.error,
            "evidence_ids": list(self.evidence_ids),
            "failure_count": self.failure_count,
        }


@dataclass(frozen=True)
class SchedulerTrace:
    """The complete, reproducible record of a scheduling session."""

    task_id: str
    config: dict[str, Any]
    steps: tuple[Step, ...] = ()
    stop_reason: StopReason = "no_legal_action"
    ledger_digest: str = ""
    evidence_digest: str = ""

    @property
    def selections(self) -> tuple[tuple[str, str], ...]:
        return tuple((step.selected_candidate, step.selected_fidelity) for step in self.steps)

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "config": self.config,
            "steps": [step.as_dict() for step in self.steps],
            "stop_reason": self.stop_reason,
            "ledger_digest": self.ledger_digest,
            "evidence_digest": self.evidence_digest,
        }

    def digest(self) -> str:
        return stable_json_hash(self.as_dict())


DistributionProvider = Callable[[Candidate, Fidelity], "PredictiveDistribution | None"]


class Scheduler:
    """Runs the ladder. Pure with respect to the ledger and the injected executor."""

    def __init__(
        self,
        *,
        vector: ObjectiveVector,
        ledger: EvidenceLedger,
        costs: CostModel,
        config: SchedulerConfig,
        distribution: DistributionProvider | None = None,
    ) -> None:
        self.vector = vector
        self.ledger = ledger
        self.costs = costs
        self.config = config
        self.distribution = distribution

    def run(
        self,
        candidates: Sequence[Candidate],
        fidelities: Sequence[Fidelity],
        executor: Executor,
        *,
        cancelled: Callable[[], bool] | None = None,
    ) -> SchedulerTrace:
        if len(self.vector.dimensions) not in (1, 2):
            # Fail before spending anything rather than part way through.
            raise UnsupportedObjectiveDimensionError(len(self.vector.dimensions))

        done: set[tuple[str, str]] = set()
        steps: list[Step] = []
        budget = self.config.budget_seconds
        stop: StopReason = "no_legal_action"
        by_id = {candidate.candidate_id: candidate for candidate in candidates}

        while True:
            if cancelled is not None and cancelled():
                stop = "cancelled"
                break
            if len(steps) >= self.config.max_steps:
                stop = "max_steps_reached"
                break

            considered, skipped = self._enumerate(candidates, fidelities, done, budget)
            if not considered:
                stop = "no_legal_action"
                break

            selected = considered[0]
            key = (selected.candidate_id, selected.fidelity_id)
            budget_before = budget
            result = executor(
                by_id[selected.candidate_id],
                next(f for f in fidelities if f.fidelity_id == selected.fidelity_id),
            )
            cost = result.cost_seconds if result.cost_seconds is not None else selected.cost
            self._absorb(result, key)
            done.add(key)
            budget = max(0.0, budget - cost)

            steps.append(
                Step(
                    index=len(steps),
                    selected_candidate=selected.candidate_id,
                    selected_fidelity=selected.fidelity_id,
                    acquisition=selected.acquisition,
                    mode=selected.mode,
                    budget_before=budget_before,
                    cost_recorded=result.cost_seconds,
                    budget_after=budget,
                    rationale=selected.reasons or ("highest cost-adjusted acquisition",),
                    considered=tuple(item.as_dict() for item in considered[:5]),
                    skipped=tuple(skipped),
                    error=result.error,
                    evidence_ids=tuple(item.evidence_id for item in result.evidence),
                    failure_count=len(result.failures),
                )
            )

            if result.error and not result.evidence:
                # A failed engine must not end the campaign; the next best action runs.
                continue
            if budget <= 0:
                stop = "budget_exhausted"
                break

        return SchedulerTrace(
            task_id=self.vector.task_id,
            config=self.config.as_dict(),
            steps=tuple(steps),
            stop_reason=stop,
            ledger_digest=self.ledger.digest(),
            evidence_digest=stable_json_hash([item.as_dict() for item in self.ledger]),
        )

    # ----------------------------------------------------------------- internals
    def _enumerate(
        self,
        candidates: Sequence[Candidate],
        fidelities: Sequence[Fidelity],
        done: set[tuple[str, str]],
        budget: float,
    ) -> tuple[list[Any], list[dict[str, Any]]]:
        scored = []
        skipped: list[dict[str, Any]] = []
        front = self.ledger.validated_points(self.vector)
        selected_scaffolds = frozenset(
            candidate.scaffold_id for candidate in candidates if candidate.scaffold_id and _is_done(candidate, done)
        )
        selected_pockets = frozenset(
            candidate.pocket_id for candidate in candidates if candidate.pocket_id and _is_done(candidate, done)
        )

        for candidate in sorted(candidates, key=lambda c: c.candidate_id):
            for fidelity in sorted(fidelities, key=lambda f: (f.rank, f.fidelity_id)):
                key = (candidate.candidate_id, fidelity.fidelity_id)
                if key in done:
                    continue
                if not fidelity.available:
                    skipped.append(
                        {
                            "candidate_id": candidate.candidate_id,
                            "fidelity_id": fidelity.fidelity_id,
                            "reason": f"unavailable: {fidelity.unavailable_reason}",
                        }
                    )
                    continue
                if not self.costs.cost_known(fidelity.fidelity_id):
                    skipped.append(
                        {
                            "candidate_id": candidate.candidate_id,
                            "fidelity_id": fidelity.fidelity_id,
                            "reason": "unknown_cost: no measured or configured cost",
                        }
                    )
                    continue
                try:
                    cost = self.costs.estimate(fidelity.fidelity_id)
                except UnknownCostError:  # pragma: no cover - guarded above
                    continue
                if cost > budget:
                    skipped.append(
                        {
                            "candidate_id": candidate.candidate_id,
                            "fidelity_id": fidelity.fidelity_id,
                            "reason": f"over_budget: {cost:.3f}s > {budget:.3f}s",
                        }
                    )
                    continue

                distribution = self.distribution(candidate, fidelity) if self.distribution else None
                if distribution is not None and not fidelity.validated:
                    # The fidelity cannot produce validated evidence; treat its
                    # prediction as exploratory so it cannot move the frontier.
                    distribution = PredictiveDistribution(
                        mean=distribution.mean,
                        sd=distribution.sd,
                        prior_sd=distribution.prior_sd,
                        calibrated=False,
                        calibration_id=None,
                    )
                score = score_action(
                    candidate_id=candidate.candidate_id,
                    fidelity_id=fidelity.fidelity_id,
                    vector=self.vector,
                    front=front,
                    distribution=distribution,
                    diversity=DiversityContext(
                        selected_scaffolds=selected_scaffolds,
                        selected_pockets=selected_pockets,
                        candidate_scaffold=candidate.scaffold_id,
                        candidate_pocket=candidate.pocket_id,
                    ),
                    cost=cost,
                    config=self.config.acquisition,
                )
                if score.mode == "exploratory" and not self.config.allow_exploratory:
                    skipped.append(
                        {
                            "candidate_id": candidate.candidate_id,
                            "fidelity_id": fidelity.fidelity_id,
                            "reason": "exploratory_not_allowed: " + "; ".join(score.reasons),
                        }
                    )
                    continue
                if score.acquisition <= self.config.min_acquisition:
                    skipped.append(
                        {
                            "candidate_id": candidate.candidate_id,
                            "fidelity_id": fidelity.fidelity_id,
                            "reason": f"below_threshold: {score.acquisition:.6g} <= {self.config.min_acquisition:.6g}",
                        }
                    )
                    continue
                scored.append(score)

        # Deterministic ordering: validated first, then acquisition, then cost, then id.
        scored.sort(
            key=lambda s: (
                0 if s.validated else 1,
                -s.acquisition,
                s.cost,
                s.candidate_id,
                s.fidelity_id,
            )
        )
        return scored, skipped

    def _absorb(self, result: ActionResult, key: tuple[str, str]) -> None:
        for item in result.evidence:
            self.ledger.add(item)
        for failure in result.failures:
            self.ledger.add_failure(failure)
        if result.cost_seconds is not None:
            self.costs.record(key[1], result.cost_seconds)


def _is_done(candidate: Candidate, done: set[tuple[str, str]]) -> bool:
    return any(candidate_id == candidate.candidate_id for candidate_id, _ in done)


def describe_trace(trace: SchedulerTrace) -> Iterable[str]:
    """Human-readable one-line-per-step summary for CLI output and reports."""
    for step in trace.steps:
        yield (
            f"{step.index:>2}. {step.selected_candidate} @ {step.selected_fidelity} "
            f"[{step.mode}] A={step.acquisition:.6g} cost={step.cost_recorded!r} "
            f"budget {step.budget_before:.1f}s -> {step.budget_after:.1f}s"
        )
    yield f"stop: {trace.stop_reason} after {len(trace.steps)} step(s)"
