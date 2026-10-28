"""Row-oriented molecule import with explicit, per-row error reporting.

Supported inputs: CSV (structure column selected by the user), SDF and plain
``.smi``. Every input row is retained in the dataset row log, including rows that
failed to parse, so nothing disappears silently.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rdkit import Chem, RDLogger

from ..chemistry.standardize import StandardizeOptions, standardize
from ..core.errors import ValidationError
from ..core.hashing import sha256_file

RDLogger.DisableLog("rdApp.*")

SUPPORTED_FORMATS = {"csv", "sdf", "smi", "smiles", "txt"}


@dataclass
class ImportOptions:
    smiles_column: str | None = None
    name_column: str | None = None
    id_column: str | None = None
    strip_salts: bool = True
    neutralize: bool = False
    canonical_tautomer: bool = False
    max_rows: int = 50_000

    def standardize_options(self) -> StandardizeOptions:
        return StandardizeOptions(
            strip_salts=self.strip_salts,
            neutralize=self.neutralize,
            canonical_tautomer=self.canonical_tautomer,
        )


@dataclass
class ParsedRow:
    row_index: int
    raw: dict[str, Any]
    smiles: str | None = None
    name: str | None = None
    source_id: str | None = None


@dataclass
class RowOutcome:
    row: ParsedRow
    status: str
    error: str | None = None
    molecule: Any | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class ImportResult:
    format: str
    checksum: str
    record_count: int
    outcomes: list[RowOutcome]
    column_mapping: dict[str, Any]
    warnings: list[str] = field(default_factory=list)

    @property
    def imported_count(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.status == "imported")

    @property
    def error_count(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.status not in {"imported", "duplicate"})


def detect_format(filename: str, head: bytes | None = None) -> str:
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix in {"csv", "tsv"}:
        return "csv"
    if suffix in {"sdf", "sd"}:
        return "sdf"
    if suffix in {"smi", "smiles"}:
        return "smi"
    if head:
        text = head.decode("utf-8", errors="replace").lstrip()
        if text.startswith("$$$$"):
            return "sdf"
        if text.startswith("smiles") or "," in text.splitlines()[0]:
            return "csv"
        if "\t" in text.splitlines()[0]:
            return "csv"
        return "smi"
    raise ValidationError(
        "Could not detect the file format. Pass --format csv|sdf|smi.",
        details={"filename": filename},
    )


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _open_text(path: Path) -> str:
    return _decode(path.read_bytes())


def _csv_rows(text: str, options: ImportOptions) -> tuple[list[ParsedRow], dict[str, Any], list[str]]:
    warnings: list[str] = []
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel

    reader = csv.reader(io.StringIO(text), dialect)
    try:
        header = next(reader)
    except StopIteration as exc:
        raise ValidationError("CSV file is empty.") from exc

    header = [cell.strip() for cell in header]
    counts: dict[str, int] = {}
    clean_header: list[str] = []
    for index, name in enumerate(header):
        base = name or f"column_{index + 1}"
        counts[base] = counts.get(base, 0) + 1
        if counts[base] > 1:
            warnings.append(f"Duplicate header '{base}' renamed to '{base}_{counts[base]}'.")
            base = f"{base}_{counts[base]}"
        clean_header.append(base)
    if not clean_header:
        raise ValidationError("CSV has no header row.")

    def pick(explicit: str | None, candidates: tuple[str, ...]) -> str | None:
        if explicit:
            if explicit not in clean_header:
                raise ValidationError(
                    f"Column '{explicit}' not found.",
                    details={"available": clean_header},
                )
            return explicit
        lowered = {name.lower(): name for name in clean_header}
        for candidate in candidates:
            if candidate in lowered:
                return lowered[candidate]
        return None

    smiles_column = pick(options.smiles_column, ("smiles", "canonical_smiles", "structure", "mol", "molecule"))
    if smiles_column is None:
        raise ValidationError(
            "No structure column found. Choose a column explicitly.",
            details={
                "available": clean_header,
                "hint": "hcs-discovery dataset import --smiles-column <name>",
            },
        )
    name_column = pick(options.name_column, ("name", "compound_name", "title", "preferred_name"))
    id_column = pick(options.id_column, ("id", "compound_id", "chembl_id", "cid", "identifier"))

    rows: list[ParsedRow] = []
    for offset, raw_cells in enumerate(reader):
        if not any(cell.strip() for cell in raw_cells):
            continue
        if len(rows) >= options.max_rows:
            raise ValidationError(
                f"Dataset exceeds the configured limit of {options.max_rows} rows. "
                "Split the file or raise HCS_MAX_IMPORT_ROWS before importing.",
                details={"max_rows": options.max_rows},
            )
        raw = {
            clean_header[i] if i < len(clean_header) else f"column_{i + 1}": value for i, value in enumerate(raw_cells)
        }
        rows.append(
            ParsedRow(
                row_index=offset + 1,
                raw=raw,
                smiles=(raw.get(smiles_column) or "").strip() or None,
                name=(raw.get(name_column) or "").strip() or None if name_column else None,
                source_id=(raw.get(id_column) or "").strip() or None if id_column else None,
            )
        )

    mapping = {"smiles": smiles_column, "name": name_column, "id": id_column}
    return rows, mapping, warnings


def _sdf_rows(path: Path, options: ImportOptions) -> tuple[list[ParsedRow], dict[str, Any], list[str]]:
    supplier = Chem.SDMolSupplier(str(path), sanitize=True, removeHs=False)
    rows: list[ParsedRow] = []
    warnings: list[str] = []
    for index, mol in enumerate(supplier):
        if index >= options.max_rows:
            raise ValidationError(
                f"Dataset exceeds the configured limit of {options.max_rows} records. "
                "Split the file or raise HCS_MAX_IMPORT_ROWS before importing.",
                details={"max_rows": options.max_rows},
            )
        if mol is None:
            rows.append(ParsedRow(row_index=index + 1, raw={"record": index + 1}, smiles=None))
            continue
        smiles = Chem.MolToSmiles(mol, isomericSmiles=True)
        name = mol.GetProp("_Name").strip() if mol.HasProp("_Name") else None
        source_id = None
        for prop in ("ID", "id", "ChEMBL_ID", "PUBCHEM_CID"):
            if mol.HasProp(prop):
                source_id = mol.GetProp(prop).strip()
                break
        rows.append(
            ParsedRow(
                row_index=index + 1,
                raw={
                    "record": index + 1,
                    "smiles": smiles,
                    "name": name or "",
                    "id": source_id or "",
                },
                smiles=smiles,
                name=name or None,
                source_id=source_id,
            )
        )
    return rows, {"smiles": "record", "name": "_Name", "id": "property"}, warnings


def _smi_rows(text: str, options: ImportOptions) -> tuple[list[ParsedRow], dict[str, Any], list[str]]:
    rows: list[ParsedRow] = []
    warnings: list[str] = []
    for index, line in enumerate(text.splitlines()):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if len(rows) >= options.max_rows:
            raise ValidationError(
                f"Dataset exceeds the configured limit of {options.max_rows} records. "
                "Split the file or raise HCS_MAX_IMPORT_ROWS before importing.",
                details={"max_rows": options.max_rows},
            )
        parts = line.split()
        smiles = parts[0]
        name = parts[1] if len(parts) > 1 else None
        rows.append(
            ParsedRow(
                row_index=index + 1,
                raw={"line": line, "smiles": smiles, "name": name or ""},
                smiles=smiles,
                name=name,
            )
        )
    return rows, {"smiles": "line[0]", "name": "line[1]", "id": None}, warnings


def parse_file(path: Path, filename: str, fmt: str, options: ImportOptions) -> ImportResult:
    if not path.exists():
        raise ValidationError("Uploaded file is missing.", details={"path": str(path)})
    size = path.stat().st_size
    if size == 0:
        raise ValidationError("File is empty.")
    fmt = fmt.lower()
    if fmt == "auto":
        with path.open("rb") as handle:
            fmt = detect_format(filename, handle.read(4096))
    if fmt not in SUPPORTED_FORMATS:
        raise ValidationError(f"Unsupported format '{fmt}'. Use csv, sdf or smi.")

    if fmt == "csv":
        rows, mapping, warnings = _csv_rows(_open_text(path), options)
    elif fmt == "sdf":
        rows, mapping, warnings = _sdf_rows(path, options)
    else:
        rows, mapping, warnings = _smi_rows(_open_text(path), options)

    outcomes: list[RowOutcome] = []
    standardize_options = options.standardize_options()
    for row in rows:
        if row.smiles is None:
            message = "Record could not be parsed by RDKit." if fmt == "sdf" else "Missing structure value."
            outcomes.append(RowOutcome(row=row, status="error", error=message))
            continue
        try:
            molecule = standardize(row.smiles, standardize_options)
        except Exception as exc:
            outcomes.append(RowOutcome(row=row, status="error", error=str(exc)))
            continue
        outcomes.append(RowOutcome(row=row, status="imported", molecule=molecule, warnings=molecule.warnings))

    return ImportResult(
        format=fmt,
        checksum=sha256_file(path),
        record_count=len(rows),
        outcomes=outcomes,
        column_mapping=mapping,
        warnings=warnings,
    )


def iter_chunks(items: list[Any], size: int = 500) -> Iterator[list[Any]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]
