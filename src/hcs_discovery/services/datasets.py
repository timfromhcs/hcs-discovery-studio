"""Dataset import and query services."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..chemistry.standardize import StandardizeOptions, standardize
from ..core.config import Settings
from ..core.errors import NotFoundError, ValidationError
from ..core.hashing import new_id
from ..core.paths import safe_filename, safe_join
from ..core.timeutil import db_now
from ..database.models import Compound, Dataset, DatasetRow
from ..datasets.readers import ImportOptions, parse_file
from .projects import audit, get_project

MAX_FILENAME = 200


def import_dataset(
    *,
    session: Session,
    settings: Settings,
    project_id: str,
    filename: str,
    data: bytes,
    fmt: str = "auto",
    options: ImportOptions | None = None,
    name: str | None = None,
    source_url: str | None = None,
    license: str = "unknown",
) -> Dataset:
    get_project(session, project_id)
    if not data:
        raise ValidationError("Uploaded file is empty.")
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise ValidationError(
            f"Upload exceeds the configured limit of {settings.max_upload_mb} MB.",
            details={"bytes": len(data), "limit": max_bytes},
        )
    if not filename or len(filename) > MAX_FILENAME:
        raise ValidationError("Filename is missing or too long.")

    options = options or ImportOptions()
    options.max_rows = min(options.max_rows, settings.max_import_rows)
    dataset_id = new_id("dts")
    safe_name = safe_filename(filename, fallback="dataset")
    upload_dir = safe_join(settings.uploads_dir, project_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored = upload_dir / f"{dataset_id}-{safe_name}"
    stored.write_bytes(data)

    try:
        result = parse_file(stored, safe_name, fmt, options)
    except Exception:
        # Never leave files behind for imports that were rejected before any DB write.
        stored.unlink(missing_ok=True)
        raise

    dataset = Dataset(
        id=dataset_id,
        project_id=project_id,
        name=(name or Path(safe_name).stem)[:200],
        source_format=result.format,
        original_filename=safe_name,
        sha256=result.checksum,
        record_count=result.record_count,
        source_url=source_url,
        license=license,
        column_mapping=result.column_mapping,
        transformation_log=[
            {
                "step": "standardize",
                "options": options.standardize_options().as_dict(),
                "policy": {
                    "identity": "canonical isomeric SMILES",
                    "duplicates": "keep first occurrence per isomeric SMILES; later rows are retained as duplicates",
                    "salts": "largest fragment when strip_salts is enabled; original record retained",
                },
            },
            *[{"step": "reader_warning", "message": warning} for warning in result.warnings],
        ],
    )
    session.add(dataset)
    session.flush()

    seen: dict[str, str] = {}
    imported = 0
    errors = 0
    duplicates = 0
    for outcome in result.outcomes:
        compound_id: str | None = None
        status = outcome.status
        error = outcome.error
        if outcome.status == "imported" and outcome.molecule is not None:
            molecule = outcome.molecule
            key = molecule.isomeric_smiles
            if key in seen:
                status = "duplicate"
                compound_id = seen[key]
                duplicates += 1
                error = f"Duplicate structure of compound {compound_id}; retained for audit, not re-imported."
            else:
                compound_id = new_id("cmp")
                seen[key] = compound_id
                imported += 1
                session.add(
                    Compound(
                        id=compound_id,
                        project_id=project_id,
                        dataset_id=dataset.id,
                        source_row_index=outcome.row.row_index,
                        source_id=outcome.row.source_id,
                        name=(outcome.row.name or "")[:200] or None,
                        input_smiles=outcome.row.smiles or "",
                        canonical_smiles=molecule.canonical_smiles,
                        isomeric_smiles=molecule.isomeric_smiles,
                        inchi=molecule.inchi,
                        inchikey=molecule.inchikey,
                        formula=molecule.formula,
                        formal_charge=molecule.formal_charge,
                        warnings=molecule.warnings,
                    )
                )
        elif outcome.status == "error":
            errors += 1
        session.add(
            DatasetRow(
                dataset_id=dataset.id,
                row_index=outcome.row.row_index,
                status=status,
                raw=outcome.row.raw,
                error=error,
                compound_id=compound_id,
            )
        )

    dataset.imported_count = imported
    dataset.error_count = errors
    dataset.transformation_log = [
        *dataset.transformation_log,
        {
            "step": "import_summary",
            "records": result.record_count,
            "imported": imported,
            "duplicates": duplicates,
            "errors": errors,
            "completed_at": db_now().isoformat(timespec="seconds") + "Z",
        },
    ]
    audit(
        session,
        "dataset.import",
        "dataset",
        dataset.id,
        {
            "filename": safe_name,
            "records": result.record_count,
            "errors": errors,
            "duplicates": duplicates,
        },
    )
    session.commit()
    session.refresh(dataset)
    return dataset


def list_datasets(session: Session, project_id: str) -> list[dict[str, Any]]:
    rows = (
        session.execute(select(Dataset).where(Dataset.project_id == project_id).order_by(Dataset.created_at.desc()))
        .scalars()
        .all()
    )
    return [dataset_dict(dataset) for dataset in rows]


def dataset_dict(dataset: Dataset) -> dict[str, Any]:
    return {
        "id": dataset.id,
        "project_id": dataset.project_id,
        "name": dataset.name,
        "source_format": dataset.source_format,
        "original_filename": dataset.original_filename,
        "sha256": dataset.sha256,
        "record_count": dataset.record_count,
        "imported_count": dataset.imported_count,
        "error_count": dataset.error_count,
        "duplicate_count": max(0, dataset.record_count - dataset.imported_count - dataset.error_count),
        "license": dataset.license,
        "source_url": dataset.source_url,
        "column_mapping": dataset.column_mapping,
        "transformation_log": dataset.transformation_log,
        "created_at": dataset.created_at.isoformat() + "Z",
    }


def get_dataset(session: Session, dataset_id: str) -> Dataset:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise NotFoundError(f"Dataset '{dataset_id}' does not exist.")
    return dataset


def delete_dataset(
    session: Session,
    dataset_id: str,
    *,
    purge_files: bool = True,
    settings: Any = None,
) -> None:
    from sqlalchemy import delete

    from ..core.config import get_settings

    settings = settings or get_settings()
    dataset = get_dataset(session, dataset_id)

    if purge_files:
        upload_dir = settings.uploads_dir / dataset.project_id
        if upload_dir.exists():
            for f in upload_dir.glob(f"{dataset.id}-*"):
                f.unlink(missing_ok=True)

    session.execute(delete(Compound).where(Compound.dataset_id == dataset.id))
    session.delete(dataset)
    audit(session, "dataset.delete", "dataset", dataset_id, {"name": dataset.name, "purged_files": purge_files})
    session.commit()


def dataset_rows(
    session: Session,
    dataset_id: str,
    *,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    get_dataset(session, dataset_id)
    query = select(DatasetRow).where(DatasetRow.dataset_id == dataset_id)
    count_query = select(func.count(DatasetRow.id)).where(DatasetRow.dataset_id == dataset_id)
    if status:
        query = query.where(DatasetRow.status == status)
        count_query = count_query.where(DatasetRow.status == status)
    total = int(session.execute(count_query).scalar() or 0)
    rows = session.execute(query.order_by(DatasetRow.row_index).limit(limit).offset(offset)).scalars().all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "row_index": row.row_index,
                "status": row.status,
                "error": row.error,
                "compound_id": row.compound_id,
                "raw": row.raw,
            }
            for row in rows
        ],
    }


def validate_molecules(
    data: bytes, filename: str, fmt: str = "auto", options: ImportOptions | None = None
) -> dict[str, Any]:
    """Pure in-memory validation used by ``compounds validate`` (no DB writes)."""
    import tempfile

    options = options or ImportOptions()
    with tempfile.TemporaryDirectory(prefix="hcs-validate-") as temp:
        path = Path(temp) / safe_filename(filename, fallback="input")
        path.write_bytes(data)
        result = parse_file(path, path.name, fmt, options)
    rows = []
    for outcome in result.outcomes:
        molecule = outcome.molecule
        rows.append(
            {
                "row_index": outcome.row.row_index,
                "status": outcome.status,
                "error": outcome.error,
                "smiles": outcome.row.smiles,
                "canonical_smiles": molecule.canonical_smiles if molecule else None,
                "name": outcome.row.name,
                "source_id": outcome.row.source_id,
                "warnings": outcome.warnings,
            }
        )
    return {
        "format": result.format,
        "checksum": result.checksum,
        "record_count": result.record_count,
        "imported_count": result.imported_count,
        "error_count": result.error_count,
        "column_mapping": result.column_mapping,
        "warnings": result.warnings,
        "rows": rows,
    }


def standardize_one(smiles: str, options: StandardizeOptions | None = None) -> dict[str, Any]:
    return standardize(smiles, options).as_dict()
