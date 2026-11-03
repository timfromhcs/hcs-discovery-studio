"""A small, dependency-free SAT solver used for constraint-based library selection.

Why this exists: selecting a subset of compounds that satisfies hard constraints
("cover every property bin at least once", "at most k compounds") is a SAT
problem, not a ranking problem. A ranking always returns something plausible; a
SAT solver can say **unsatisfiable**, which is the honest answer when the
constraints cannot all be met.

The implementation is DPLL with two-watched-literal unit propagation, pure
literal elimination at the root, a deterministic branching heuristic and
chronological backtracking. It is not a competitive CDCL solver and does not
pretend to be: the target size is library-scale selection (hundreds to a few
thousand clauses), where correctness and determinism matter more than the last
order of magnitude.

Contract:

- Literals are non-zero integers: ``x`` is variable ``x`` true, ``-x`` false.
  Variables are 1-based.
- ``solve`` returns :class:`SolveResult` with ``satisfiable``, the model (a dict
  ``variable -> bool``) and a deterministic decision count.
- Duplicate literals and tautologies (``x or not x``) are removed; an empty
  clause makes the formula unsatisfiable by definition.
- Two runs on the same input produce the same model.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from hcs_discovery.core.errors import ValidationError

__all__ = [
    "Cnf",
    "Selection",
    "SolveResult",
    "Unsatisfiable",
    "at_least_one",
    "at_most_k",
    "select_subset",
    "solve",
]

Clause = list[int]


class Unsatisfiable(Exception):
    """Raised by helpers that require a model (e.g. selection)."""


@dataclass(frozen=True)
class SolveResult:
    satisfiable: bool
    model: dict[int, bool] = field(default_factory=dict)
    decisions: int = 0
    propagations: int = 0
    variables: int = 0
    clauses: int = 0

    def value(self, variable: int) -> bool | None:
        return self.model.get(variable)


class Cnf:
    """Builder that normalises clauses and tracks the variable range."""

    def __init__(self) -> None:
        self.clauses: list[Clause] = []
        self._max_var = 0

    def add(self, *literals: int) -> Cnf:
        clause = _normalise(literals)
        for literal in clause:
            self._max_var = max(self._max_var, abs(literal))
        if clause or not literals:  # an explicitly empty clause is kept: it is UNSAT
            self.clauses.append(clause)
        return self

    def new_variable(self) -> int:
        self._max_var += 1
        return self._max_var

    @property
    def variables(self) -> int:
        return self._max_var

    def __len__(self) -> int:
        return len(self.clauses)


def _normalise(literals: Iterable[int]) -> Clause:
    seen: set[int] = set()
    out: Clause = []
    for literal in literals:
        if not isinstance(literal, int) or isinstance(literal, bool):
            raise ValidationError("SAT literals must be integers.", details={"literal": repr(literal)})
        if literal == 0:
            raise ValidationError("0 is not a literal; variables are 1-based.")
        if -literal in seen:
            return []  # tautology: always satisfiable, drop it
        if literal not in seen:
            seen.add(literal)
            out.append(literal)
    return out


def _drop_tautologies(clauses: Sequence[Sequence[int]]) -> tuple[list[Clause], int]:
    normalised: list[Clause] = []
    variables = 0
    for raw in clauses:
        clause = _normalise(raw)
        if not clause and raw:
            continue  # tautology
        normalised.append(clause)
        for literal in clause:
            variables = max(variables, abs(literal))
    return normalised, variables


def solve(clauses: Sequence[Sequence[int]], *, variables: int | None = None) -> SolveResult:
    """Solve a CNF in DPLL form. Deterministic for a given clause order."""
    normalised, detected = _drop_tautologies(clauses)
    if variables is None:
        variables = detected
    else:
        for clause in normalised:
            for literal in clause:
                if abs(literal) > variables:
                    raise ValidationError(
                        "A literal exceeds the declared variable count.",
                        details={"literal": literal, "variables": variables},
                    )
    if any(len(clause) == 0 for clause in normalised):
        return SolveResult(False, {}, 0, 0, variables, len(normalised))

    solver = _Dpll(normalised, variables)
    sat, model = solver.run()
    return SolveResult(
        satisfiable=sat,
        model=model if sat else {},
        decisions=solver.decisions,
        propagations=solver.propagations,
        variables=variables,
        clauses=len(normalised),
    )


class _Dpll:
    def __init__(self, clauses: list[Clause], variables: int) -> None:
        self.clauses = clauses
        self.n = variables
        self.assign: list[int] = [0] * (variables + 1)  # 0 unknown, 1 true, -1 false
        self.trail: list[int] = []
        self.trail_lim: list[int] = []
        self.qhead = 0
        self.watches: dict[int, list[int]] = defaultdict(list)
        self.decisions = 0
        self.propagations = 0
        self.unsat = False
        self._attach()

    # -- setup ------------------------------------------------------------
    def _attach(self) -> None:
        units: list[int] = []
        index = 0
        for clause in self.clauses:
            if len(clause) == 1:
                units.append(clause[0])
                continue
            self.watches[clause[0]].append(index)
            self.watches[clause[1]].append(index)
            index += 1
        self.clauses = [clause for clause in self.clauses if len(clause) > 1]
        for literal in units:
            if not self._enqueue(literal):
                self.unsat = True
                return

    # -- assignment -------------------------------------------------------
    def _literal_value(self, literal: int) -> int:
        value = self.assign[abs(literal)]
        return value if literal > 0 else -value

    def _enqueue(self, literal: int) -> bool:
        variable = abs(literal)
        wanted = 1 if literal > 0 else -1
        current = self.assign[variable]
        if current != 0:
            return current == wanted
        self.assign[variable] = wanted
        self.trail.append(literal)
        return True

    def _propagate(self) -> bool:
        while self.qhead < len(self.trail):
            false_literal = -self.trail[self.qhead]
            self.qhead += 1
            pending = self.watches.get(false_literal)
            if not pending:
                continue
            self.watches[false_literal] = []
            kept: list[int] = []
            conflict = False
            for position, clause_index in enumerate(pending):
                if conflict:
                    # Keep the watchers that were not processed yet: this clause list
                    # is rebuilt from `kept` below and unprocessed entries must survive.
                    kept.extend(pending[position:])
                    break
                clause = self.clauses[clause_index]
                # Put the false literal in position 1, so position 0 is the other watch.
                if clause[0] == false_literal:
                    clause[0], clause[1] = clause[1], clause[0]
                if self._literal_value(clause[0]) == 1:
                    kept.append(clause_index)
                    continue
                replacement = -1
                for slot in range(2, len(clause)):
                    if self._literal_value(clause[slot]) != -1:
                        replacement = slot
                        break
                if replacement >= 0:
                    clause[1], clause[replacement] = clause[replacement], clause[1]
                    self.watches[clause[1]].append(clause_index)
                    continue
                kept.append(clause_index)
                value = self._literal_value(clause[0])
                if value == -1:
                    conflict = True
                    continue
                self.propagations += 1
                if not self._enqueue(clause[0]):
                    conflict = True
            self.watches[false_literal].extend(kept)
            if conflict:
                self.qhead = len(self.trail)
                return False
        return True

    # -- search -----------------------------------------------------------
    def _undo_to(self, trail_mark: int, level_count: int) -> None:
        for literal in reversed(self.trail[trail_mark:]):
            self.assign[abs(literal)] = 0
        del self.trail[trail_mark:]
        del self.trail_lim[level_count:]
        self.qhead = len(self.trail)

    def _pick_variable(self) -> int:
        """Most frequent unassigned variable in still-unresolved clauses (deterministic)."""
        counts: Counter[int] = Counter()
        for clause in self.clauses:
            unresolved = True
            for literal in clause:
                if self._literal_value(literal) == 1:
                    unresolved = False
                    break
            if not unresolved:
                continue
            for literal in clause:
                if self.assign[abs(literal)] == 0:
                    counts[abs(literal)] += 1
        if not counts:
            return 0
        return min(counts, key=lambda variable: (-counts[variable], variable))

    def _all_assigned_satisfied(self) -> bool:
        return all(any(self._literal_value(literal) == 1 for literal in clause) for clause in self.clauses)

    def _try(self, literal: int, stack: list[tuple[int, bool, int, int]]) -> bool | None:
        """Push one phase as a decision. Returns True on success, None on immediate failure."""
        mark, level_count = len(self.trail), len(self.trail_lim)
        self.trail_lim.append(mark)
        if self._enqueue(literal) and self._propagate():
            stack.append((abs(literal), literal > 0, mark, level_count))
            return True
        self._undo_to(mark, level_count)
        return None

    def _backtrack(self, stack: list[tuple[int, bool, int, int]]) -> bool:
        """Undo decisions until one can be flipped; return False when exhausted."""
        while stack:
            variable, was_true, mark, level_count = stack.pop()
            self._undo_to(mark, level_count)
            if was_true and self._try(-variable, stack) is True:
                return True
        return False

    def _assign_pure_literals(self) -> None:
        """A variable that occurs in one polarity only can be fixed at the root level.

        Variables that are already assigned are skipped: the polarity summary is taken
        from the clauses that remain after unit clauses were consumed, so an assigned
        variable can look pure in the wrong direction.
        """
        positive: set[int] = set()
        negative: set[int] = set()
        for clause in self.clauses:
            for literal in clause:
                (positive if literal > 0 else negative).add(abs(literal))
        for variable in sorted(positive - negative):
            if self.assign[variable] == 0:
                self._enqueue(variable)
        for variable in sorted(negative - positive):
            if self.assign[variable] == 0:
                self._enqueue(-variable)

    def run(self) -> tuple[bool, dict[int, bool]]:
        if self.unsat:
            return False, {}
        self._assign_pure_literals()
        if self.unsat:
            return False, {}
        if not self._propagate():
            return False, {}
        stack: list[tuple[int, bool, int, int]] = []
        while True:
            variable = self._pick_variable()
            if variable == 0:
                if self._all_assigned_satisfied():
                    # A model assigns every declared variable; unassigned ones are
                    # irrelevant to satisfaction, so they get a deterministic False.
                    model = {v: self.assign[v] == 1 for v in range(1, self.n + 1)}
                    return True, model
                if not self._backtrack(stack):
                    return False, {}
                continue
            self.decisions += 1
            if self._try(variable, stack) is True:
                continue
            if self._try(-variable, stack) is True:
                continue
            if not self._backtrack(stack):
                return False, {}


# --------------------------------------------------------------------------- encodings
def at_least_one(literals: Sequence[int]) -> Clause:
    if not literals:
        raise ValidationError("at_least_one requires at least one literal.")
    return list(literals)


def at_most_k(cnf: Cnf, literals: Sequence[int], k: int) -> None:
    """Sinz sequential-counter encoding of ``sum(literals) <= k``.

    Adds ``n * k`` auxiliary variables; the encoding is propagation complete and,
    unlike the naive subset encoding, stays polynomial.
    """
    n = len(literals)
    if k < 0:
        cnf.add()
        return
    if k >= n:
        return
    if k == 0:
        for literal in literals:
            cnf.add(-literal)
        return
    # s[i][j] means "at least j of the first i literals are true" (1-based j).
    s = [[cnf.new_variable() for _ in range(k + 1)] for _ in range(n + 1)]
    for i in range(1, n + 1):
        cnf.add(-literals[i - 1], s[i][1])
        cnf.add(-s[i - 1][1], s[i][1])
        for j in range(2, k + 1):
            cnf.add(-literals[i - 1], -s[i - 1][j - 1], s[i][j])
            cnf.add(-s[i - 1][j], s[i][j])
        cnf.add(-literals[i - 1], -s[i - 1][k])


@dataclass(frozen=True)
class Selection:
    """Result of a constraint-based subset selection."""

    satisfiable: bool
    selected: tuple[str, ...]
    k_max: int
    stats: SolveResult
    reason: str | None = None


def select_subset(
    groups: Mapping[str, Sequence[str]],
    *,
    k_max: int,
    min_per_group: int = 1,
) -> Selection:
    """Choose at most ``k_max`` candidates covering every group at least ``min_per_group`` times.

    ``groups`` maps a bin name to the candidate ids it contains. The encoding is
    plain CNF: one variable per candidate, a Sinz sequential counter for the
    cardinality bound, and one counter per group for the minimum coverage. An
    unsatisfiable instance returns ``satisfiable=False`` with a reason instead of
    a best-effort selection.
    """
    if k_max < 0:
        raise ValidationError("k_max must not be negative.")
    if min_per_group < 0:
        raise ValidationError("min_per_group must not be negative.")
    ids = sorted({candidate for members in groups.values() for candidate in members})
    if not ids:
        return Selection(
            satisfiable=min_per_group == 0,
            selected=(),
            k_max=k_max,
            stats=SolveResult(False, {}, 0, 0, 0, 0),
            reason=None if min_per_group == 0 else "no candidates were supplied",
        )
    variable_of = {candidate: index + 1 for index, candidate in enumerate(ids)}
    cnf = Cnf()
    for _ in ids:
        cnf.new_variable()
    at_most_k(cnf, [variable_of[candidate] for candidate in ids], k_max)
    for name, members in sorted(groups.items()):
        literals = [variable_of[candidate] for candidate in members]
        if not literals:
            if min_per_group > 0:
                return Selection(
                    satisfiable=False,
                    selected=(),
                    k_max=k_max,
                    stats=SolveResult(False, {}, 0, 0, len(ids), len(cnf)),
                    reason=f"group '{name}' has no candidates",
                )
            continue
        if min_per_group == 0:
            continue
        if min_per_group == 1:
            cnf.add(*literals)
        elif min_per_group > len(literals):
            return Selection(
                satisfiable=False,
                selected=(),
                k_max=k_max,
                stats=SolveResult(False, {}, 0, 0, len(ids), len(cnf)),
                reason=f"group '{name}' has {len(literals)} candidates, fewer than {min_per_group}",
            )
        else:
            # at least t among n  <=>  at most n - t of the negations
            at_most_k(cnf, [-literal for literal in literals], len(literals) - min_per_group)
    stats = solve(cnf.clauses, variables=cnf.variables)
    if not stats.satisfiable:
        return Selection(False, (), k_max, stats, "constraints are unsatisfiable")
    selected = tuple(
        candidate for candidate in ids if stats.model.get(variable_of[candidate]) is True and candidate in ids
    )
    return Selection(True, selected, k_max, stats)
