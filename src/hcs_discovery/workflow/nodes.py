"""Built-in workflow nodes: descriptors, similarity, rule filters, Pareto ranking, summary."""

from __future__ import annotations

import html
import math
from datetime import UTC, datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from rdkit import Chem

from ..chemistry.descriptors import (
    DEFAULT_DESCRIPTORS,
    DESCRIPTORS,
    descriptor_columns,
    tanimoto_to_query,
)
from ..core.errors import ValidationError
from ..plugins.science.docking.vina import (
    VinaConfig,
    run_vina_docking,
    vina_docking_columns,
    vina_runtime_fingerprint,
)
from ..plugins.science.properties.adapter import (
    PropertyPredictorConfig,
    property_prediction_columns,
    run_property_prediction,
)
from ..plugins.science.properties.models import get_property_model
from .registry import NodeContext, NodeDefinition, NodeRegistry
from .table import FILTER_COLUMNS, Column, Table

NODE_VERSION = "1.0.0"


# --------------------------------------------------------------------------- descriptors
class DescriptorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    descriptors: list[str] = Field(default_factory=lambda: list(DEFAULT_DESCRIPTORS))

    @field_validator("descriptors")
    @classmethod
    def _known(cls, value: list[str]) -> list[str]:
        unknown = [key for key in value if key not in DESCRIPTORS]
        if unknown:
            raise ValueError(f"Unknown descriptor(s): {', '.join(unknown)}")
        if not value:
            raise ValueError("Select at least one descriptor.")
        return value


def _run_descriptors(table: Table, config: DescriptorConfig, ctx: NodeContext) -> Table:
    table.require(["smiles"])
    columns = descriptor_columns(config.descriptors)
    values: dict[str, list[float | None]] = {column.name: [] for column in columns}
    total = len(table.rows)
    failed = 0
    for index, row in enumerate(table.rows, start=1):
        mol = Chem.MolFromSmiles(row["smiles"])
        if mol is None:
            failed += 1
            for column in columns:
                values[column.name].append(None)
            continue
        for column in columns:
            spec = DESCRIPTORS[column.name]
            try:
                values[column.name].append(float(spec.fn(mol)))
            except (ValueError, TypeError, ZeroDivisionError, ArithmeticError, RuntimeError):
                values[column.name].append(None)
        if index % 250 == 0 or index == total:
            ctx.report_progress(index / total if total else None)
            ctx.check_cancel()
    result = table.copy()
    for column in columns:
        result.add_values(column, values[column.name])
    if failed:
        ctx.log(
            f"{failed} structure(s) could not be re-parsed; descriptors left empty.",
            level="warning",
        )
    ctx.report_progress(1.0)
    return result


# --------------------------------------------------------------------------- similarity
class SimilarityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    query_smiles: str
    column: str = Field(default="similarity_query", pattern=r"^[a-z][a-z0-9_]{0,47}$")
    radius: int = Field(default=2, ge=1, le=4)
    bits: int = Field(default=2048, ge=256, le=8192)
    metric: Literal["tanimoto"] = "tanimoto"

    @field_validator("query_smiles")
    @classmethod
    def _valid_query(cls, value: str) -> str:
        if Chem.MolFromSmiles(value) is None:
            raise ValueError("query_smiles is not a valid SMILES string")
        return value


def _run_similarity(table: Table, config: SimilarityConfig, ctx: NodeContext) -> Table:
    table.require(["smiles"])
    query = Chem.MolFromSmiles(config.query_smiles)
    if query is None:
        raise ValidationError("Similarity query SMILES is invalid.")
    column = Column(
        config.column,
        "Tanimoto similarity to query",
        "number",
        unit="similarity (0-1)",
        direction="higher",
        method=f"Morgan/ECFP r={config.radius} {config.bits} bits, Tanimoto",
        description="Fingerprint similarity to the configured query structure.",
    )
    values: list[float | None] = []
    total = len(table.rows)
    for index, row in enumerate(table.rows, start=1):
        mol = Chem.MolFromSmiles(row["smiles"])
        values.append(None if mol is None else tanimoto_to_query(mol, query, radius=config.radius, bits=config.bits))
        if index % 250 == 0 or index == total:
            ctx.report_progress(index / total if total else None)
            ctx.check_cancel()
    result = table.copy().add_values(column, values)
    ctx.report_progress(1.0)
    return result


# --------------------------------------------------------------------------- filters
Operator = Literal["le", "lt", "ge", "gt", "eq", "ne", "between"]


class RuleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    column: str
    op: Operator
    value: float | str | bool
    value2: float | None = None
    label: str | None = None

    @model_validator(mode="after")
    def _validate_rule(self) -> Self:
        if self.op in {"le", "lt", "ge", "gt"}:
            if isinstance(self.value, bool):
                raise ValueError(f"Numeric filter '{self.op}' requires a number, not boolean")
            try:
                numeric_val = float(self.value)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Numeric filter '{self.op}' requires a numeric value, got '{self.value}'") from exc
            if not math.isfinite(numeric_val):
                raise ValueError(f"Filter threshold for '{self.column}' must be a finite number.")
            self.value = numeric_val
            self.value2 = None
        elif self.op == "between":
            if self.value2 is None:
                raise ValueError(f"Rule on '{self.column}' uses 'between' without value2")
            if isinstance(self.value, bool) or isinstance(self.value2, bool):
                raise ValueError("'between' filter requires numeric bounds, not boolean")
            try:
                v1 = float(self.value)
                v2 = float(self.value2)
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    f"'between' filter requires numeric bounds, got '{self.value}' and '{self.value2}'"
                ) from exc
            if not math.isfinite(v1) or not math.isfinite(v2):
                raise ValueError(f"'between' bounds for '{self.column}' must be finite numbers.")
            self.value = min(v1, v2)
            self.value2 = max(v1, v2)
        elif self.op in {"eq", "ne"}:
            if not isinstance(self.value, (bool, str)):
                try:
                    num = float(self.value)
                    if not math.isfinite(num):
                        raise ValueError(f"Filter threshold for '{self.column}' must be finite.")
                    self.value = num
                except (ValueError, TypeError):
                    pass
        return self


class FilterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    rules: list[RuleConfig] = Field(min_length=1)
    mode: Literal["flag", "drop"] = "flag"

    @field_validator("rules")
    @classmethod
    def _between(cls, rules: list[RuleConfig]) -> list[RuleConfig]:
        for rule in rules:
            if rule.op == "between" and rule.value2 is None:
                raise ValueError(f"Rule on '{rule.column}' uses 'between' without value2")
        return rules


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if (math.isnan(number) or math.isinf(number)) else number


def _check(rule: RuleConfig, value: Any) -> bool:
    if value is None:
        return False
    number = _numeric(value)
    if rule.op in {"eq", "ne"} and not isinstance(rule.value, (int, float)):
        if isinstance(rule.value, bool):
            return (bool(value) == rule.value) if rule.op == "eq" else (bool(value) != rule.value)
        equal = str(value).strip().lower() == str(rule.value).strip().lower()
        return equal if rule.op == "eq" else not equal
    if number is None:
        return False
    threshold = float(rule.value)
    if rule.op == "le":
        return number <= threshold
    if rule.op == "lt":
        return number < threshold
    if rule.op == "ge":
        return number >= threshold
    if rule.op == "gt":
        return number > threshold
    if rule.op == "eq":
        return math.isclose(number, threshold, rel_tol=1e-9, abs_tol=1e-9)
    if rule.op == "ne":
        return not math.isclose(number, threshold, rel_tol=1e-9, abs_tol=1e-9)
    low = float(rule.value)
    high = float(rule.value2)  # type: ignore[arg-type]
    return low <= number <= high


def _rule_text(rule: RuleConfig, column_label: str) -> str:
    text = f"{column_label} {rule.op} {rule.value}"
    if rule.op == "between":
        text += f"..{rule.value2}"
    return rule.label or text


def _run_filters(table: Table, config: FilterConfig, ctx: NodeContext) -> Table:
    labels = {column.name: column.label for column in table.columns}
    for rule in config.rules:
        if not table.has_column(rule.column):
            raise ValidationError(
                f"Filter rule references missing column '{rule.column}'.",
                details={"columns": table.column_names},
            )
    pass_values: list[bool] = []
    reason_values: list[str] = []
    for index, row in enumerate(table.rows, start=1):
        failures = [
            _rule_text(rule, labels.get(rule.column, rule.column))
            for rule in config.rules
            if not _check(rule, row.get(rule.column))
        ]
        pass_values.append(not failures)
        reason_values.append("; ".join(failures))
        if index % 1000 == 0:
            ctx.check_cancel()
    result = table.copy()
    result.add_values(FILTER_COLUMNS[0], pass_values)
    result.add_values(FILTER_COLUMNS[1], reason_values)
    passed = sum(pass_values)
    ctx.log(f"{passed} of {len(pass_values)} record(s) passed {len(config.rules)} rule check(s).")
    if config.mode == "drop":
        dropped = len(pass_values) - passed
        result = Table(
            rows=[row for row, ok in zip(result.rows, pass_values, strict=True) if ok],
            columns=result.columns,
        )
        ctx.log(f"Dropped {dropped} record(s) after flagging (mode=drop).", level="warning")
    return result


# --------------------------------------------------------------------------- ranking
ObjectiveDirection = Literal[
    "higher",
    "lower",
    "maximize",
    "minimize",
    "target_range",
    "constraint",
    "informational",
]


class ObjectiveConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    column: str
    direction: ObjectiveDirection = "higher"
    weight: float = Field(default=1.0, ge=0.0, le=100.0)
    target_min: float | None = None
    target_max: float | None = None
    tolerance: float | None = None
    participates_in_pareto: bool | None = None

    @model_validator(mode="after")
    def _validate_objective(self) -> Self:
        if self.direction == "target_range":
            if self.target_min is None or self.target_max is None:
                raise ValueError(
                    f"Objective on '{self.column}' with direction 'target_range' requires target_min and target_max."
                )
            if not math.isfinite(self.target_min) or not math.isfinite(self.target_max):
                raise ValueError(f"target_min and target_max for '{self.column}' must be finite numbers.")
            if self.target_min > self.target_max:
                self.target_min, self.target_max = self.target_max, self.target_min
            if self.tolerance is not None and (not math.isfinite(self.tolerance) or self.tolerance < 0):
                raise ValueError(f"tolerance for '{self.column}' must be a non-negative finite number.")
        elif self.direction == "constraint":
            if self.target_min is None and self.target_max is None:
                raise ValueError(f"Constraint objective on '{self.column}' requires at least target_min or target_max.")
            if "weight" in self.model_fields_set and self.weight != 0:
                raise ValueError(
                    f"Constraint objective on '{self.column}' is an eligibility gate, not a scored objective; "
                    "remove the weight or set it to 0."
                )
            if self.participates_in_pareto:
                raise ValueError(
                    f"Constraint objective on '{self.column}' cannot participate in a Pareto front; "
                    "constraints gate eligibility instead."
                )
            self.weight = 0.0
            if self.participates_in_pareto is None:
                self.participates_in_pareto = False
        elif self.direction == "informational":
            self.weight = 0.0
            if self.participates_in_pareto is None:
                self.participates_in_pareto = False
        return self


class RankConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    objectives: list[ObjectiveConfig] = Field(min_length=1)
    pareto_front_limit: int = Field(default=10, ge=1, le=50)

    @field_validator("objectives")
    @classmethod
    def _weights(cls, objectives: list[ObjectiveConfig]) -> list[ObjectiveConfig]:
        active_weights = [obj.weight for obj in objectives if obj.direction != "informational"]
        has_pareto = any(
            (obj.participates_in_pareto is True)
            or (obj.participates_in_pareto is None and obj.weight > 0 and obj.direction != "informational")
            for obj in objectives
        )
        if sum(active_weights) <= 0 and not has_pareto:
            raise ValueError("At least one objective must have a positive weight or participate in Pareto ranking")
        return objectives


def _dominates(a: list[float], b: list[float], eps: float = 1e-12) -> bool:
    better_or_equal = all(x >= y - eps for x, y in zip(a, b, strict=True))
    strictly_better = any(x > y + eps for x, y in zip(a, b, strict=True))
    return better_or_equal and strictly_better


def fast_nondominated_sort(
    candidate_indices: list[int],
    vectors: list[list[float]],
    max_fronts: int = 10,
) -> list[list[int]]:
    """Deb et al. Fast Non-dominated Sorting algorithm (NSGA-II).

    Invariants:
    1. Permutation invariance: changing the order of candidate_indices does not alter front memberships.
    2. Dominance invariant: no member of front i can be dominated by any member of front >= i.
    3. Tie handling: identical vectors are assigned to the exact same front.
    """
    N = len(candidate_indices)
    if N == 0:
        return []

    S: list[list[int]] = [[] for _ in range(N)]
    n: list[int] = [0] * N
    first_front: list[int] = []

    for p in range(N):
        vec_p = vectors[p]
        for q in range(p + 1, N):
            vec_q = vectors[q]
            p_dom_q = _dominates(vec_p, vec_q)
            q_dom_p = _dominates(vec_q, vec_p)
            if p_dom_q:
                S[p].append(q)
                n[q] += 1
            elif q_dom_p:
                S[q].append(p)
                n[p] += 1
        if n[p] == 0:
            first_front.append(p)

    fronts: list[list[int]] = [first_front]
    i = 0
    while i < len(fronts) and fronts[i] and (i + 1) < max_fronts:
        next_front: list[int] = []
        for p in fronts[i]:
            for q in S[p]:
                n[q] -= 1
                if n[q] == 0:
                    next_front.append(q)
        if not next_front:
            break
        fronts.append(next_front)
        i += 1

    return [[candidate_indices[idx] for idx in front] for front in fronts if front]


def _run_rank(table: Table, config: RankConfig, ctx: NodeContext) -> Table:
    columns = {column.name: column for column in table.columns}
    for objective in config.objectives:
        if objective.column not in columns:
            raise ValidationError(
                f"Objective column '{objective.column}' is missing.",
                details={"columns": table.column_names},
            )
        column = columns[objective.column]
        if column.type != "number":
            raise ValidationError(f"Objective column '{objective.column}' is not numeric.")
        expected = column.direction
        if (
            expected in {"higher", "lower"}
            and expected != objective.direction
            and objective.direction in {"higher", "lower"}
        ):
            ctx.log(
                f"Objective '{objective.column}' uses direction '{objective.direction}' while the column "
                f"metadata says '{expected}'. The explicit objective wins.",
                level="warning",
            )

    raw = {objective.column: table.numeric(objective.column) for objective in config.objectives}
    total_rows = len(table.rows)

    constraint_objectives = [obj for obj in config.objectives if obj.direction == "constraint"]
    constraint_ok: list[bool] = [True] * total_rows
    constraint_reasons: list[str | None] = [None] * total_rows
    if constraint_objectives:
        for index in range(total_rows):
            reasons: list[str] = []
            for objective in constraint_objectives:
                value = raw[objective.column][index]
                if value is None:
                    reasons.append(f"{objective.column}: missing value")
                    continue
                if objective.target_min is not None and value < objective.target_min:
                    reasons.append(f"{objective.column}: {value:.6g} < {objective.target_min:.6g}")
                if objective.target_max is not None and value > objective.target_max:
                    reasons.append(f"{objective.column}: {value:.6g} > {objective.target_max:.6g}")
            constraint_ok[index] = not reasons
            constraint_reasons[index] = "; ".join(reasons) if reasons else None

    normalized: dict[str, list[float | None]] = {}
    for objective in config.objectives:
        values = [value for value in raw[objective.column] if value is not None]
        low = min(values) if values else None
        high = max(values) if values else None
        series: list[float | None] = []
        for value in raw[objective.column]:
            if value is None:
                series.append(None)
            elif objective.direction in {"higher", "maximize"}:
                if low is None or high is None or math.isclose(high, low):
                    series.append(0.5)
                else:
                    series.append((value - low) / (high - low))
            elif objective.direction in {"lower", "minimize"}:
                if low is None or high is None or math.isclose(high, low):
                    series.append(0.5)
                else:
                    series.append((high - value) / (high - low))
            elif objective.direction == "target_range":
                t_min = objective.target_min
                t_max = objective.target_max
                assert t_min is not None and t_max is not None
                if t_min <= value <= t_max:
                    series.append(1.0)
                else:
                    tol = (
                        objective.tolerance
                        if objective.tolerance and objective.tolerance > 0
                        else max(1.0, 0.5 * (t_max - t_min))
                    )
                    dist = (t_min - value) if value < t_min else (value - t_max)
                    series.append(max(0.0, 1.0 - dist / tol))
            elif objective.direction == "constraint":
                t_min = objective.target_min
                t_max = objective.target_max
                ok = True
                if t_min is not None and value < t_min:
                    ok = False
                if t_max is not None and value > t_max:
                    ok = False
                series.append(1.0 if ok else 0.0)
            elif objective.direction == "informational":
                series.append(0.0)
        normalized[objective.column] = series

    scoring_objectives = [
        obj for obj in config.objectives if obj.weight > 0 and obj.direction not in {"informational", "constraint"}
    ]
    total_weight = sum(obj.weight for obj in scoring_objectives)
    scores: list[float | None] = []
    for index in range(total_rows):
        if total_weight <= 0:
            scores.append(None)
            continue
        weighted = 0.0
        complete = True
        for objective in scoring_objectives:
            value = normalized[objective.column][index]
            if value is None:
                complete = False
                break
            weighted += value * objective.weight
        if not complete:
            scores.append(None)
        else:
            scores.append(weighted / total_weight)

    pareto_objectives = [
        obj
        for obj in config.objectives
        if obj.direction not in {"informational", "constraint"}
        and ((obj.participates_in_pareto is True) or (obj.participates_in_pareto is None and obj.weight > 0))
    ]
    vectors: list[list[float] | None] = []
    for index in range(total_rows):
        if not pareto_objectives:
            vectors.append(None)
            continue
        vector: list[float] = []
        complete = True
        for objective in pareto_objectives:
            value = raw[objective.column][index]
            if value is None:
                complete = False
                break
            if objective.direction in {"higher", "maximize"}:
                vector.append(float(value))
            elif objective.direction in {"lower", "minimize"}:
                vector.append(-float(value))
            elif objective.direction in {"target_range", "constraint"}:
                norm_val = normalized[objective.column][index]
                if norm_val is None:
                    complete = False
                    break
                vector.append(float(norm_val))
        vectors.append(vector if complete else None)

    order = sorted(
        range(total_rows),
        key=lambda i: (
            not bool(table.rows[i].get("filter_pass", True)),
            not constraint_ok[i],
            scores[i] is None,
            -float(scores[i] or 0.0),
            i,
        ),
    )

    candidates = [
        index
        for index in order
        if vectors[index] is not None and constraint_ok[index] and bool(table.rows[index].get("filter_pass", True))
    ]
    candidate_vectors: list[list[float]] = [v for idx in candidates if (v := vectors[idx]) is not None]
    fronts = fast_nondominated_sort(candidates, candidate_vectors, max_fronts=config.pareto_front_limit)
    pareto_rank: list[int | None] = [None] * total_rows
    for front_idx, front_members in enumerate(fronts, start=1):
        for member_idx in front_members:
            pareto_rank[member_idx] = front_idx

    skipped = total_rows - len(candidates)
    if skipped:
        ctx.log(f"Excluded {skipped} filter-failing, constraint-failing or incomplete record(s) from Pareto fronts.")
    if constraint_objectives:
        failed = sum(1 for ok in constraint_ok if not ok)
        ctx.log(
            f"Evaluated {len(constraint_objectives)} hard constraint(s); {failed} record(s) failed and are ranked "
            "after eligible records.",
            level="warning" if failed else "info",
        )
    ctx.log(
        f"Ranking {total_rows} record(s) on {len(config.objectives)} objective(s); "
        "composite scores use normalized objectives with the configured weights.",
    )

    result = table.copy()
    result.add_values(
        Column(
            "composite_score",
            "Composite score",
            "number",
            unit="0-1",
            direction="higher",
            method="Weighted min-max normalised objectives",
            description=(
                "Transparent composite of the configured objectives. Min-max normalisation is relative to "
                "this run's rows, so scores change when rows are added and are not comparable across runs. "
                "Inspect the weights before use."
            ),
        ),
        scores,
    )
    result.add_values(
        Column(
            "pareto_rank",
            "Pareto front",
            "number",
            unit="front",
            direction="lower",
            method="Non-dominated sorting",
            description=(
                "1 = non-dominated front among filter- and constraint-passing records. "
                "Filtered or constraint-failing records are not ranked."
            ),
        ),
        pareto_rank,
    )
    if constraint_objectives:
        result.add_values(
            Column(
                "constraint_pass",
                "Passes hard constraints",
                "boolean",
                method="Configured constraint objective bounds",
                description="False when a constraint value is missing or outside its configured bounds.",
            ),
            constraint_ok,
        )
        result.add_values(
            Column(
                "constraint_reasons",
                "Constraint reasons",
                "string",
                description="Semicolon-separated reasons for a failed hard constraint.",
            ),
            constraint_reasons,
        )
    rank_by_row = {row_index: position + 1 for position, row_index in enumerate(order)}
    result.add_values(
        Column(
            "rank",
            "Rank",
            "number",
            unit="position",
            direction="lower",
            method="Filter status, then hard constraints, then composite score",
            description="Composite ranking. Rows failing filters or hard constraints are ranked after eligible rows.",
        ),
        [rank_by_row[index] for index in range(total_rows)],
    )
    return result


# --------------------------------------------------------------------------- summary report
class SummaryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    title: str = "Run summary"
    top_n: int = Field(default=10, ge=1, le=100)


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def _run_summary(table: Table, config: SummaryConfig, ctx: NodeContext) -> Table:
    rows = len(table.rows)
    passing = sum(1 for row in table.rows if row.get("filter_pass", True))
    ranked = [row for row in table.rows if row.get("rank")]
    ranked.sort(key=lambda row: float(row.get("rank") or 0))
    top = ranked[: config.top_n]

    numeric_columns = [column for column in table.columns if column.type == "number" and column.name != "rank"]
    header = ["Rank", "Name", "SMILES", *[column.label for column in numeric_columns]]
    lines = [
        f"# {config.title}",
        "",
        f"Generated: {datetime.now(UTC).isoformat(timespec='seconds')}",
        f"Records: {rows} | Passing configured filters: {passing} | Failed: {rows - passing}",
        "",
        "| " + " | ".join(header) + " |",
        "|" + "|".join(["---"] * len(header)) + "|",
    ]
    for row in top:
        cells = [_fmt(row.get("rank")), _fmt(row.get("name") or ""), _fmt(row.get("smiles"))]
        cells.extend(_fmt(row.get(column.name)) for column in numeric_columns)
        lines.append("| " + " | ".join(cell.replace("|", "\\|") for cell in cells) + " |")
    lines.extend(
        [
            "",
            "## Column definitions",
            "",
            *[
                f"- **{column.label}** (`{column.name}`)"
                + (f" [{column.unit}]" if column.unit else "")
                + (f" — {column.method}" if column.method else "")
                for column in table.columns
            ],
            "",
            "> Predictions and scores are hypotheses for prioritisation, not experimental measurements, "
            "proof of binding, safety or efficacy.",
            "",
        ]
    )
    markdown = "\n".join(lines)
    ctx.write_artifact("summary.md", markdown, "text/markdown")

    escaped_header = "".join(f"<th>{html.escape(cell)}</th>" for cell in header)
    body = []
    for row in top:
        cells = [_fmt(row.get("rank")), _fmt(row.get("name") or ""), _fmt(row.get("smiles"))]
        cells.extend(_fmt(row.get(column.name)) for column in numeric_columns)
        body.append("<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in cells) + "</tr>")
    document = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        f"<title>{html.escape(config.title)}</title>"
        "<style>body{font-family:system-ui,sans-serif;background:#0b0f14;color:#e6edf6;padding:2rem}"
        "table{border-collapse:collapse;width:100%;font-size:0.85rem}"
        "th,td{border-bottom:1px solid #24303d;padding:0.4rem;text-align:left}"
        "th{color:#8fb3d9;font-weight:600}code{color:#9fd3c7}</style></head><body>"
        f"<h1>{html.escape(config.title)}</h1>"
        f"<p>{rows} records, {passing} passing filters.</p>"
        f"<table><thead><tr>{escaped_header}</tr></thead><tbody>{''.join(body)}</tbody></table>"
        "<p><em>Scores are prioritisation signals, not experimental evidence.</em></p>"
        "</body></html>"
    )
    ctx.write_artifact("summary.html", document, "text/html")
    ctx.log(f"Summary report written for {len(top)} top record(s).")
    return table


# --------------------------------------------------------------------------- table.join
class JoinConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    key_column: str = Field(default="id", description="Common column to align rows on.")
    how: Literal["inner", "left", "outer"] = Field(
        default="left", description="Join type: 'left' (retain all left rows), 'inner', or 'outer'."
    )
    suffix: str = Field(
        default="_branch",
        pattern=r"^_[a-z0-9_]{1,16}$",
        description="Suffix for resolving column name collisions between branches.",
    )


def _run_join(table: Table, config: JoinConfig, ctx: NodeContext) -> Table:
    if not ctx.incoming_tables or len(ctx.incoming_tables) < 2:
        return table

    tables = list(ctx.incoming_tables.values())
    result = tables[0]
    for idx, other in enumerate(tables[1:], start=2):
        sfx = f"{config.suffix}_{idx}" if len(tables) > 2 else config.suffix
        result = result.join(other, key_column=config.key_column, how=config.how, suffix=sfx)

    ctx.log(
        f"Joined {len(tables)} tables on '{config.key_column}' ({config.how}) -> "
        f"{len(result.rows)} rows, {len(result.columns)} columns.",
        level="info",
    )
    ctx.report_progress(1.0)
    return result


def register_builtin_nodes(registry: NodeRegistry) -> None:
    registry.register(
        NodeDefinition(
            type="chem.descriptors",
            title="RDKit descriptors",
            category="chemistry",
            version=NODE_VERSION,
            description="Compute deterministic physicochemical descriptors with RDKit.",
            config_model=DescriptorConfig,
            handler=_run_descriptors,
            requires=("smiles",),
            outputs=lambda config: descriptor_columns(config.descriptors),
            documentation="Values and units follow the pinned RDKit version recorded in the run manifest.",
        )
    )
    registry.register(
        NodeDefinition(
            type="chem.similarity",
            title="Similarity to query",
            category="chemistry",
            version=NODE_VERSION,
            description="Tanimoto similarity of each structure to a query SMILES using Morgan fingerprints.",
            config_model=SimilarityConfig,
            handler=_run_similarity,
            requires=("smiles",),
            extra_requires=lambda _config: (),
            outputs=lambda config: [
                Column(
                    config.column,
                    "Tanimoto similarity",
                    "number",
                    unit="0-1",
                    direction="higher",
                    method="Morgan fingerprint, Tanimoto",
                )
            ],
        )
    )
    registry.register(
        NodeDefinition(
            type="filter.rules",
            title="Rule filter",
            category="triage",
            version=NODE_VERSION,
            description="Flag rows against explicit, editable thresholds. Rejected rows keep their reasons.",
            config_model=FilterConfig,
            handler=_run_filters,
            requires=(),
            extra_requires=lambda config: tuple(rule.column for rule in config.rules),
            outputs=lambda _config: list(FILTER_COLUMNS),
            documentation="Thresholds are project criteria, not universal medicinal-chemistry laws.",
        )
    )
    registry.register(
        NodeDefinition(
            type="rank.pareto",
            title="Pareto + composite ranking",
            category="prioritisation",
            version=NODE_VERSION,
            description="Non-dominated sorting plus a transparent weighted composite score.",
            config_model=RankConfig,
            handler=_run_rank,
            requires=(),
            extra_requires=lambda config: tuple(objective.column for objective in config.objectives),
            outputs=lambda _config: [
                Column(
                    "composite_score",
                    "Composite score",
                    "number",
                    unit="0-1",
                    direction="higher",
                    method="Weighted min-max normalised objectives",
                    description="Dataset-relative: not comparable across runs or datasets.",
                ),
                Column(
                    "pareto_rank",
                    "Pareto front",
                    "number",
                    unit="front",
                    direction="lower",
                    method="Non-dominated sorting",
                ),
                Column(
                    "rank",
                    "Rank",
                    "number",
                    unit="position",
                    direction="lower",
                    method="Filter status, then composite score",
                ),
            ],
        )
    )
    registry.register(
        NodeDefinition(
            type="report.summary",
            title="Summary report",
            category="reporting",
            version=NODE_VERSION,
            description="Write Markdown and HTML summary artifacts with column definitions and caveats.",
            config_model=SummaryConfig,
            handler=_run_summary,
            requires=(),
            outputs=lambda _config: [],
        )
    )
    registry.register(
        NodeDefinition(
            type="dock.vina",
            title="AutoDock Vina docking",
            category="docking",
            version="1.2.5",
            description="CPU molecular docking and binding pose prediction with AutoDock Vina.",
            config_model=VinaConfig,
            handler=run_vina_docking,
            runtime_fingerprint=vina_runtime_fingerprint,
            requires=("smiles",),
            outputs=lambda config: vina_docking_columns(config.output_prefix),
            documentation=(
                "Scores are computational prioritisation signals, not experimental affinity or efficacy proof."
            ),
        )
    )
    registry.register(
        NodeDefinition(
            type="predict.property",
            title="Learned property prediction",
            category="properties",
            version="1.0.0",
            description="Literature-derived property estimates: reduced ESOL logS and a CNS MPO approximation.",
            config_model=PropertyPredictorConfig,
            handler=run_property_prediction,
            requires=("smiles",),
            outputs=lambda config: property_prediction_columns(
                get_property_model(config.model_id),
                config.output_prefix or config.model_id,
                include_uncertainty=config.include_uncertainty,
                check_domain=config.check_applicability_domain,
            ),
            documentation="Predictions are statistical estimations within model applicability domains.",
        )
    )
    registry.register(
        NodeDefinition(
            type="table.join",
            title="Table merge / join",
            category="data",
            version=NODE_VERSION,
            description="Merge branching pipeline tables on a common key column.",
            config_model=JoinConfig,
            handler=_run_join,
            requires=(),
            outputs=lambda _config: [],
            documentation="Combines multiple pipeline branches using key-based alignment.",
        )
    )
