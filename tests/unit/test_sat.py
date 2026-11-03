"""SAT solver: differential tests against brute force, UNSAT cases and encodings."""

from __future__ import annotations

import itertools
import random

import pytest

from hcs_discovery.core.errors import ValidationError
from hcs_discovery.sat import Cnf, SolveResult, at_most_k, solve


def brute_force(clauses: list[list[int]], variables: int) -> bool:
    for bits in itertools.product([False, True], repeat=variables):
        if all(
            any(bits[abs(literal) - 1] if literal > 0 else not bits[abs(literal) - 1] for literal in clause)
            for clause in clauses
        ):
            return True
    return False


def random_3sat(rng: random.Random, variables: int, clause_count: int) -> list[list[int]]:
    clauses = []
    for _ in range(clause_count):
        picked = rng.sample(range(1, variables + 1), 3)
        clauses.append([variable if rng.random() < 0.5 else -variable for variable in picked])
    return clauses


@pytest.mark.parametrize("seed", range(40))
def test_matches_brute_force_on_random_3sat(seed):
    rng = random.Random(seed)
    variables = rng.randint(3, 7)
    clauses = random_3sat(rng, variables, rng.randint(1, 4 * variables))
    expected = brute_force(clauses, variables)
    result = solve(clauses, variables=variables)
    assert result.satisfiable is expected
    if expected:
        model = result.model
        assert all(
            any(model[abs(literal)] if literal > 0 else not model[abs(literal)] for literal in clause)
            for clause in clauses
        )


def test_model_is_total_and_consistent():
    result = solve([[1, 2]], variables=3)
    assert result.satisfiable is True
    assert set(result.model) == {1, 2, 3}
    assert all(isinstance(value, bool) for value in result.model.values())
    assert result.model[1] or result.model[2]


def test_unit_propagation_chain():
    result = solve([[1], [-1, 2], [-2, 3], [-3]])
    assert result.satisfiable is False


def test_empty_formula_is_satisfiable():
    result = solve([], variables=0)
    assert result.satisfiable is True and result.model == {}


def test_empty_clause_is_unsatisfiable():
    result = solve([[]], variables=2)
    assert result.satisfiable is False


def test_tautologies_and_duplicates_are_normalised():
    result = solve([[1, -1], [2, 2], [2]], variables=2)
    assert result.satisfiable is True
    assert result.model[2] is True


def test_invalid_literals_are_rejected():
    with pytest.raises(ValidationError):
        solve([[0]])
    with pytest.raises(ValidationError):
        solve([["x"]])  # type: ignore[list-item]
    with pytest.raises(ValidationError):
        solve([[5]], variables=4)


def pigeonhole(pigeons: int, holes: int) -> tuple[list[list[int]], int]:
    """Every pigeon in some hole, no hole holds two pigeons."""
    var = lambda pigeon, hole: pigeon * holes + hole + 1  # noqa: E731
    clauses = [[var(p, h) for h in range(holes)] for p in range(pigeons)]
    for h in range(holes):
        for p1 in range(pigeons):
            for p2 in range(p1 + 1, pigeons):
                clauses.append([-var(p1, h), -var(p2, h)])
    return clauses, pigeons * holes


@pytest.mark.parametrize(("pigeons", "holes"), [(3, 3), (4, 3), (5, 4), (6, 5)])
def test_pigeonhole(pigeons, holes):
    clauses, variables = pigeonhole(pigeons, holes)
    result = solve(clauses, variables=variables)
    assert result.satisfiable is (pigeons <= holes)


def test_solver_is_deterministic():
    clauses, variables = pigeonhole(4, 4)
    first = solve(clauses, variables=variables)
    second = solve(clauses, variables=variables)
    assert first.model == second.model
    assert first.decisions == second.decisions


def test_at_most_k_encoding_bounds_the_selection():
    cnf = Cnf()
    literals = [cnf.new_variable() for _ in range(5)]
    at_most_k(cnf, literals, 2)
    result = solve(cnf.clauses, variables=cnf.variables)
    assert result.satisfiable is True
    selected = [variable for variable in literals if result.model[variable]]
    assert len(selected) <= 2


def test_at_most_k_zero_and_unbounded():
    cnf = Cnf()
    literals = [cnf.new_variable() for _ in range(4)]
    at_most_k(cnf, literals, 0)
    result = solve(cnf.clauses, variables=cnf.variables)
    assert result.satisfiable and not any(result.model[variable] for variable in literals)

    other = Cnf()
    literals = [other.new_variable() for _ in range(4)]
    at_most_k(other, literals, 4)
    assert other.clauses == []


def test_at_least_one_combined_with_at_most_k():
    cnf = Cnf()
    literals = [cnf.new_variable() for _ in range(3)]
    at_most_k(cnf, literals, 1)
    cnf.add(*literals)  # at least one
    result = solve(cnf.clauses, variables=cnf.variables)
    assert result.satisfiable
    assert sum(1 for variable in literals if result.model[variable]) == 1


def test_result_carries_statistics():
    result = solve([[1, 2], [-1, 2], [1, -2]])
    assert isinstance(result, SolveResult)
    assert result.variables == 2 and result.clauses == 3
    assert result.decisions >= 0 and result.propagations >= 0


def test_select_subset_covers_every_group_within_budget():
    from hcs_discovery.sat import select_subset

    groups = {"low": ["a", "b"], "mid": ["c", "d"], "high": ["e"]}
    result = select_subset(groups, k_max=3)
    assert result.satisfiable is True
    assert len(result.selected) <= 3
    assert {"low", "mid", "high"} <= {name for name, members in groups.items() if set(members) & set(result.selected)}


def test_select_subset_refuses_an_impossible_budget():
    from hcs_discovery.sat import select_subset

    groups = {"a": ["x"], "b": ["y"], "c": ["z"]}
    result = select_subset(groups, k_max=2)
    assert result.satisfiable is False
    assert result.reason == "constraints are unsatisfiable"


def test_select_subset_reports_an_empty_group():
    from hcs_discovery.sat import select_subset

    result = select_subset({"a": ["x"], "empty": []}, k_max=5)
    assert result.satisfiable is False
    assert "empty" in (result.reason or "")


def test_select_subset_min_per_group():
    from hcs_discovery.sat import select_subset

    groups = {"only": ["a", "b", "c"]}
    result = select_subset(groups, k_max=3, min_per_group=2)
    assert result.satisfiable is True
    assert len(set(result.selected) & {"a", "b", "c"}) >= 2
