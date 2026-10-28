"""Workflow validation, table semantics, filters, ranking and cache keys."""

from __future__ import annotations

import copy

import pytest

from hcs_discovery.core.errors import ValidationError
from hcs_discovery.workflow.cache import cache_key
from hcs_discovery.workflow.nodes import (
    FilterConfig,
    RankConfig,
    SimilarityConfig,
    _run_filters,
    _run_rank,
)
from hcs_discovery.workflow.registry import NodeContext
from hcs_discovery.workflow.schema import validate_workflow
from hcs_discovery.workflow.table import IDENTITY_COLUMNS, Column, Table


class DummyContext(NodeContext):
    def __init__(self) -> None:
        super().__init__(
            run_id="run_test",
            node_id="node",
            work_dir=__import__("pathlib").Path("."),
            emit=lambda *args, **kwargs: None,
            report_progress=lambda *_: None,
            check_cancel=lambda: None,
            write_artifact=lambda *args, **kwargs: {},
        )


def _table() -> Table:
    rows = [
        {"compound_id": "c1", "smiles": "CCO", "name": "ethanol", "mw": 46.0, "logp": -0.3},
        {"compound_id": "c2", "smiles": "c1ccccc1", "name": "benzene", "mw": 78.0, "logp": 2.1},
        {
            "compound_id": "c3",
            "smiles": "CCCCCCCCCCCCCCCC",
            "name": "alkane",
            "mw": 226.0,
            "logp": 8.0,
        },
    ]
    return Table(
        rows=rows,
        columns=[
            *IDENTITY_COLUMNS,
            Column("mw", "MW", "number", unit="g/mol", direction="lower"),
            Column("logp", "cLogP", "number", direction="lower"),
        ],
    )


def test_triage_template_is_valid(triage_definition):
    validated = validate_workflow(triage_definition)
    assert [node.id for node in validated.order] == ["descriptors", "filters", "ranking", "summary"]
    assert validated.content_hash == validate_workflow(triage_definition).content_hash


def test_hash_changes_when_config_changes(triage_definition):
    first = validate_workflow(triage_definition).content_hash
    changed = copy.deepcopy(triage_definition)
    changed["nodes"][0]["config"]["descriptors"] = [
        *changed["nodes"][0]["config"]["descriptors"],
        "fsp3",
    ]
    assert validate_workflow(changed).content_hash != first


def test_unknown_node_type_is_rejected(triage_definition):
    broken = copy.deepcopy(triage_definition)
    broken["nodes"][1]["type"] = "science:magic"
    with pytest.raises(ValidationError) as excinfo:
        validate_workflow(broken)
    assert excinfo.value.details["issues"][0]["code"] == "unknown_node_type"


def test_cycle_is_rejected(triage_definition):
    broken = copy.deepcopy(triage_definition)
    broken["edges"] = [
        {"source": "descriptors", "target": "filters"},
        {"source": "filters", "target": "ranking"},
        {"source": "ranking", "target": "summary"},
        {"source": "summary", "target": "descriptors"},
    ]
    with pytest.raises(ValidationError) as excinfo:
        validate_workflow(broken)
    codes = {issue["code"] for issue in excinfo.value.details["issues"]}
    assert "no_root" in codes


def test_disconnected_node_is_rejected(triage_definition):
    broken = copy.deepcopy(triage_definition)
    broken["nodes"].append({"id": "extra", "type": "chem.descriptors", "config": {"descriptors": ["mw"]}})
    with pytest.raises(ValidationError) as excinfo:
        validate_workflow(broken)
    codes = {issue["code"] for issue in excinfo.value.details["issues"]}
    assert "multiple_roots" in codes


def test_duplicate_node_id_is_rejected(triage_definition):
    broken = copy.deepcopy(triage_definition)
    broken["nodes"].append(copy.deepcopy(broken["nodes"][0]))
    with pytest.raises(ValidationError) as excinfo:
        validate_workflow(broken)
    assert any(issue["code"] == "duplicate_node" for issue in excinfo.value.details["issues"])


def test_missing_column_is_reported_before_queueing(triage_definition):
    broken = copy.deepcopy(triage_definition)
    broken["nodes"] = [
        *broken["nodes"][:1],
        {
            "id": "ranking",
            "type": "rank.pareto",
            "config": {"objectives": [{"column": "not_computed", "direction": "higher", "weight": 1.0}]},
        },
    ]
    broken["edges"] = [{"source": "descriptors", "target": "ranking"}]
    with pytest.raises(ValidationError) as excinfo:
        validate_workflow(broken)
    assert any(issue["code"] == "missing_column" for issue in excinfo.value.details["issues"])


def test_invalid_config_is_reported(triage_definition):
    broken = copy.deepcopy(triage_definition)
    broken["nodes"][0]["config"]["descriptors"] = ["made_up"]
    with pytest.raises(ValidationError) as excinfo:
        validate_workflow(broken)
    assert any(issue["code"] == "invalid_config" for issue in excinfo.value.details["issues"])


def test_multi_input_merge_is_explicitly_unsupported(triage_definition):
    broken = copy.deepcopy(triage_definition)
    broken["edges"].append({"source": "descriptors", "target": "summary"})
    with pytest.raises(ValidationError) as excinfo:
        validate_workflow(broken)
    assert any(issue["code"] == "multiple_inputs_unsupported" for issue in excinfo.value.details["issues"])


def test_empty_workflow_is_rejected():
    with pytest.raises(ValidationError):
        validate_workflow({"schema_version": 1, "name": "empty", "nodes": [], "edges": []})


def test_similarity_config_validates_query():
    with pytest.raises(ValueError):
        SimilarityConfig(query_smiles="not-a-smiles")


def test_filter_flags_and_preserves_rejected_rows():
    table = _table()
    config = FilterConfig(rules=[{"column": "mw", "op": "le", "value": 100}])
    result = _run_filters(table, config, DummyContext())
    assert len(result.rows) == 3
    assert [row["filter_pass"] for row in result.rows] == [True, True, False]
    assert "MW" in result.rows[2]["filter_reasons"]
    assert result.column("filter_pass").type == "boolean"


def test_filter_drop_mode_removes_rows():
    table = _table()
    config = FilterConfig(mode="drop", rules=[{"column": "mw", "op": "le", "value": 100}])
    result = _run_filters(table, config, DummyContext())
    assert len(result.rows) == 2


def test_filter_between_and_string_rules():
    table = _table()
    config = FilterConfig(
        rules=[
            {"column": "mw", "op": "between", "value": 40, "value2": 100},
            {"column": "name", "op": "ne", "value": "BENZENE"},
        ]
    )
    result = _run_filters(table, config, DummyContext())
    assert result.rows[0]["filter_pass"] is True
    assert result.rows[1]["filter_pass"] is False


def test_pareto_fronts_and_composite_scores():
    table = _table()
    config = RankConfig(
        objectives=[
            {"column": "mw", "direction": "lower", "weight": 1.0},
            {"column": "logp", "direction": "lower", "weight": 1.0},
        ]
    )
    result = _run_rank(table, config, DummyContext())
    by_id = {row["compound_id"]: row for row in result.rows}
    assert by_id["c1"]["pareto_rank"] == 1
    assert by_id["c3"]["pareto_rank"] is not None and by_id["c3"]["pareto_rank"] > 1
    assert by_id["c1"]["rank"] == 1
    assert 0.0 <= by_id["c1"]["composite_score"] <= 1.0
    assert result.column("composite_score").direction == "higher"


def test_rank_places_rejected_rows_last():
    table = _table()
    table.add_values(Column("filter_pass", "pass", "boolean"), [False, True, True])
    table.add_values(Column("filter_reasons", "why", "string"), ["bad", "", ""])
    config = RankConfig(objectives=[{"column": "mw", "direction": "lower", "weight": 1.0}])
    result = _run_rank(table, config, DummyContext())
    assert result.rows[0]["rank"] > result.rows[1]["rank"]
    assert result.rows[0]["pareto_rank"] is None
    assert result.rows[1]["pareto_rank"] is not None


def test_missing_objective_values_do_not_become_zero():
    table = _table()
    table.rows[0]["mw"] = None
    config = RankConfig(objectives=[{"column": "mw", "direction": "lower", "weight": 1.0}])
    result = _run_rank(table, config, DummyContext())
    assert result.rows[0]["composite_score"] is None
    assert result.rows[0]["rank"] == 3


def test_cache_key_sensitivity():
    base = dict(
        node_type="chem.descriptors",
        node_version="1.0.0",
        config={"descriptors": ["mw"]},
        input_hash="a" * 64,
        engine_versions={"rdkit": "2026.9.1"},
        implementation_hash="impl",
    )
    key = cache_key(**base)
    assert cache_key(**base) == key
    assert cache_key(**{**base, "config": {"descriptors": ["logp"]}}) != key
    assert cache_key(**{**base, "input_hash": "b" * 64}) != key
    assert cache_key(**{**base, "engine_versions": {"rdkit": "2025.1"}}) != key
    assert cache_key(**{**base, "implementation_hash": "other"}) != key
    assert cache_key(**{**base, "node_version": "1.0.1"}) != key


def test_table_hash_includes_row_order():
    first = _table()
    second = _table()
    assert first.content_hash() == second.content_hash()
    second.rows.reverse()
    assert first.content_hash() != second.content_hash()


def test_numeric_column_coerces_missing_and_booleans():
    table = _table()
    table.rows[0]["mw"] = True
    table.rows[1]["mw"] = None
    assert table.numeric("mw") == [None, None, 226.0]
