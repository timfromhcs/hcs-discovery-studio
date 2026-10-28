"""Typed tabular data that flows between workflow nodes.

Every column carries its unit, score direction and producing method, so downstream
ranking and the UI cannot silently interpret an unqualified number.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Literal

from ..core.errors import ValidationError
from ..core.hashing import stable_json_hash

ColumnType = Literal["string", "number", "boolean"]


@dataclass(frozen=True)
class Column:
    name: str
    label: str
    type: ColumnType = "number"
    unit: str | None = None
    direction: Literal["higher", "lower", "neutral"] | None = None
    method: str | None = None
    description: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "type": self.type,
            "unit": self.unit,
            "direction": self.direction,
            "method": self.method,
            "description": self.description,
        }


IDENTITY_COLUMNS: tuple[Column, ...] = (
    Column("compound_id", "Compound ID", "string", description="Internal identifier."),
    Column("id", "ID", "string", description="Compound identifier."),
    Column(
        "smiles",
        "SMILES",
        "string",
        method="RDKit canonical isomeric SMILES",
        description="Canonical isomeric SMILES after the dataset standardisation policy.",
    ),
    Column("name", "Name", "string"),
    Column("source_id", "Source ID", "string", description="Identifier from the source record."),
)

FILTER_COLUMNS: tuple[Column, ...] = (
    Column(
        "filter_pass",
        "Passes filters",
        "boolean",
        description="Result of the configured rule checks. Rejected rows are retained.",
    ),
    Column(
        "filter_reasons",
        "Filter reasons",
        "string",
        description="Semicolon-separated reasons for a failed rule.",
    ),
)


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value)))


@dataclass
class Table:
    rows: list[dict[str, Any]]
    columns: list[Column] = field(default_factory=list)

    def __post_init__(self) -> None:
        seen: dict[str, Column] = {}
        for column in self.columns:
            seen[column.name] = column
        self.columns = list(seen.values())

    @property
    def column_names(self) -> list[str]:
        return [column.name for column in self.columns]

    def column(self, name: str) -> Column:
        for column in self.columns:
            if column.name == name:
                return column
        raise ValidationError(f"Column '{name}' is not present.", details={"columns": self.column_names})

    def has_column(self, name: str) -> bool:
        return any(column.name == name for column in self.columns)

    def require(self, names: Iterable[str]) -> None:
        missing = [name for name in names if not self.has_column(name)]
        if missing:
            raise ValidationError(
                f"Required column(s) missing: {', '.join(missing)}.",
                details={"missing": missing, "columns": self.column_names},
            )

    def with_columns(self, new_columns: Iterable[Column]) -> Table:
        merged = list(self.columns)
        existing = {column.name for column in merged}
        for column in new_columns:
            if column.name not in existing:
                merged.append(column)
                existing.add(column.name)
        return Table(rows=self.rows, columns=merged)

    def add_values(self, column: Column, values: list[Any]) -> Table:
        if len(values) != len(self.rows):
            raise ValueError("Column length does not match row count")
        for row, value in zip(self.rows, values, strict=True):
            row[column.name] = value
        if not self.has_column(column.name):
            self.columns.append(column)
        return self

    def numeric(self, name: str) -> list[float | None]:
        out: list[float | None] = []
        for row in self.rows:
            value = row.get(name)
            if value is None or isinstance(value, bool):
                out.append(None)
                continue
            if isinstance(value, (int, float)):
                if math.isnan(value) or math.isinf(value):
                    out.append(None)
                else:
                    out.append(float(value))
                continue
            try:
                num = float(value)
                if math.isnan(num) or math.isinf(num):
                    out.append(None)
                else:
                    out.append(num)
            except (TypeError, ValueError):
                out.append(None)
        return out

    def copy(self, *, rows: list[dict[str, Any]] | None = None) -> Table:
        return Table(
            rows=[dict(row) for row in rows] if rows is not None else [dict(row) for row in self.rows],
            columns=list(self.columns),
        )

    def subset_columns(self, names: Iterable[str]) -> Table:
        keep = list(names)
        for name in keep:
            self.column(name)
        return Table(
            rows=[{key: row.get(key) for key in keep} for row in self.rows],
            columns=[column for column in self.columns if column.name in keep],
        )

    def join(
        self,
        other: Table,
        *,
        key_column: str = "id",
        how: Literal["inner", "left", "outer"] = "left",
        suffix: str = "_right",
    ) -> Table:
        """Merge this table with another table on a common key column."""
        self.require([key_column])
        other.require([key_column])

        merged_columns: list[Column] = list(self.columns)
        right_col_map: dict[str, str] = {}
        existing_names = set(self.column_names)

        for col in other.columns:
            if col.name == key_column:
                continue
            final_name = col.name
            if final_name in existing_names:
                final_name = f"{col.name}{suffix}"
            right_col_map[col.name] = final_name
            merged_columns.append(
                Column(
                    name=final_name,
                    label=col.label,
                    type=col.type,
                    unit=col.unit,
                    direction=col.direction,
                    method=col.method,
                    description=col.description,
                )
            )

        right_index: dict[Any, dict[str, Any]] = {}
        for r in other.rows:
            k = r.get(key_column)
            if k is not None:
                right_index[k] = r

        new_rows: list[dict[str, Any]] = []
        seen_right_keys: set[Any] = set()

        for l_row in self.rows:
            k = l_row.get(key_column)
            r_row = right_index.get(k)
            if r_row is None and how == "inner":
                continue
            row_dict = dict(l_row)
            if r_row is not None:
                seen_right_keys.add(k)
                for orig_name, final_name in right_col_map.items():
                    row_dict[final_name] = r_row.get(orig_name)
            else:
                for final_name in right_col_map.values():
                    row_dict[final_name] = None
            new_rows.append(row_dict)

        if how == "outer":
            for k, r_row in right_index.items():
                if k not in seen_right_keys:
                    row_dict = {c.name: None for c in self.columns}
                    row_dict[key_column] = k
                    for orig_name, final_name in right_col_map.items():
                        row_dict[final_name] = r_row.get(orig_name)
                    new_rows.append(row_dict)

        return Table(rows=new_rows, columns=merged_columns)

    def content_hash(self) -> str:
        return stable_json_hash(
            {
                "columns": [column.as_dict() for column in self.columns],
                "rows": self.rows,
            }
        )

    def summary(self) -> dict[str, Any]:
        return {
            "rows": len(self.rows),
            "columns": self.column_names,
        }

    def to_records(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        rows = self.rows if limit is None else self.rows[:limit]
        return [dict(row) for row in rows]
