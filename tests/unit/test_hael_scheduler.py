"""Tests for the HAEL scheduler: determinism, budgets, gates, failure recovery.

The scheduler is the only component that spends compute, so its failure modes are
the expensive ones. Each test here corresponds to a rule in AGENTS.md §4.8.
"""

from __future__ import annotations

import pytest

from hcs_discovery.hael.acquisition import AcquisitionConfig, PredictiveDistribution, UnsupportedObjectiveDimensionError
from hcs_discovery.hael.cost import CostModel, UnknownCostError
from hcs_discovery.hael.evidence import (
    EvaluationFailure,
    EvidenceItem,
    EvidenceLedger,
    ObjectiveVector,
    TaskObjective,
)
from hcs_discovery.hael.scheduler import (
    ActionResult,
    Candidate,
    Fidelity,
    Scheduler,
    SchedulerConfig,
    SchedulerError,
    describe_trace,
)

VECTOR = ObjectiveVector(
    task_id="egfr_potency",
    dimensions=(
        TaskObjective(
            task_id="egfr_potency",
            endpoint="egfr_pic50",
            metric="predicted_pic50",
            unit="log10(mol/L)",
            direction="higher",
        ),
    ),
)

CHEAP = Fidelity("f1", "Descriptors", rank=1)
MODELLED = Fidelity("f2", "Endpoint model", rank=2)


def _calibrated(mean: float = 6.5, sd: float = 0.3) -> PredictiveDistribution:
    return PredictiveDistribution(mean=(mean,), sd=(sd,), prior_sd=(1.0,), calibrated=True, calibration_id="cal_x")


def _evidence(candidate: str, value: float, **overrides: object) -> EvidenceItem:
    payload: dict[str, object] = {
        "evidence_id": f"ev_{candidate}_{overrides.get('evidence_id_suffix', '1')}",
        "candidate_id": candidate,
        "endpoint": "egfr_pic50",
        "value": value,
        "unit": "log10(mol/L)",
        "direction": "higher",
        "method": "chemprop-v2",
        "engine": "chemprop",
        "engine_version": "2.1.0",
        "status": "validated",
        "uncertainty_kind": "conformal",
        "uncertainty_low": value - 0.5,
        "uncertainty_high": value + 0.5,
        "calibration_id": "cal_x",
        "applicability_domain": "in_domain",
    }
    overrides.pop("evidence_id_suffix", None)
    payload.update(overrides)
    return EvidenceItem(**payload)  # type: ignore[arg-type]


def _costs(*, cheap: float = 1.0, modelled: float = 10.0) -> CostModel:
    model = CostModel()
    model.set_default("f1", cheap)
    model.set_default("f2", modelled)
    model.set_default("f3", 5.0)
    return model


def _scheduler(
    ledger: EvidenceLedger | None = None,
    *,
    budget: float = 100.0,
    distribution=None,
    allow_exploratory: bool = True,
    min_acquisition: float = 0.0,
) -> Scheduler:
    return Scheduler(
        # `ledger or ...` would discard an empty ledger, because a ledger with no
        # evidence is falsy; keep the caller's object explicitly.
        vector=VECTOR,
        ledger=ledger if ledger is not None else EvidenceLedger(),
        costs=_costs(),
        config=SchedulerConfig(
            budget_seconds=budget,
            acquisition=AcquisitionConfig(seed=11, samples=128),
            allow_exploratory=allow_exploratory,
            min_acquisition=min_acquisition,
        ),
        distribution=distribution or (lambda candidate, fidelity: _calibrated()),
    )


def _executor(record: list[tuple[str, str]] | None = None, *, failing: set[str] | None = None):
    def execute(candidate: Candidate, fidelity: Fidelity) -> ActionResult:
        if record is not None:
            record.append((candidate.candidate_id, fidelity.fidelity_id))
        if failing and candidate.candidate_id in failing:
            return ActionResult(
                failures=(
                    EvaluationFailure(
                        candidate_id=candidate.candidate_id,
                        endpoint="egfr_pic50",
                        engine="chemprop",
                        engine_version="2.1.0",
                        error_code="engine_crash",
                        message="Model process exited with code 1",
                    ),
                ),
                cost_seconds=0.5,
                error="engine_crash",
            )
        return ActionResult(
            evidence=(
                _evidence(
                    candidate.candidate_id,
                    6.0 + 0.1 * len(record or []),
                    evidence_id_suffix=fidelity.fidelity_id,
                ),
            ),
            cost_seconds=2.0,
        )

    return execute


# ------------------------------------------------------------------ determinism
def test_same_inputs_produce_the_same_selection_sequence():
    candidates = [Candidate("cmp_a"), Candidate("cmp_b"), Candidate("cmp_c")]
    first = _scheduler(budget=6.0).run(candidates, [CHEAP, MODELLED], _executor())
    second = _scheduler(budget=6.0).run(candidates, [CHEAP, MODELLED], _executor())
    assert first.selections == second.selections
    assert first.digest() == second.digest()


def test_trace_records_every_considered_and_skipped_action():
    trace = _scheduler(budget=100.0).run([Candidate("cmp_a")], [CHEAP, MODELLED], _executor())
    assert trace.steps
    first_step = trace.steps[0]
    assert first_step.considered
    assert isinstance(first_step.considered[0], dict)
    assert first_step.rationale
    # The second action for the same candidate was not chosen yet, so it is listed.
    assert len(trace.steps[0].considered) >= 1


# ---------------------------------------------------------------- budget and cost
def test_budget_is_respected_and_the_run_stops_when_exhausted():
    trace = _scheduler(budget=3.0).run(
        [Candidate("cmp_a"), Candidate("cmp_b"), Candidate("cmp_c")],
        [CHEAP],
        _executor(),
    )
    assert trace.stop_reason in {"budget_exhausted", "no_legal_action"}
    assert trace.steps[0].budget_after <= 3.0
    assert all(step.budget_after >= 0.0 for step in trace.steps)


def test_action_without_a_known_cost_is_skipped_not_guessed():
    scheduler = Scheduler(
        vector=VECTOR,
        ledger=EvidenceLedger(),
        costs=CostModel(),  # nothing recorded, no defaults
        config=SchedulerConfig(budget_seconds=10.0),
        distribution=lambda candidate, fidelity: _calibrated(),
    )
    trace = scheduler.run([Candidate("cmp_a")], [CHEAP], _executor())
    assert trace.steps == ()
    assert trace.stop_reason == "no_legal_action"


def test_cost_model_raises_instead_of_inventing_a_number():
    with pytest.raises(UnknownCostError):
        CostModel().estimate("f9")


def test_cost_estimate_uses_the_recorded_percentile():
    model = CostModel(percentile=0.9)
    for seconds in (1.0, 2.0, 3.0, 4.0, 100.0):
        model.record("f1", seconds)
    assert model.estimate("f1") > 4.0  # the slow tail dominates p90


# ------------------------------------------------------------------- gate integrity
def test_unavailable_fidelity_is_reported_not_run():
    ledger = EvidenceLedger()
    unavailable = Fidelity("f4", "Boltz-2", rank=4, available=False, unavailable_reason="needs_gpu")
    trace = _scheduler(ledger).run([Candidate("cmp_a")], [CHEAP, unavailable], _executor())
    assert all(step.selected_fidelity != "f4" for step in trace.steps)
    reasons = [item["reason"] for item in trace.steps[0].skipped]
    assert any("unavailable: needs_gpu" in reason for reason in reasons)


def test_exploratory_actions_can_be_forbidden():
    scheduler = _scheduler(distribution=lambda candidate, fidelity: None, allow_exploratory=False)
    trace = scheduler.run([Candidate("cmp_a")], [CHEAP], _executor())
    assert trace.steps == ()
    reasons = [item["reason"] for item in _skipped_reasons(scheduler, [Candidate("cmp_a")])]
    assert any("exploratory_not_allowed" in reason for reason in reasons)


def _skipped_reasons(scheduler: Scheduler, candidates: list[Candidate]) -> list[dict[str, object]]:
    _, skipped = scheduler._enumerate(candidates, [CHEAP], set(), scheduler.config.budget_seconds)
    return skipped


def test_uncalibrated_fidelity_cannot_move_the_validated_frontier():
    """A fidelity flagged as not validated must produce exploratory evidence only."""
    ledger = EvidenceLedger()
    unvalidated = Fidelity("f3", "Learned docking", rank=3, validated=False)
    trace = _scheduler(ledger).run([Candidate("cmp_a")], [unvalidated], _executor())
    assert trace.steps
    assert trace.steps[0].mode == "exploratory"


# --------------------------------------------------------------- failure recovery
def test_a_failed_engine_does_not_end_the_campaign():
    executed: list[tuple[str, str]] = []
    trace = _scheduler(budget=50.0).run(
        [Candidate("cmp_a"), Candidate("cmp_b")],
        [CHEAP, MODELLED],
        _executor(executed, failing={"cmp_a"}),
    )
    assert trace.steps[0].error == "engine_crash"
    assert len(trace.steps) >= 2
    assert any(candidate == "cmp_b" for candidate, _ in executed)
    assert trace.stop_reason != "cancelled"


def test_failures_are_kept_in_the_ledger_and_never_become_values():
    ledger = EvidenceLedger()
    _scheduler(ledger, budget=50.0).run([Candidate("cmp_a")], [CHEAP], _executor(failing={"cmp_a"}))
    assert ledger.failures
    assert all(item.candidate_id != "cmp_a" for item in ledger)
    assert ledger.objective_table(VECTOR) == {}


# ------------------------------------------------------------------- guard rails
def test_cancellation_stops_before_the_next_action():
    executed: list[tuple[str, str]] = []
    checks = {"count": 0}

    def cancelled() -> bool:
        checks["count"] += 1
        return checks["count"] > 1

    trace = _scheduler(budget=100.0).run(
        [Candidate("cmp_a"), Candidate("cmp_b"), Candidate("cmp_c")],
        [CHEAP],
        _executor(executed),
        cancelled=cancelled,
    )
    assert trace.stop_reason == "cancelled"
    assert len(executed) == 1


def test_max_steps_bounds_the_campaign():
    scheduler = Scheduler(
        vector=VECTOR,
        ledger=EvidenceLedger(),
        costs=_costs(),
        config=SchedulerConfig(budget_seconds=1000.0, max_steps=2),
        distribution=lambda candidate, fidelity: _calibrated(),
    )
    trace = scheduler.run([Candidate(f"cmp_{index}") for index in range(10)], [CHEAP], _executor())
    assert trace.stop_reason == "max_steps_reached"
    assert len(trace.steps) == 2


def test_unsupported_objective_dimension_fails_before_spending_compute():
    vector = ObjectiveVector(
        task_id="wide",
        dimensions=(
            TaskObjective("wide", "a", "m", "dimensionless", "higher"),
            TaskObjective("wide", "b", "m", "dimensionless", "higher"),
            TaskObjective("wide", "c", "m", "dimensionless", "higher"),
        ),
    )
    executed: list[tuple[str, str]] = []
    scheduler = Scheduler(
        vector=vector,
        ledger=EvidenceLedger(),
        costs=_costs(),
        config=SchedulerConfig(budget_seconds=100.0),
    )
    with pytest.raises(UnsupportedObjectiveDimensionError):
        scheduler.run([Candidate("cmp_a")], [CHEAP], _executor(executed))
    assert executed == []


def test_fidelity_without_a_reason_for_being_unavailable_is_rejected():
    with pytest.raises(SchedulerError):
        Fidelity("f9", "Broken", rank=9, available=False)


def test_describe_trace_is_human_readable():
    trace = _scheduler(budget=10.0).run([Candidate("cmp_a")], [CHEAP], _executor())
    lines = list(describe_trace(trace))
    assert lines[-1].startswith("stop:")
    assert "cmp_a" in lines[0]
