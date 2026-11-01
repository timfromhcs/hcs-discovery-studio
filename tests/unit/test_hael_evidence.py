"""Tests for typed evidence, gates and the objective frontier.

These encode the rules that keep HAEL scientifically honest: units cannot be
mixed, unearned evidence cannot reach the validated frontier, gaps are not
imputed and failures are preserved.
"""

from __future__ import annotations

import pytest

from hcs_discovery.core.errors import ValidationError
from hcs_discovery.hael.evidence import (
    EvaluationFailure,
    EvidenceError,
    EvidenceItem,
    EvidenceLedger,
    GateDecision,
    ObjectiveVector,
    TaskObjective,
)
from hcs_discovery.hael.units import UnitMismatchError, UnknownUnitError, dimension_of, require_same_dimension


def _item(evidence_id: str, candidate: str, value: float, **overrides: object) -> EvidenceItem:
    payload: dict[str, object] = {
        "evidence_id": evidence_id,
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
        "uncertainty_low": value - 1.0,
        "uncertainty_high": value + 1.0,
        "calibration_id": "cal_2026_11_01",
        "applicability_domain": "in_domain",
    }
    payload.update(overrides)
    return EvidenceItem(**payload)  # type: ignore[arg-type]


def _dimension(**overrides: object) -> TaskObjective:
    payload: dict[str, object] = {
        "task_id": "egfr_potency",
        "endpoint": "egfr_pic50",
        "metric": "predicted_pic50",
        "unit": "log10(mol/L)",
        "direction": "higher",
    }
    payload.update(overrides)
    return TaskObjective(**payload)  # type: ignore[arg-type]


# --------------------------------------------------------------------- units
def test_dimension_lookup_rejects_unknown_units():
    with pytest.raises(UnknownUnitError) as excinfo:
        dimension_of("furlongs/fortnight")
    assert excinfo.value.code == "unknown_unit"


def test_compatible_energy_units_share_a_dimension_but_stay_separate_values():
    require_same_dimension("kcal/mol", "kJ/mol")
    assert dimension_of("kcal/mol") == dimension_of("kJ/mol")
    # Same dimension is not permission to merge: the endpoint gate still decides.
    item = _item(
        "ev_1",
        "cmp_1",
        -8.5,
        endpoint="docking_vina",
        unit="kcal/mol",
        direction="lower",
        uncertainty_low=-9.5,
        uncertainty_high=-7.5,
    )
    assert item.unit == "kcal/mol"
    assert EvidenceLedger().gate(item, _dimension()).eligible is False


def test_incomparable_units_raise():
    with pytest.raises(UnitMismatchError) as excinfo:
        require_same_dimension("kcal/mol", "log10(mol/L)")
    assert excinfo.value.code == "unit_mismatch"


# ---------------------------------------------------------------- validation
def test_value_must_be_finite():
    with pytest.raises(EvidenceError):
        _item("ev_nan", "cmp_1", float("nan"))


def test_value_outside_its_own_interval_is_rejected():
    with pytest.raises(EvidenceError) as excinfo:
        _item("ev_iv", "cmp_1", 9.0, uncertainty_low=4.0, uncertainty_high=6.0)
    assert "outside its own interval" in excinfo.value.message


def test_uncertainty_kind_requires_bounds_and_bounds_require_a_kind():
    with pytest.raises(EvidenceError):
        EvidenceItem(
            evidence_id="ev_a",
            candidate_id="cmp_1",
            endpoint="egfr_pic50",
            value=5.0,
            unit="log10(mol/L)",
            direction="higher",
            method="m",
            engine="e",
            engine_version="1",
            uncertainty_kind="conformal",
        )
    with pytest.raises(EvidenceError):
        EvidenceItem(
            evidence_id="ev_b",
            candidate_id="cmp_1",
            endpoint="egfr_pic50",
            value=5.0,
            unit="log10(mol/L)",
            direction="higher",
            method="m",
            engine="e",
            engine_version="1",
            uncertainty_low=4.0,
            uncertainty_high=6.0,
        )


def test_evidence_must_name_an_endpoint():
    with pytest.raises(EvidenceError):
        _item("ev_endpoint", "cmp_1", 5.0, endpoint="")


def test_evidence_ids_are_immutable():
    ledger = EvidenceLedger()
    ledger.add(_item("ev_1", "cmp_1", 5.0))
    with pytest.raises(EvidenceError):
        ledger.add(_item("ev_1", "cmp_1", 5.5))


# ------------------------------------------------------------- objective vector
def test_objective_vector_rejects_mixed_tasks_and_duplicate_endpoints():
    with pytest.raises(EvidenceError):
        ObjectiveVector(
            task_id="egfr_potency",
            dimensions=(_dimension(), _dimension(task_id="other_task")),
        )
    with pytest.raises(EvidenceError):
        ObjectiveVector(task_id="egfr_potency", dimensions=(_dimension(), _dimension()))


def test_objective_vector_has_no_scalar_collapse():
    vector = ObjectiveVector(task_id="egfr_potency", dimensions=(_dimension(),))
    assert not any(name in dir(vector) for name in ("composite", "score", "total", "combine", "summarise", "summarize"))


# ---------------------------------------------------------------------- gates
def test_calibrated_in_domain_validated_evidence_is_eligible():
    decision = EvidenceLedger().gate(_item("ev_1", "cmp_1", 5.0), _dimension())
    assert decision == GateDecision(eligible=True, reasons=())


@pytest.mark.parametrize(
    ("overrides", "reason_prefix"),
    [
        ({"status": "exploratory"}, "exploratory"),
        ({"status": "blocked"}, "blocked"),
        ({"calibration_id": None}, "not_calibrated"),
        ({"uncertainty_kind": "heuristic"}, "not_calibrated"),
        ({"applicability_domain": "out_of_domain"}, "applicability_domain"),
        ({"applicability_domain": "unknown"}, "applicability_domain"),
        ({"unit": "dimensionless"}, "unit_mismatch"),
        ({"direction": "lower"}, "direction_mismatch"),
        ({"endpoint": "solubility_logs"}, "endpoint_mismatch"),
    ],
)
def test_gate_denies_unearned_evidence(overrides: dict[str, object], reason_prefix: str):
    item = _item("ev_bad", "cmp_1", 5.0, **overrides)
    decision = EvidenceLedger().gate(item, _dimension())
    assert decision.eligible is False
    assert any(reason.startswith(reason_prefix) for reason in decision.reasons), decision.reasons


def test_heuristic_uncertainty_is_not_a_calibrated_interval():
    item = _item("ev_h", "cmp_1", 5.0, uncertainty_kind="heuristic")
    assert item.calibrated is False
    assert EvidenceLedger().gate(item, _dimension()).eligible is False


# ------------------------------------------------------------------- frontier
def test_frontier_uses_only_validated_evidence():
    ledger = EvidenceLedger()
    ledger.add(_item("ev_a", "cmp_a", 5.0))
    ledger.add(_item("ev_b", "cmp_b", 6.0))
    ledger.add(_item("ev_c", "cmp_c", 9.0, status="exploratory"))  # best number, unearned
    front = ledger.frontier(ObjectiveVector(task_id="egfr_potency", dimensions=(_dimension(),)))
    assert "cmp_c" not in front
    assert front == ("cmp_b",)


def test_frontier_omits_candidates_with_a_missing_dimension():
    potency = _dimension()
    selectivity = _dimension(endpoint="egfr_her2_selectivity", metric="ratio", unit="dimensionless")
    vector = ObjectiveVector(task_id="egfr_potency", dimensions=(potency, selectivity))

    ledger = EvidenceLedger()
    ledger.add(_item("ev_p1", "cmp_a", 6.0))
    ledger.add(_item("ev_s1", "cmp_a", 2.0, endpoint="egfr_her2_selectivity", unit="dimensionless"))
    ledger.add(_item("ev_p2", "cmp_b", 7.0))  # no selectivity value

    table = ledger.objective_table(vector)
    assert set(table) == {"cmp_a"}
    assert table["cmp_a"] == {"egfr_pic50": 6.0, "egfr_her2_selectivity": 2.0}


def test_ambiguous_validated_values_are_not_averaged():
    ledger = EvidenceLedger()
    ledger.add(_item("ev_1", "cmp_a", 5.0))
    ledger.add(_item("ev_2", "cmp_a", 7.0, method="other-model"))
    assert ledger.objective_table(ObjectiveVector(task_id="egfr_potency", dimensions=(_dimension(),))) == {}


# ------------------------------------------------------------------- failures
def test_failures_are_preserved_not_converted_to_zero():
    ledger = EvidenceLedger()
    failure = EvaluationFailure(
        candidate_id="cmp_a",
        endpoint="egfr_pic50",
        engine="chemprop",
        engine_version="2.1.0",
        error_code="invalid_input",
        message="Unparseable SMILES",
    )
    ledger.add_failure(failure)
    assert len(ledger) == 0
    assert ledger.failures == (failure,)
    assert ledger.objective_table(ObjectiveVector(task_id="egfr_potency", dimensions=(_dimension(),))) == {}


def test_ledger_digest_is_stable_and_content_addressed():
    first = EvidenceLedger()
    second = EvidenceLedger()
    for ledger in (first, second):
        ledger.add(_item("ev_b", "cmp_b", 6.0))
        ledger.add(_item("ev_a", "cmp_a", 5.0))
    assert first.digest() == second.digest()
    second.add(_item("ev_c", "cmp_c", 7.0))
    assert first.digest() != second.digest()


def test_evidence_item_round_trips_through_dict():
    item = _item("ev_1", "cmp_1", 5.0)
    assert item.as_dict()["evidence_id"] == "ev_1"
    assert item.as_dict()["calibration_id"] == "cal_2026_11_01"


def test_validation_error_is_the_public_error_family():
    assert issubclass(EvidenceError, ValidationError)
