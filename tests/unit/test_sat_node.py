"""The `select.sat` node: coverage selection, infeasibility and edge cases."""

from __future__ import annotations

import pytest

from hcs_discovery.core.errors import ValidationError
from hcs_discovery.workflow.nodes import SatSelectConfig, _run_sat_select
from hcs_discovery.workflow.table import IDENTITY_COLUMNS, Column, Table
from tests.unit.test_workflow import DummyContext


def _table(rows: list[tuple[str, str]]) -> Table:
    return Table(
        rows=[{"compound_id": compound, "band": band} for compound, band in rows],
        columns=[*IDENTITY_COLUMNS, Column("band", "Band", "string")],
    )


def test_selects_at_most_k_and_covers_every_group():
    table = _table([("a", "low"), ("b", "low"), ("c", "mid"), ("d", "mid"), ("e", "high")])
    config = SatSelectConfig(group_column="band", k_max=3)
    result = _run_sat_select(table, config, DummyContext())

    selected = [row["compound_id"] for row in result.rows if row["sat_selected"]]
    assert len(selected) <= 3
    covered = {row["band"] for row in result.rows if row["sat_selected"]}
    assert covered == {"low", "mid", "high"}
    assert all(row["sat_reason"] in {"selected", "not selected within the budget"} for row in result.rows)
    assert len(result.rows) == len(table.rows), "the node must not drop rows"


def test_infeasible_budget_fails_by_default():
    table = _table([("a", "low"), ("b", "mid"), ("c", "high")])
    with pytest.raises(ValidationError) as excinfo:
        _run_sat_select(table, SatSelectConfig(group_column="band", k_max=2), DummyContext())
    assert excinfo.value.code == "validation_error"
    assert excinfo.value.details["groups"] == 3


def test_infeasible_budget_can_be_marked_instead():
    table = _table([("a", "low"), ("b", "mid"), ("c", "high")])
    config = SatSelectConfig(group_column="band", k_max=2, on_infeasible="mark")
    result = _run_sat_select(table, config, DummyContext())
    assert not any(row["sat_selected"] for row in result.rows)
    assert all(row["sat_reason"] for row in result.rows)


def test_rows_without_a_group_are_never_selected():
    table = _table([("a", "low"), ("b", ""), ("c", "high")])
    result = _run_sat_select(table, SatSelectConfig(group_column="band", k_max=2), DummyContext())
    by_id = {row["compound_id"]: row for row in result.rows}
    assert by_id["b"]["sat_selected"] is False
    assert by_id["b"]["sat_reason"] == "no group value"


def test_empty_group_column_is_a_validation_error():
    table = _table([("a", ""), ("b", "")])
    with pytest.raises(ValidationError):
        _run_sat_select(table, SatSelectConfig(group_column="band", k_max=2), DummyContext())


def test_min_per_group_is_respected():
    table = _table([("a", "only"), ("b", "only"), ("c", "only")])
    result = _run_sat_select(
        table,
        SatSelectConfig(group_column="band", k_max=3, min_per_group=2),
        DummyContext(),
    )
    assert sum(1 for row in result.rows if row["sat_selected"]) >= 2


def test_missing_columns_are_reported():
    table = Table(rows=[{"compound_id": "a"}], columns=list(IDENTITY_COLUMNS))
    with pytest.raises(ValidationError):
        _run_sat_select(table, SatSelectConfig(group_column="band", k_max=1), DummyContext())


def test_selection_is_deterministic():
    rows = [("a", "low"), ("b", "low"), ("c", "mid"), ("d", "high")]
    first = _run_sat_select(_table(rows), SatSelectConfig(group_column="band", k_max=3), DummyContext())
    second = _run_sat_select(_table(rows), SatSelectConfig(group_column="band", k_max=3), DummyContext())
    assert [row["sat_selected"] for row in first.rows] == [row["sat_selected"] for row in second.rows]
