"""Target and structure routes.

Structure upload is a multipart form so the API and the CLI go through the same
service call and the same size limits.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy.orm import Session

from ... import services
from ..deps import db
from ..schemas import TargetCreate, TargetUpdate

router = APIRouter(prefix="/api/v1", tags=["targets"])


@router.get("/projects/{project_id}/targets")
def list_targets(project_id: str, session: Session = Depends(db)) -> dict:
    return {"items": services.list_targets(session, project_id)}


@router.post("/projects/{project_id}/targets", status_code=201)
def create_target(project_id: str, payload: TargetCreate, session: Session = Depends(db)) -> dict:
    target = services.create_target(
        session,
        project_id=project_id,
        name=payload.name,
        gene_symbol=payload.gene_symbol,
        uniprot_id=payload.uniprot_id,
        organism=payload.organism,
        notes=payload.notes,
    )
    return services.target_detail(session, target.id)


@router.get("/targets/{target_id}")
def target_detail(target_id: str, session: Session = Depends(db)) -> dict:
    return services.target_detail(session, target_id)


@router.patch("/targets/{target_id}")
def update_target(target_id: str, payload: TargetUpdate, session: Session = Depends(db)) -> dict:
    services.update_target(
        session,
        target_id,
        name=payload.name,
        gene_symbol=payload.gene_symbol,
        uniprot_id=payload.uniprot_id,
        organism=payload.organism,
        notes=payload.notes,
    )
    return services.target_detail(session, target_id)


@router.delete("/targets/{target_id}", status_code=204)
def delete_target(target_id: str, session: Session = Depends(db)) -> Response:
    services.delete_target(session, target_id)
    return Response(status_code=204)


@router.get("/projects/{project_id}/structures")
def list_structures(project_id: str, session: Session = Depends(db)) -> dict:
    return {"items": services.list_structures(session, project_id)}


@router.post("/projects/{project_id}/structures", status_code=201)
async def import_structure(
    project_id: str,
    file: UploadFile = File(...),
    target_id: str = Form(""),
    source: str = Form("upload"),
    accession: str = Form(""),
    license: str = Form("unknown"),
    session: Session = Depends(db),
) -> dict:
    data = await file.read()
    structure = services.import_structure(
        session,
        project_id=project_id,
        filename=file.filename or "structure.pdb",
        data=data,
        target_id=target_id or None,
        source=source,
        accession=accession or None,
        license=license,
    )
    return services.structure_detail(session, structure.id)


@router.get("/structures/{structure_id}")
def structure_detail(structure_id: str, session: Session = Depends(db)) -> dict:
    return services.structure_detail(session, structure_id)


@router.delete("/structures/{structure_id}", status_code=204)
def delete_structure(structure_id: str, session: Session = Depends(db)) -> Response:
    services.delete_structure(session, structure_id)
    return Response(status_code=204)
