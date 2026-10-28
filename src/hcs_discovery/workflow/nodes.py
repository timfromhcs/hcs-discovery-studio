"""Built-in workflow nodes: descriptors, similarity, rule filters, Pareto ranking, summary."""

from __future__ import annotations

import html
import math
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator
from rdkit import Chem

from ..chemistry.descriptors import (
    DEFAULT_DESCRIPTORS,
    DESCRIPTORS,
    descriptor_columns,
    tanimoto_to_query,
)
from ..core.errors import ValidationError
from .registry import NodeContext, NodeDefinition, NodeRegistry
from .table import FILTER_COLUMNS, Column, Table

NODE_VERSION = "1.0.0"


# --------------------------------------------------------------------------- descriptors
class DescriptorConfig(BaseModel):
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
            except Exception:
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
    column: str
    op: Operator
    value: float | str | bool
    value2: float | None = None
    label: str | None = None


class FilterConfig(BaseModel):
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
    return None if math.isnan(number) else number


def _check(rule: RuleConfig, value: Any) -> bool:
    number = _numeric(value)
    if rule.op in {"eq", "ne"} and not isinstance(rule.value, (int, float)):
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
    low = min(threshold, float(rule.value2))  # type: ignore[arg-type]
    high = max(threshold, float(rule.value2))  # type: ignore[arg-type]
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
class ObjectiveConfig(BaseModel):
    column: str
    direction: Literal["higher", "lower"]
    weight: float = Field(default=1.0, ge=0.0, le=100.0)


class RankConfig(BaseModel):
    objectives: list[ObjectiveConfig] = Field(min_length=1)
    pareto_front_limit: int = Field(default=10, ge=1, le=50)

    @field_validator("objectives")
    @classmethod
    def _weights(cls, objectives: list[ObjectiveConfig]) -> list[ObjectiveConfig]:
        if sum(objective.weight for objective in objectives) <= 0:
            raise ValueError("At least one objective must have a positive weight")
        return objectives


def _dominates(a: list[float], b: list[float]) -> bool:
    better_or_equal = all(x >= y for x, y in zip(a, b, strict=True))
    strictly_better = any(x > y for x, y in zip(a, b, strict=True))
    return better_or_equal and strictly_better


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
        if expected in {"higher", "lower"} and expected != objective.direction:
            ctx.log(
                f"Objective '{objective.column}' uses direction '{objective.direction}' while the column "
                f"metadata says '{expected}'. The explicit objective wins.",
                level="warning",
            )

    raw = {objective.column: table.numeric(objective.column) for objective in config.objectives}
    total_rows = len(table.rows)

    normalized: dict[str, list[float | None]] = {}
    for objective in config.objectives:
        values = [value for value in raw[objective.column] if value is not None]
        low = min(values) if values else None
        high = max(values) if values else None
        series: list[float | None] = []
        for value in raw[objective.column]:
            if value is None or low is None or high is None:
                series.append(None)
            elif math.isclose(high, low):
                series.append(0.5)
            elif objective.direction == "higher":
                series.append((value - low) / (high - low))
            else:
                series.append((high - value) / (high - low))
        normalized[objective.column] = series

    total_weight = sum(objective.weight for objective in config.objectives)
    scores: list[float | None] = []
    mentioned: list[str] = []
    for index in range(total_rows):
        weighted = 0.0
        complete = True
        for objective in config.objectives:
            value = normalized[objective.column][index]
            if value is None:
                complete = False
                break
            weighted += value * objective.weight
        if not complete:
            scores.append(None)
            mentioned.append("missing objective value")
        else:
            scores.append(weighted / total_weight)

    # Pareto fronts on objective vectors (direction-normalised, higher is better).
    vectors: list[list[float] | None] = []
    for index in range(total_rows):
        vector: list[float] = []
        for objective in config.objectives:
            value = raw[objective.column][index]
            if value is None:
                vector = []
                break
            vector.append(float(value) if objective.direction == "higher" else -float(value))
        vectors.append(vector or None)

    order = sorted(
        range(total_rows),
        key=lambda i: (
            not bool(table.rows[i].get("filter_pass", True)),
            scores[i] is None,
            -float(scores[i] or 0.0),
        ),
    )
    pareto_rank: list[int | None] = [None] * total_rows
    candidates = [
        index for index in order if vectors[index] is not None and bool(table.rows[index].get("filter_pass", True))
    ]
    skipped = total_rows - len(candidates)
    if skipped:
        ctx.log(f"Excluded {skipped} filter-failing record(s) from Pareto fronts.")
    rank_value = 1
    ctx.log(
        f"Ranking {total_rows} record(s) on {len(config.objectives)} objective(s); "
        "composite scores use min-max normalisation with the configured weights.",
    )
    while candidates and rank_value <= config.pareto_front_limit:
        front: list[int] = []
        remaining: list[int] = []
        for index in candidates:
            current_vector: list[float] | None = vectors[index]
            assert current_vector is not None
            if any(_dominates(vectors[other], current_vector) for other in front):  # type: ignore[arg-type]
                remaining.append(index)
            else:
                front.append(index)
        if not front:
            break
        for index in front:
            pareto_rank[index] = rank_value
        candidates = remaining
        rank_value += 1
        if total_rows > 2000:
            ctx.check_cancel()
    if candidates:
        ctx.log(
            f"{len(candidates)} record(s) were not assigned a Pareto front within the configured "
            f"limit of {config.pareto_front_limit} fronts.",
            level="warning",
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
            description="Transparent composite of the configured objectives. Inspect the weights before use.",
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
            description="1 = non-dominated front among filter-passing records. Filtered records are not ranked.",
        ),
        pareto_rank,
    )
    rank_by_row = {row_index: position + 1 for position, row_index in enumerate(order)}
    result.add_values(
        Column(
            "rank",
            "Rank",
            "number",
            unit="position",
            direction="lower",
            method="Filter status, then composite score",
            description="Composite ranking. Rows failing filters are ranked after passing rows.",
        ),
        [rank_by_row[index] for index in range(total_rows)],
    )
    return result


# --------------------------------------------------------------------------- summary report
class SummaryConfig(BaseModel):
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
