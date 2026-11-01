"""Guard-rail coverage for HAEL: every rejection path is exercised.

These are the branches that stop malformed evidence, unknown units and unchecked
costs from entering a decision. They are cheap to test and expensive to get wrong.
"""

from __future__ import annotations

import math

import pytest

from hcs_discovery.hael.acquisition import (
    AcquisitionConfig,
    AcquisitionError,
    DiversityContext,
    PredictiveDistribution,
    UnsupportedObjectiveDimensionError,
    score_action,
)
from hcs_discovery.hael.cost import CostModel, UnknownCostError
from hcs_discovery.hael.evidence import (
    EvidenceError,
    EvidenceItem,
    EvidenceLedger,
    ObjectiveVector,
    TaskObjective,
    dimension_of_endpoint,
)
from hcs_discovery.hael.scheduler import Candidate, Fidelity, SchedulerError

BASE = {
    "evidence_id": "ev_1",
    "candidate_id": "cmp_1",
    "endpoint": "egfr_pic50",
    "value": 5.0,
    "unit": "log10(mol/L)",
    "direction": "higher",
    "method": "m",
    "engine": "e",
    "engine_version": "1",
}


def _build(**overrides: object) -> EvidenceItem:
    payload = dict(BASE)
    payload.update(overrides)
    return EvidenceItem(**payload)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"evidence_id": ""}, "evidence_id must not be empty"),
        ({"candidate_id": ""}, "candidate_id must not be empty"),
        ({"endpoint": ""}, "endpoint must not be empty"),
        ({"direction": "sideways"}, "direction 'sideways'"),
        ({"status": "maybe"}, "Unknown evidence status"),
        ({"uncertainty_kind": "vibes"}, "Unknown uncertainty kind"),
        ({"applicability_domain": "elsewhere"}, "Unknown applicability domain"),
        ({"cost_seconds": -1.0}, "invalid cost"),
        ({"cost_seconds": float("inf")}, "invalid cost"),
    ],
)
def test_evidence_rejects_malformed_fields(overrides: dict[str, object], message: str):
    with pytest.raises(EvidenceError) as excinfo:
        _build(**overrides)
    assert message in excinfo.value.message


def test_evidence_rejects_non_finite_value():
    with pytest.raises(EvidenceError) as excinfo:
        _build(value=float("inf"))
    assert "non-finite value" in excinfo.value.message


def test_uncertainty_none_with_bounds_is_contradictory():
    with pytest.raises(EvidenceError) as excinfo:
        _build(uncertainty_kind="none", uncertainty_low=1.0, uncertainty_high=2.0)
    assert "declares uncertainty_kind='none'" in excinfo.value.message


def test_uncertainty_bounds_must_be_finite_and_ordered():
    with pytest.raises(EvidenceError) as non_finite:
        _build(uncertainty_kind="conformal", uncertainty_low=float("nan"), uncertainty_high=6.0)
    assert "non-finite uncertainty" in non_finite.value.message

    with pytest.raises(EvidenceError) as inverted:
        _build(uncertainty_kind="conformal", uncertainty_low=6.0, uncertainty_high=4.0, value=5.0)
    assert "low > high" in inverted.value.message


def test_standard_error_and_calibrated_flags():
    item = _build(uncertainty_kind="conformal", uncertainty_low=4.0, uncertainty_high=6.0, calibration_id="cal")
    assert item.standard_error == 1.0
    assert item.calibrated is True
    assert _build().standard_error is None


def test_task_objective_requires_its_identity_fields():
    with pytest.raises(EvidenceError):
        TaskObjective("", "e", "m", "dimensionless", "higher")
    with pytest.raises(EvidenceError):
        TaskObjective("t", "", "m", "dimensionless", "higher")
    with pytest.raises(EvidenceError):
        TaskObjective("t", "e", "", "dimensionless", "higher")
    with pytest.raises(EvidenceError):
        TaskObjective("t", "e", "m", "dimensionless", "bigger")


def test_objective_vector_requires_dimensions_and_matching_task_id():
    with pytest.raises(EvidenceError) as empty:
        ObjectiveVector(task_id="t", dimensions=())
    assert "at least one dimension" in empty.value.message

    with pytest.raises(EvidenceError) as mismatch:
        ObjectiveVector(task_id="other", dimensions=(TaskObjective("t", "e", "m", "dimensionless", "higher"),))
    assert "does not match" in mismatch.value.message

    vector = ObjectiveVector(task_id="t", dimensions=(TaskObjective("t", "e", "m", "dimensionless", "higher"),))
    assert len(vector) == 1
    assert vector.as_dict()["task_id"] == "t"
    assert vector.as_dict()["dimensions"][0]["endpoint"] == "e"


def test_gate_decision_serialises_reasons():
    decision = EvidenceLedger().gate(_build(), TaskObjective("t", "egfr_pic50", "m", "log10(mol/L)", "higher"))
    assert decision.as_dict()["eligible"] is False
    assert any("exploratory" in reason for reason in decision.as_dict()["reasons"])


def test_ledger_lookup_and_empty_frontier():
    ledger = EvidenceLedger()
    vector = ObjectiveVector(task_id="t", dimensions=(TaskObjective("t", "egfr_pic50", "m", "log10(mol/L)", "higher"),))
    assert ledger.frontier(vector) == ()
    ledger.add(_build())
    assert ledger.get("ev_1").value == 5.0
    assert dimension_of_endpoint(ledger, "egfr_pic50") == "log10(mol/L)"
    assert dimension_of_endpoint(ledger, "absent") is None


def test_frontier_handles_both_directions():
    lower = ObjectiveVector(
        task_id="t",
        dimensions=(TaskObjective("t", "docking_vina", "m", "kcal/mol", "lower"),),
    )
    ledger = EvidenceLedger()
    ledger.add(
        _build(
            evidence_id="ev_a",
            candidate_id="cmp_a",
            endpoint="docking_vina",
            unit="kcal/mol",
            direction="lower",
            value=-9.0,
            status="validated",
            uncertainty_kind="conformal",
            uncertainty_low=-10.0,
            uncertainty_high=-8.0,
            calibration_id="cal",
            applicability_domain="in_domain",
        )
    )
    ledger.add(
        _build(
            evidence_id="ev_b",
            candidate_id="cmp_b",
            endpoint="docking_vina",
            unit="kcal/mol",
            direction="lower",
            value=-7.0,
            status="validated",
            uncertainty_kind="conformal",
            uncertainty_low=-8.0,
            uncertainty_high=-6.0,
            calibration_id="cal",
            applicability_domain="in_domain",
        )
    )
    assert ledger.frontier(lower) == ("cmp_a",)


# ------------------------------------------------------------------- acquisition
VECTOR = ObjectiveVector(task_id="t", dimensions=(TaskObjective("t", "e", "m", "dimensionless", "higher"),))


def test_distribution_length_must_match_the_vector():
    with pytest.raises(AcquisitionError) as excinfo:
        score_action(
            candidate_id="c",
            fidelity_id="f",
            vector=VECTOR,
            front=(),
            distribution=PredictiveDistribution(mean=(1.0, 2.0), sd=(0.1, 0.1)),
            diversity=DiversityContext(),
            cost=1.0,
            config=AcquisitionConfig(),
        )
    assert "does not match" in excinfo.value.message


def test_distribution_rejects_bad_shapes_and_values():
    with pytest.raises(AcquisitionError):
        PredictiveDistribution(mean=(), sd=())
    with pytest.raises(AcquisitionError):
        PredictiveDistribution(mean=(1.0,), sd=(0.1, 0.2))
    with pytest.raises(AcquisitionError):
        PredictiveDistribution(mean=(1.0,), sd=(0.1,), prior_sd=(1.0, 2.0))
    with pytest.raises(AcquisitionError):
        PredictiveDistribution(mean=(float("nan"),), sd=(0.1,))
    with pytest.raises(AcquisitionError):
        PredictiveDistribution(mean=(1.0,), sd=(-0.1,))
    with pytest.raises(AcquisitionError):
        PredictiveDistribution(mean=(1.0,), sd=(0.1,), prior_sd=(-1.0,))


def test_config_rejects_degenerate_values():
    with pytest.raises(AcquisitionError):
        AcquisitionConfig(epsilon=0.0)
    with pytest.raises(AcquisitionError):
        AcquisitionConfig(lambda_eig=-1.0)
    with pytest.raises(AcquisitionError):
        AcquisitionConfig(nu_diversity=-1.0)
    with pytest.raises(AcquisitionError):
        AcquisitionConfig(samples=0)
    with pytest.raises(AcquisitionError):
        AcquisitionConfig(version="")


def test_two_dimensional_scoring_with_an_empty_front_is_positive():
    vector = ObjectiveVector(
        task_id="t",
        dimensions=(
            TaskObjective("t", "a", "m", "dimensionless", "higher"),
            TaskObjective("t", "b", "m", "dimensionless", "higher"),
        ),
    )
    score = score_action(
        candidate_id="c",
        fidelity_id="f",
        vector=vector,
        front=(),
        distribution=PredictiveDistribution(mean=(2.0, 2.0), sd=(0.2, 0.2), calibrated=True, calibration_id="cal"),
        diversity=DiversityContext(),
        cost=1.0,
        config=AcquisitionConfig(samples=64),
    )
    assert score.ehvi > 0


def test_zero_noise_prediction_is_scored_without_sampling_artifacts():
    score = score_action(
        candidate_id="c",
        fidelity_id="f",
        vector=VECTOR,
        front=((1.0,),),
        distribution=PredictiveDistribution(mean=(2.0,), sd=(0.0,), calibrated=True, calibration_id="cal"),
        diversity=DiversityContext(),
        cost=1.0,
        config=AcquisitionConfig(),
    )
    assert score.ehvi == pytest.approx(1.0)


def test_unsupported_dimension_is_explicit():
    vector = ObjectiveVector(
        task_id="t",
        dimensions=(
            TaskObjective("t", "a", "m", "dimensionless", "higher"),
            TaskObjective("t", "b", "m", "dimensionless", "higher"),
            TaskObjective("t", "c", "m", "dimensionless", "higher"),
        ),
    )
    with pytest.raises(UnsupportedObjectiveDimensionError):
        score_action(
            candidate_id="c",
            fidelity_id="f",
            vector=vector,
            front=(),
            distribution=None,
            diversity=DiversityContext(),
            cost=1.0,
            config=AcquisitionConfig(),
        )


def test_missing_distribution_is_scored_as_exploratory():
    score = score_action(
        candidate_id="c",
        fidelity_id="f",
        vector=VECTOR,
        front=(),
        distribution=None,
        diversity=DiversityContext(),
        cost=1.0,
        config=AcquisitionConfig(),
    )
    assert score.mode == "exploratory"
    assert "no_predictive_distribution" in score.reasons


# -------------------------------------------------------------------------- cost
def test_cost_model_validates_its_configuration():
    with pytest.raises(ValueError):
        CostModel(percentile=1.5)
    with pytest.raises(ValueError):
        CostModel(window=0)
    model = CostModel()
    with pytest.raises(ValueError):
        model.set_default("f", 0.0)
    with pytest.raises(ValueError):
        model.record("f", -1.0)


def test_cost_model_single_sample_and_extremes():
    model = CostModel()
    model.record("f", 4.0)
    assert model.estimate("f") == 4.0
    assert model.observations("f") == (4.0,)
    model.record("f", 8.0)
    assert model.estimate("f") == pytest.approx(7.6)  # p90 interpolates towards the slow tail
    low = CostModel(percentile=0.0)
    low.record("g", 3.0)
    low.record("g", 9.0)
    assert low.estimate("g") == pytest.approx(3.0)
    assert low.as_dict()["window"] == 20


def test_cost_model_unknown_action_raises():
    with pytest.raises(UnknownCostError) as excinfo:
        CostModel().estimate("nope")
    assert excinfo.value.code == "unknown_cost"


def test_cost_model_trims_its_window():
    model = CostModel(window=2)
    for value in (1.0, 2.0, 3.0, 4.0):
        model.record("f", value)
    assert model.observations("f") == (3.0, 4.0)


# ---------------------------------------------------------------------- scheduler
def test_scheduler_validates_its_inputs():
    with pytest.raises(SchedulerError):
        Candidate("")
    with pytest.raises(SchedulerError):
        Fidelity("", "x", rank=1)


def test_trace_without_steps_is_serialisable():
    from hcs_discovery.hael.scheduler import SchedulerTrace

    trace = SchedulerTrace(task_id="t", config={"budget_seconds": 1.0})
    assert trace.selections == ()
    assert trace.as_dict()["stop_reason"] == "no_legal_action"
    assert len(trace.digest()) == 64


def test_infinite_cost_is_rejected_at_scoring_time():
    with pytest.raises(AcquisitionError):
        score_action(
            candidate_id="c",
            fidelity_id="f",
            vector=VECTOR,
            front=(),
            distribution=None,
            diversity=DiversityContext(),
            cost=math.inf,
            config=AcquisitionConfig(),
        )
