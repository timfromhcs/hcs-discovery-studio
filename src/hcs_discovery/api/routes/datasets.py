"""Dataset import and inspection routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy.orm import Session

from ...core.config import Settings
from ...core.errors import ValidationError
from ...datasets.readers import ImportOptions
from ...services import datasets as dataset_service
from ..deps import db, settings_dep

router = APIRouter(prefix="/api/v1", tags=["datasets"])


def _options(
    smiles_column: str | None,
    name_column: str | None,
    id_column: str | None,
    strip_salts: bool,
    neutralize: bool,
    canonical_tautomer: bool,
) -> ImportOptions:
    return ImportOptions(
        smiles_column=smiles_column or None,
        name_column=name_column or None,
        id_column=id_column or None,
        strip_salts=strip_salts,
        neutralize=neutralize,
        canonical_tautomer=canonical_tautomer,
    )


async def _read_upload(file: UploadFile, settings: Settings) -> bytes:
    limit = settings.max_upload_mb * 1024 * 1024
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > limit:
            raise ValidationError(
                f"Upload exceeds the configured limit of {settings.max_upload_mb} MB.",
                details={"limit_bytes": limit},
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/projects/{project_id}/datasets", status_code=201)
async def import_dataset(
    project_id: str,
    file: UploadFile = File(...),
    format: str = Form("auto"),
    smiles_column: str = Form(""),
    name_column: str = Form(""),
    id_column: str = Form(""),
    strip_salts: bool = Form(True),
    neutralize: bool = Form(False),
    canonical_tautomer: bool = Form(False),
    name: str = Form(""),
    source_url: str = Form(""),
    license: str = Form("unknown"),
    session: Session = Depends(db),
    settings: Settings = Depends(settings_dep),
) -> dict:
    data = await _read_upload(file, settings)
    dataset = dataset_service.import_dataset(
        session=session,
        settings=settings,
        project_id=project_id,
        filename=file.filename or "upload",
        data=data,
        fmt=format,
        options=_options(smiles_column, name_column, id_column, strip_salts, neutralize, canonical_tautomer),
        name=name or None,
        source_url=source_url or None,
        license=license or "unknown",
    )
    return dataset_service.dataset_dict(dataset)


@router.get("/projects/{project_id}/datasets")
def list_datasets(project_id: str, session: Session = Depends(db)) -> dict:
    return {"items": dataset_service.list_datasets(session, project_id)}


@router.get("/datasets/{dataset_id}")
def dataset_detail(dataset_id: str, session: Session = Depends(db)) -> dict:
    return dataset_service.dataset_dict(dataset_service.get_dataset(session, dataset_id))


@router.get("/datasets/{dataset_id}/rows")
def dataset_rows(
    dataset_id: str,
    status: str | None = Query(default=None, pattern="^(imported|error|duplicate)$"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(db),
) -> dict:
    return dataset_service.dataset_rows(session, dataset_id, status=status, limit=limit, offset=offset)


@router.delete("/datasets/{dataset_id}", status_code=204)
def delete_dataset(dataset_id: str, session: Session = Depends(db)) -> Response:
    dataset_service.delete_dataset(session, dataset_id)
    return Response(status_code=204)


@router.post("/compounds/validate")
async def validate_compounds(
    file: UploadFile = File(...),
    format: str = Form("auto"),
    smiles_column: str = Form(""),
    name_column: str = Form(""),
    id_column: str = Form(""),
    strip_salts: bool = Form(True),
    neutralize: bool = Form(False),
    canonical_tautomer: bool = Form(False),
    settings: Settings = Depends(settings_dep),
) -> dict:
    data = await _read_upload(file, settings)
    return dataset_service.validate_molecules(
        data,
        file.filename or "upload",
        fmt=format,
        options=_options(smiles_column, name_column, id_column, strip_salts, neutralize, canonical_tautomer),
    )
