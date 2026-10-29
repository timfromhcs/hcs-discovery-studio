"""Property-based invariants for Pareto sorting, ranking and key-based joins."""

from __future__ import annotations

import math
import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from hcs_discovery.core.errors import ValidationError
from hcs_discovery.workflow.nodes import (
    ObjectiveConfig,
    RankConfig,
    _dominates,
    _run_rank,
    fast_nondominated_sort,
)
from hcs_discovery.workflow.schema import validate_workflow
from hcs_discovery.workflow.table import Column, Table
from tests.unit.test_workflow import DummyContext

# Small integer grids produce many exact ties and dominance chains.
values = st.integers(min_value=0, max_value=4).map(float)
vectors = st.lists(st.lists(values, min_size=2, max_size=2), min_size=0, max_size=14)


def _reference_fronts(vecs: list[list[float]]) -> list[set[int]]:
    """Fronts by definition: repeatedly peel off the non-dominated remainder."""
    remaining = set(range(len(vecs)))
    fronts = []
    while remaining:
        front = {p for p in remaining if not any(_dominates(vecs[q], vecs[p]) for q in remaining if q != p)}
        fronts.append(front)
        remaining -= front
    return fronts


@settings(max_examples=200, deadline=None)
@given(vectors)
def test_nondominated_sort_matches_the_definition(vecs):
    fronts = fast_nondominated_sort(list(range(len(vecs))), vecs, max_fronts=len(vecs) + 1)
    assert [set(front) for front in fronts] == _reference_fronts(vecs)


@settings(max_examples=150, deadline=None)
@given(vectors, st.integers(min_value=1, max_value=4))
def test_front_limit_truncates_but_never_reorders(vecs, limit):
    fronts = fast_nondominated_sort(list(range(len(vecs))), vecs, max_fronts=limit)
    assert [set(front) for front in fronts] == _reference_fronts(vecs)[:limit]


@settings(max_examples=150, deadline=None)
@given(vectors, st.randoms(use_true_random=False))
def test_front_membership_is_permutation_invariant(vecs, rnd):
    ids = list(range(len(vecs)))
    shuffled = ids[:]
    rnd.shuffle(shuffled)
    base = fast_nondominated_sort(ids, vecs, max_fronts=20)
    permuted = fast_nondominated_sort(shuffled, [vecs[i] for i in shuffled], max_fronts=20)
    assert [set(f) for f in base] == [set(f) for f in permuted]


@settings(max_examples=150, deadline=None)
@given(vectors)
def test_identical_vectors_share_a_front(vecs):
    fronts = fast_nondominated_sort(list(range(len(vecs))), vecs, max_fronts=20)
    front_of = {member: n for n, front in enumerate(fronts) for member in front}
    for i, a in enumerate(vecs):
        for j, b in enumerate(vecs):
            if a == b:
                assert front_of[i] == front_of[j]


def _rank_table(rows: list[dict[str, float | None]]) -> Table:
    return Table(
        rows=[{"compound_id": f"c{i}", **row} for i, row in enumerate(rows)],
        columns=[
            Column("compound_id", "ID", "string"),
            Column("a", "A", "number"),
            Column("b", "B", "number"),
            Column("c", "C", "number"),
        ],
    )


optional = st.one_of(st.none(), values)
rank_rows = st.lists(st.fixed_dictionaries({"a": optional, "b": optional, "c": optional}), min_size=1, max_size=12)


@settings(max_examples=120, deadline=None)
@given(rank_rows)
def test_rank_output_invariants(rows):
    config = RankConfig(
        objectives=[
            ObjectiveConfig(column="a", direction="higher", weight=2.0),
            ObjectiveConfig(column="b", direction="lower", weight=1.0),
            ObjectiveConfig(column="c", direction="constraint", target_max=2.0),
        ]
    )
    result = _run_rank(_rank_table(rows), config, DummyContext())
    out = result.rows
    assert sorted(row["rank"] for row in out) == list(range(1, len(out) + 1))
    for row in out:
        score = row["composite_score"]
        if row["a"] is None or row["b"] is None:
            assert score is None, "missing objective values must not become a score"
        else:
            assert 0.0 <= score <= 1.0
        eligible = row["c"] is not None and row["c"] <= 2.0
        assert row["constraint_pass"] is eligible
        if not eligible or row["a"] is None or row["b"] is None:
            assert row["pareto_rank"] is None
    eligible_ranks = [row["rank"] for row in out if row["constraint_pass"]]
    ineligible_ranks = [row["rank"] for row in out if not row["constraint_pass"]]
    if eligible_ranks and ineligible_ranks:
        assert max(eligible_ranks) < min(ineligible_ranks)


@settings(max_examples=80, deadline=None)
@given(rank_rows)
def test_constraint_column_does_not_change_scores_or_fronts_of_eligible_rows(rows):
    scored = [ObjectiveConfig(column="a", direction="higher"), ObjectiveConfig(column="b", direction="lower")]
    with_constraint = RankConfig(
        objectives=[*scored, ObjectiveConfig(column="c", direction="constraint", target_min=0)]
    )
    eligible = [row for row in rows if row["c"] is not None]
    if not eligible:
        return
    gated = {r["compound_id"]: r for r in _run_rank(_rank_table(eligible), with_constraint, DummyContext()).rows}
    plain = {
        r["compound_id"]: r
        for r in _run_rank(_rank_table(eligible), RankConfig(objectives=scored), DummyContext()).rows
    }
    for key, row in plain.items():
        assert gated[key]["composite_score"] == row["composite_score"]
        assert gated[key]["pareto_rank"] == row["pareto_rank"]


@pytest.mark.parametrize(("alias", "canonical"), [("maximize", "higher"), ("minimize", "lower")])
def test_direction_aliases_rank_identically(alias, canonical):
    rng = random.Random(7)
    rows = [{"a": float(rng.randint(0, 9)), "b": float(rng.randint(0, 9)), "c": 0.0} for _ in range(10)]

    def run(direction):
        config = RankConfig(objectives=[ObjectiveConfig(column="a", direction=direction), ObjectiveConfig(column="b")])
        return [
            (r["composite_score"], r["pareto_rank"], r["rank"])
            for r in _run_rank(_rank_table(rows), config, DummyContext()).rows
        ]

    assert run(alias) == run(canonical)


def test_zero_weight_objective_neither_scores_nor_enters_pareto_unless_requested():
    rows = [{"a": 1.0, "b": 5.0, "c": 0.0}, {"a": 2.0, "b": 1.0, "c": 0.0}, {"a": 3.0, "b": 3.0, "c": 0.0}]
    only_a = RankConfig(objectives=[ObjectiveConfig(column="a")])
    with_zero_b = RankConfig(objectives=[ObjectiveConfig(column="a"), ObjectiveConfig(column="b", weight=0.0)])
    base = _run_rank(_rank_table(rows), only_a, DummyContext()).rows
    zero = _run_rank(_rank_table(rows), with_zero_b, DummyContext()).rows
    assert [r["composite_score"] for r in base] == [r["composite_score"] for r in zero]
    assert [r["pareto_rank"] for r in base] == [r["pareto_rank"] for r in zero]

    in_pareto = RankConfig(
        objectives=[
            ObjectiveConfig(column="a"),
            ObjectiveConfig(column="b", direction="lower", weight=0.0, participates_in_pareto=True),
        ]
    )
    pareto = _run_rank(_rank_table(rows), in_pareto, DummyContext()).rows
    assert [r["composite_score"] for r in pareto] == [r["composite_score"] for r in base]
    # (a up, b down): (1, 5) is dominated by (3, 3); (2, 1) and (3, 3) trade off.
    assert [r["pareto_rank"] for r in pareto] == [2, 1, 1]


def test_composite_score_is_dataset_relative():
    """Documented limitation: adding a row changes the scores of existing rows."""
    config = RankConfig(objectives=[ObjectiveConfig(column="a")])
    rows = [{"a": 1.0, "b": 0.0, "c": 0.0}, {"a": 2.0, "b": 0.0, "c": 0.0}]
    before = _run_rank(_rank_table(rows), config, DummyContext()).rows
    after = _run_rank(_rank_table([*rows, {"a": 3.0, "b": 0.0, "c": 0.0}]), config, DummyContext()).rows
    assert before[1]["composite_score"] == 1.0
    assert math.isclose(after[1]["composite_score"], 0.5)


# --------------------------------------------------------------------------- joins
keys = st.one_of(st.none(), st.sampled_from(["a", "b", "c", "d", "e"]))


def _left(keys_):
    return Table(
        rows=[{"id": k, "value": float(i)} for i, k in enumerate(keys_)],
        columns=[Column("id", "ID", "string"), Column("value", "Value", "number")],
    )


def _right(keys_):
    return Table(
        rows=[{"id": k, "score": float(100 + i)} for i, k in enumerate(keys_)],
        columns=[Column("id", "ID", "string"), Column("score", "Score", "number")],
    )


right_keys = st.lists(keys, max_size=6).filter(lambda ks: len([k for k in ks if k]) == len({k for k in ks if k}))


@settings(max_examples=150, deadline=None)
@given(st.lists(keys, max_size=8), right_keys)
def test_join_matches_by_key_and_never_drops_or_duplicates_rows(left_keys, rkeys):
    left, right = _left(left_keys), _right(rkeys)
    score_by_key = {row["id"]: row["score"] for row in right.rows if row["id"] is not None}

    joined = left.join(right, how="left")
    assert [(r["id"], r["value"]) for r in joined.rows] == [(r["id"], r["value"]) for r in left.rows]
    assert [r["score"] for r in joined.rows] == [score_by_key.get(r["id"]) for r in left.rows]

    inner = left.join(right, how="inner")
    assert [r["value"] for r in inner.rows] == [r["value"] for r in left.rows if r["id"] in score_by_key]

    outer = left.join(right, how="outer")
    assert outer.rows[: len(left.rows)] == joined.rows
    left_ids = {r["id"] for r in left.rows} - {None}
    unmatched = [r["score"] for r in right.rows if r["id"] is None or r["id"] not in left_ids]
    appended = outer.rows[len(left.rows) :]
    assert sorted(r["score"] for r in appended) == sorted(unmatched), "unmatched right rows appear exactly once"
    assert all(r["value"] is None for r in appended)


def test_join_node_with_a_single_input_is_rejected_before_queueing():
    spec = {
        "schema_version": 1,
        "name": "join with one input",
        "nodes": [
            {"id": "desc", "type": "chem.descriptors", "config": {}},
            {"id": "merge", "type": "table.join", "config": {}},
        ],
        "edges": [{"source": "desc", "target": "merge"}],
    }
    with pytest.raises(ValidationError) as excinfo:
        validate_workflow(spec)
    assert "join_requires_two_inputs" in {issue["code"] for issue in excinfo.value.details["issues"]}
