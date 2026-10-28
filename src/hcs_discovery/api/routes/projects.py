"""Project routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ... import services
from ..deps import db
from ..schemas import ProjectCreate

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.get("")
def list_projects(session: Session = Depends(db)) -> dict:
    return {"items": services.list_projects(session)}


@router.post("", status_code=201)
def create_project(payload: ProjectCreate, session: Session = Depends(db)) -> dict:
    project = services.create_project(
        session, name=payload.name, description=payload.description, purpose=payload.purpose
    )
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "purpose": project.purpose,
        "created_at": project.created_at.isoformat() + "Z",
        "updated_at": project.updated_at.isoformat() + "Z",
    }


@router.get("/{project_id}")
def project_overview(project_id: str, session: Session = Depends(db)) -> dict:
    return services.project_overview(session, project_id)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, session: Session = Depends(db)) -> Response:
    services.delete_project(session, project_id)
    return Response(status_code=204)
