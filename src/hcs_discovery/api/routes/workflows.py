"""Workflow routes: catalog, templates, validation and CRUD."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ... import services
from ...core.errors import ValidationError
from ...database.models import Workflow
from ...workflow.registry import default_registry
from ...workflow.schema import validate_workflow
from ...workflow.templates import templates
from ..deps import db
from ..schemas import WorkflowSaveRequest, WorkflowValidateRequest

router = APIRouter(prefix="/api/v1", tags=["workflows"])


@router.get("/projects/{project_id}/workflows")
def list_workflows(project_id: str, session: Session = Depends(db)) -> dict:
    services.get_project(session, project_id)
    workflows = (
        session.execute(select(Workflow).where(Workflow.project_id == project_id).order_by(Workflow.updated_at.desc()))
        .scalars()
        .all()
    )
    return {
        "items": [
            {
                "id": workflow.id,
                "name": workflow.name,
                "description": workflow.description,
                "schema_version": workflow.schema_version,
                "content_hash": workflow.content_hash,
                "definition": workflow.definition,
                "created_at": workflow.created_at.isoformat() + "Z",
                "updated_at": workflow.updated_at.isoformat() + "Z",
            }
            for workflow in workflows
        ]
    }


@router.post("/workflows", status_code=201)
def create_workflow(payload: WorkflowSaveRequest, session: Session = Depends(db)) -> dict:
    workflow = services.save_workflow(session, project_id=payload.project_id, payload=payload.definition)
    return _workflow_dict(workflow)


@router.get("/workflows/{workflow_id}")
def get_workflow(workflow_id: str, session: Session = Depends(db)) -> dict:
    workflow = session.get(Workflow, workflow_id)
    if workflow is None:
        raise ValidationError(f"Workflow '{workflow_id}' does not exist.")
    return _workflow_dict(workflow)


@router.put("/workflows/{workflow_id}")
def update_workflow(workflow_id: str, payload: WorkflowSaveRequest, session: Session = Depends(db)) -> dict:
    workflow = services.save_workflow(
        session, project_id=payload.project_id, payload=payload.definition, workflow_id=workflow_id
    )
    return _workflow_dict(workflow)


@router.delete("/workflows/{workflow_id}", status_code=204)
def delete_workflow(workflow_id: str, session: Session = Depends(db)) -> Response:
    workflow = session.get(Workflow, workflow_id)
    if workflow is None:
        raise ValidationError(f"Workflow '{workflow_id}' does not exist.")
    session.delete(workflow)
    session.commit()
    return Response(status_code=204)


@router.post("/workflows/validate")
def validate(payload: WorkflowValidateRequest, request: Request) -> dict:
    validated = validate_workflow(payload.definition, registry=request.app.state.registry)
    return {
        "valid": True,
        "content_hash": validated.content_hash,
        "order": [node.id for node in validated.order],
        "nodes": [
            {
                "id": node.id,
                "type": node.type,
                "columns_after": [column.as_dict() for column in validated.columns_at.get(node.id, [])],
            }
            for node in validated.order
        ],
    }


@router.get("/workflow-catalog")
def catalog(request: Request) -> dict:
    registry = request.app.state.registry or default_registry()
    return {"items": registry.catalog(), "templates": templates()}


def _workflow_dict(workflow: Workflow) -> dict:
    return {
        "id": workflow.id,
        "project_id": workflow.project_id,
        "name": workflow.name,
        "description": workflow.description,
        "schema_version": workflow.schema_version,
        "content_hash": workflow.content_hash,
        "definition": workflow.definition,
        "created_at": workflow.created_at.isoformat() + "Z",
        "updated_at": workflow.updated_at.isoformat() + "Z",
    }
