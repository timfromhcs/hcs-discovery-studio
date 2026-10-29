"""Workflow validation, table semantics, filters, ranking and cache keys."""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError as PydanticValidationError

from hcs_discovery.core.errors import ValidationError
from hcs_discovery.workflow.cache import cache_key
from hcs_discovery.workflow.nodes import (
    FilterConfig,
    RankConfig,
    SimilarityConfig,
    _run_filters,
    _run_rank,
)
from hcs_discovery.workflow.registry import NodeContext, default_registry
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


def test_pareto_permutation_invariance_and_dominance():
    import random

    from hcs_discovery.workflow.nodes import ObjectiveConfig, RankConfig, _run_rank

    # Create 8 compounds with known dominance relations
    # c1 dominates c2, c3 is a trade-off, c4 is dominated by c3, etc.
    raw_data = [
        {"compound_id": "c1", "smiles": "C", "mw": 200.0, "logp": 1.0},  # Dominates c2
        {"compound_id": "c2", "smiles": "CC", "mw": 250.0, "logp": 1.5},
        {"compound_id": "c3", "smiles": "CCC", "mw": 150.0, "logp": 2.5},  # Trade-off with c1
        {"compound_id": "c4", "smiles": "CCCC", "mw": 180.0, "logp": 3.0},  # Dominated by c3
        {"compound_id": "c5", "smiles": "CCCCC", "mw": 300.0, "logp": 0.5},  # Trade-off
        {"compound_id": "c6", "smiles": "CCCCCC", "mw": 350.0, "logp": 1.0},  # Dominated by c5
        {"compound_id": "c7", "smiles": "c1ccccc1", "mw": 100.0, "logp": 5.0},  # Trade-off
        {"compound_id": "c8", "smiles": "c1ccccc1C", "mw": 120.0, "logp": 5.5},  # Dominated by c7
    ]

    config = RankConfig(
        objectives=[
            ObjectiveConfig(column="mw", direction="lower", weight=1.0),
            ObjectiveConfig(column="logp", direction="lower", weight=1.0),
        ],
        pareto_front_limit=5,
    )

    base_table = Table(
        rows=[dict(r) for r in raw_data],
        columns=[
            Column("compound_id", "ID", "string"),
            Column("smiles", "SMILES", "string"),
            Column("mw", "MW", "number", direction="lower"),
            Column("logp", "LogP", "number", direction="lower"),
        ],
    )
    base_result = _run_rank(base_table, config, DummyContext())
    baseline_pareto = {r["compound_id"]: r["pareto_rank"] for r in base_result.rows}

    # Invariant 1: c1 must strictly dominate c2
    assert baseline_pareto["c1"] < baseline_pareto["c2"]
    assert baseline_pareto["c3"] < baseline_pareto["c4"]
    assert baseline_pareto["c5"] < baseline_pareto["c6"]
    assert baseline_pareto["c7"] < baseline_pareto["c8"]
    # Front 1 should contain non-dominated trade-offs: c1, c3, c5, c7
    assert baseline_pareto["c1"] == 1
    assert baseline_pareto["c3"] == 1
    assert baseline_pareto["c5"] == 1
    assert baseline_pareto["c7"] == 1

    # Invariant 2: 20 random permutations must yield IDENTICAL pareto_ranks for every compound
    rng = random.Random(42)
    for _ in range(20):
        shuffled_rows = [dict(r) for r in raw_data]
        rng.shuffle(shuffled_rows)
        shuffled_table = Table(rows=shuffled_rows, columns=list(base_table.columns))
        shuffled_result = _run_rank(shuffled_table, config, DummyContext())
        permuted_pareto = {r["compound_id"]: r["pareto_rank"] for r in shuffled_result.rows}
        assert permuted_pareto == baseline_pareto, "Pareto rank must be 100% permutation-invariant"


def test_pareto_identical_ties():
    from hcs_discovery.workflow.nodes import ObjectiveConfig, RankConfig, _run_rank

    table = Table(
        rows=[
            {"compound_id": "c1", "smiles": "C", "mw": 200.0, "logp": 1.0},
            {"compound_id": "c2", "smiles": "CC", "mw": 200.0, "logp": 1.0},  # Identical to c1
            {"compound_id": "c3", "smiles": "CCC", "mw": 300.0, "logp": 2.0},
        ],
        columns=[
            Column("compound_id", "ID", "string"),
            Column("smiles", "SMILES", "string"),
            Column("mw", "MW", "number"),
            Column("logp", "LogP", "number"),
        ],
    )
    config = RankConfig(
        objectives=[
            ObjectiveConfig(column="mw", direction="lower", weight=1.0),
            ObjectiveConfig(column="logp", direction="lower", weight=1.0),
        ]
    )
    res = _run_rank(table, config, DummyContext())
    by_id = {r["compound_id"]: r for r in res.rows}
    assert by_id["c1"]["pareto_rank"] == by_id["c2"]["pareto_rank"] == 1
    assert by_id["c3"]["pareto_rank"] == 2


def test_target_range_objective():
    import math

    from hcs_discovery.workflow.nodes import ObjectiveConfig, RankConfig, _run_rank

    table = Table(
        rows=[
            {"compound_id": "c1", "smiles": "C", "mw": 300.0},  # inside [200, 400] -> score 1.0
            {"compound_id": "c2", "smiles": "CC", "mw": 200.0},  # boundary -> score 1.0
            {"compound_id": "c3", "smiles": "CCC", "mw": 150.0},  # distance 50 with tol 100 -> score 0.5
            {"compound_id": "c4", "smiles": "CCCC", "mw": 500.0},  # distance 100 with tol 100 -> score 0.0
        ],
        columns=[
            Column("compound_id", "ID", "string"),
            Column("smiles", "SMILES", "string"),
            Column("mw", "MW", "number"),
        ],
    )
    config = RankConfig(
        objectives=[
            ObjectiveConfig(
                column="mw",
                direction="target_range",
                target_min=200.0,
                target_max=400.0,
                tolerance=100.0,
                weight=1.0,
            )
        ]
    )
    res = _run_rank(table, config, DummyContext())
    by_id = {r["compound_id"]: r for r in res.rows}
    assert math.isclose(by_id["c1"]["composite_score"], 1.0)
    assert math.isclose(by_id["c2"]["composite_score"], 1.0)
    assert math.isclose(by_id["c3"]["composite_score"], 0.5)
    assert math.isclose(by_id["c4"]["composite_score"], 0.0)


def test_rule_config_validation_and_missing_values():
    from pydantic import ValidationError as PydanticValidationError

    from hcs_discovery.workflow.nodes import RuleConfig, _run_filters

    # 1. Invalid non-numeric string for numeric op fails validation
    with pytest.raises(PydanticValidationError):
        RuleConfig(column="mw", op="le", value="not_a_number")

    with pytest.raises(PydanticValidationError):
        RuleConfig(column="mw", op="between", value=100.0, value2="bad")

    # 2. between with min > max normalizes automatically
    norm_rule = RuleConfig(column="mw", op="between", value=500.0, value2=100.0)
    assert norm_rule.value == 100.0
    assert norm_rule.value2 == 500.0

    # 3. Missing values do not pass numeric constraints
    table = Table(
        rows=[
            {"compound_id": "c1", "smiles": "C", "mw": None},
            {"compound_id": "c2", "smiles": "CC", "mw": 200.0},
        ],
        columns=[
            Column("compound_id", "ID", "string"),
            Column("smiles", "SMILES", "string"),
            Column("mw", "MW", "number"),
        ],
    )
    fconfig = FilterConfig(rules=[RuleConfig(column="mw", op="le", value=300.0)])
    filtered = _run_filters(table, fconfig, DummyContext())
    assert filtered.rows[0]["filter_pass"] is False
    assert filtered.rows[1]["filter_pass"] is True


@pytest.mark.parametrize("node_type", default_registry().types())
def test_every_registered_node_rejects_unknown_fields(node_type):
    definition = default_registry().get(node_type)
    with pytest.raises(PydanticValidationError) as excinfo:
        definition.config_model.model_validate({"unknown_field_for_contract_test": 1})
    assert any(error["type"] == "extra_forbidden" for error in excinfo.value.errors())


def _join_tables() -> tuple[Table, Table]:
    left = Table(
        rows=[{"id": "a", "value": 1.0}, {"id": "b", "value": 2.0}],
        columns=[Column("id", "ID", "string"), Column("value", "Value", "number")],
    )
    right = Table(
        rows=[{"id": "a", "score": 10.0}, {"id": "b", "score": 20.0}],
        columns=[Column("id", "ID", "string"), Column("score", "Score", "number")],
    )
    return left, right


def test_join_preserves_all_left_rows_and_matches_by_key():
    left, right = _join_tables()
    joined = left.join(right, key_column="id", how="left")
    assert [row["id"] for row in joined.rows] == ["a", "b"]
    assert [row["score"] for row in joined.rows] == [10.0, 20.0]


def test_join_rejects_duplicate_right_keys_instead_of_discarding_rows():
    left, _ = _join_tables()
    right = Table(
        rows=[
            {"id": "a", "score": 10.0},
            {"id": "a", "score": 11.0},
            {"id": "b", "score": 20.0},
        ],
        columns=[Column("id", "ID", "string"), Column("score", "Score", "number")],
    )
    for how in ("inner", "left", "outer"):
        with pytest.raises(ValidationError) as excinfo:
            left.join(right, key_column="id", how=how)  # type: ignore[arg-type]
        assert excinfo.value.details["duplicate_keys"] == ["a"]


def test_join_rejects_suffix_collision_instead_of_overwriting_columns():
    left = Table(
        rows=[{"id": "a", "value": 1.0, "value_right": 99.0}],
        columns=[
            Column("id", "ID", "string"),
            Column("value", "Value", "number"),
            Column("value_right", "Existing suffixed value", "number"),
        ],
    )
    right = Table(
        rows=[{"id": "a", "value": 2.0}],
        columns=[Column("id", "ID", "string"), Column("value", "Other value", "number")],
    )
    with pytest.raises(ValidationError) as excinfo:
        left.join(right, key_column="id")
    assert excinfo.value.details["column"] == "value"
    assert excinfo.value.details["suffix"] == "_right"


def test_constraint_objectives_gate_ranking_and_pareto_without_scoring():
    table = _table()
    constrained = RankConfig(
        objectives=[
            {"column": "mw", "direction": "lower", "weight": 1.0},
            {"column": "logp", "direction": "constraint", "target_max": 3.0},
        ]
    )
    result = _run_rank(table, constrained, DummyContext())
    by_id = {row["compound_id"]: row for row in result.rows}
    assert by_id["c1"]["constraint_pass"] is True
    assert by_id["c3"]["constraint_pass"] is False
    assert "logp: 8 > 3" in by_id["c3"]["constraint_reasons"]
    assert by_id["c3"]["pareto_rank"] is None
    assert by_id["c3"]["rank"] > by_id["c1"]["rank"]
    assert result.column("constraint_pass").type == "boolean"

    unconstrained = RankConfig(objectives=[{"column": "mw", "direction": "lower", "weight": 1.0}])
    baseline = _run_rank(_table(), unconstrained, DummyContext())
    baseline_by_id = {row["compound_id"]: row for row in baseline.rows}
    for compound_id, row in by_id.items():
        assert row["composite_score"] == baseline_by_id[compound_id]["composite_score"]


def test_constraint_objective_cannot_be_scored_or_enter_pareto():
    from hcs_discovery.workflow.nodes import ObjectiveConfig

    with pytest.raises(PydanticValidationError):
        ObjectiveConfig(column="logp", direction="constraint", target_max=3.0, weight=1.0)
    with pytest.raises(PydanticValidationError):
        ObjectiveConfig(
            column="logp",
            direction="constraint",
            target_max=3.0,
            participates_in_pareto=True,
        )
    objective = ObjectiveConfig(column="logp", direction="constraint", target_max=3.0)
    assert objective.weight == 0.0
    assert objective.participates_in_pareto is False
