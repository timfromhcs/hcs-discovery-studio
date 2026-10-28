"""Application services shared by the HTTP API, CLI and tests.

Keeping the domain logic here guarantees that the UI, CLI and API execute the same
code paths instead of maintaining parallel pipelines.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.errors import ConflictError, NotFoundError, ValidationError
from ..core.redaction import redact_text
from ..database.models import AuditEvent, Compound, Dataset, Project, Run, RunNode, Workflow
from ..workflow.registry import NodeRegistry, default_registry
from ..workflow.schema import validate_workflow


def create_project(session: Session, *, name: str, description: str = "", purpose: str = "") -> Project:
    name = name.strip()
    if not name:
        raise ValidationError("Project name must not be empty.")
    if len(name) > 200:
        raise ValidationError("Project name is too long (max 200 characters).")
    project = Project(id=new_project_id(), name=name, description=description.strip(), purpose=purpose.strip())
    session.add(project)
    audit(session, "project.create", "project", project.id, {"name": name})
    session.commit()
    session.refresh(project)
    return project


def new_project_id() -> str:
    from ..core.hashing import new_id

    return new_id("prj")


def list_projects(session: Session) -> list[dict]:
    rows = session.execute(
        select(
            Project,
            select(func.count(Compound.id)).where(Compound.project_id == Project.id).scalar_subquery(),
            select(func.count(Run.id)).where(Run.project_id == Project.id).scalar_subquery(),
            select(func.max(Run.created_at)).where(Run.project_id == Project.id).scalar_subquery(),
        ).order_by(Project.updated_at.desc())
    ).all()
    items = []
    for project, compound_count, run_count, last_run in rows:
        items.append(
            {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "purpose": project.purpose,
                "compound_count": int(compound_count or 0),
                "run_count": int(run_count or 0),
                "last_run_at": last_run.isoformat() + "Z" if isinstance(last_run, datetime) else None,
                "created_at": project.created_at.isoformat() + "Z",
                "updated_at": project.updated_at.isoformat() + "Z",
            }
        )
    return items


def get_project(session: Session, project_id: str) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise NotFoundError(f"Project '{project_id}' does not exist.")
    return project


def preview_project_deletion(session: Session, project_id: str, settings: Any = None) -> dict[str, Any]:
    from ..core.config import get_settings

    settings = settings or get_settings()
    project = get_project(session, project_id)

    run_ids = session.execute(select(Run.id).where(Run.project_id == project.id)).scalars().all()
    datasets = session.execute(select(Dataset).where(Dataset.project_id == project.id)).scalars().all()
    workflow_count = (
        session.execute(select(func.count(Workflow.id)).where(Workflow.project_id == project.id)).scalar() or 0
    )
    compound_count = (
        session.execute(select(func.count(Compound.id)).where(Compound.project_id == project.id)).scalar() or 0
    )

    disk_paths: list[str] = []
    total_disk_bytes = 0

    for rid in run_ids:
        rdir = settings.runs_dir / rid
        if rdir.exists():
            disk_paths.append(str(rdir))
            for f in rdir.rglob("*"):
                if f.is_file():
                    total_disk_bytes += f.stat().st_size

    prj_upload = settings.uploads_dir / project.id
    if prj_upload.exists():
        disk_paths.append(str(prj_upload))
        for f in prj_upload.rglob("*"):
            if f.is_file():
                total_disk_bytes += f.stat().st_size

    return {
        "project_id": project.id,
        "name": project.name,
        "datasets_count": len(datasets),
        "compounds_count": int(compound_count),
        "workflows_count": int(workflow_count),
        "runs_count": len(run_ids),
        "disk_paths": disk_paths,
        "total_disk_bytes": total_disk_bytes,
    }


def delete_project(
    session: Session,
    project_id: str,
    *,
    purge_files: bool = True,
    settings: Any = None,
) -> dict[str, Any]:
    import shutil

    from ..core.config import get_settings

    settings = settings or get_settings()
    preview = preview_project_deletion(session, project_id, settings)
    project = get_project(session, project_id)

    if purge_files:
        run_ids = session.execute(select(Run.id).where(Run.project_id == project.id)).scalars().all()
        for rid in run_ids:
            rdir = settings.runs_dir / rid
            if rdir.exists():
                shutil.rmtree(rdir, ignore_errors=True)

        prj_upload = settings.uploads_dir / project.id
        if prj_upload.exists():
            shutil.rmtree(prj_upload, ignore_errors=True)

    session.delete(project)
    audit(session, "project.delete", "project", project_id, {"name": project.name, "purged_files": purge_files})
    session.commit()
    return preview


def project_overview(session: Session, project_id: str) -> dict:
    project = get_project(session, project_id)
    datasets = (
        session.execute(select(Dataset).where(Dataset.project_id == project.id).order_by(Dataset.created_at.desc()))
        .scalars()
        .all()
    )
    runs = (
        session.execute(select(Run).where(Run.project_id == project.id).order_by(Run.created_at.desc()).limit(8))
        .scalars()
        .all()
    )
    workflows = (
        session.execute(select(Workflow).where(Workflow.project_id == project.id).order_by(Workflow.updated_at.desc()))
        .scalars()
        .all()
    )
    compound_count = (
        session.execute(select(func.count(Compound.id)).where(Compound.project_id == project.id)).scalar() or 0
    )
    return {
        "project": {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "purpose": project.purpose,
            "created_at": project.created_at.isoformat() + "Z",
            "updated_at": project.updated_at.isoformat() + "Z",
        },
        "counts": {
            "compounds": int(compound_count),
            "datasets": len(datasets),
            "runs": len(runs),
            "workflows": len(workflows),
        },
        "datasets": [
            {
                "id": dataset.id,
                "name": dataset.name,
                "source_format": dataset.source_format,
                "record_count": dataset.record_count,
                "imported_count": dataset.imported_count,
                "error_count": dataset.error_count,
                "created_at": dataset.created_at.isoformat() + "Z",
            }
            for dataset in datasets
        ],
        "runs": [run_summary(run) for run in runs],
        "workflows": [
            {
                "id": workflow.id,
                "name": workflow.name,
                "description": workflow.description,
                "content_hash": workflow.content_hash,
                "updated_at": workflow.updated_at.isoformat() + "Z",
            }
            for workflow in workflows
        ],
    }


def audit(
    session: Session,
    action: str,
    object_type: str,
    object_id: str | None,
    metadata: dict | None = None,
    *,
    outcome: str = "ok",
    actor: str = "local",
) -> None:
    session.add(
        AuditEvent(
            actor=actor,
            action=action,
            object_type=object_type,
            object_id=object_id,
            outcome=outcome,
            metadata_json=metadata or {},
        )
    )


def save_workflow(
    session: Session,
    *,
    project_id: str,
    payload: dict,
    registry: NodeRegistry | None = None,
    workflow_id: str | None = None,
) -> Workflow:
    registry = registry or default_registry()
    get_project(session, project_id)
    validated = validate_workflow(payload, registry=registry)
    spec = validated.spec
    duplicate = session.execute(
        select(Workflow).where(
            Workflow.project_id == project_id,
            Workflow.name == spec.name,
            Workflow.id != (workflow_id or ""),
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise ConflictError(f"A workflow named '{spec.name}' already exists in this project.")

    workflow = session.get(Workflow, workflow_id) if workflow_id else None
    if workflow_id and workflow is None:
        raise NotFoundError(f"Workflow '{workflow_id}' does not exist.")
    if workflow is None:
        from ..core.hashing import new_id

        workflow = Workflow(id=new_id("wfl"), project_id=project_id, name=spec.name, definition={}, content_hash="")
        session.add(workflow)
    workflow.name = spec.name
    workflow.description = spec.description
    workflow.schema_version = spec.schema_version
    workflow.definition = spec.model_dump(mode="json")
    workflow.content_hash = spec.content_hash()
    audit(session, "workflow.save", "workflow", workflow.id, {"name": spec.name})
    session.commit()
    session.refresh(workflow)
    return workflow


def delete_workflow(session: Session, workflow_id: str) -> None:
    workflow = session.get(Workflow, workflow_id)
    if workflow is None:
        raise NotFoundError(f"Workflow '{workflow_id}' does not exist.")
    audit(session, "workflow.delete", "workflow", workflow_id, {"name": workflow.name})
    session.delete(workflow)
    session.commit()


def run_summary(run: Run) -> dict:
    return {
        "id": run.id,
        "workflow_name": run.workflow_name,
        "status": run.status,
        "project_id": run.project_id,
        "dataset_id": run.dataset_id,
        "created_at": run.created_at.isoformat() + "Z",
        "started_at": run.started_at.isoformat() + "Z" if run.started_at else None,
        "finished_at": run.finished_at.isoformat() + "Z" if run.finished_at else None,
        "error": redact_text(run.error["message"])
        if isinstance(run.error, dict) and run.error.get("message")
        else None,
    }


def run_detail(session: Session, run_id: str) -> dict:
    run = session.get(Run, run_id)
    if run is None:
        raise NotFoundError(f"Run '{run_id}' does not exist.")
    nodes = session.execute(select(RunNode).where(RunNode.run_id == run.id).order_by(RunNode.id)).scalars().all()
    from ..database.models import Artifact

    artifacts = session.execute(select(Artifact).where(Artifact.run_id == run.id).order_by(Artifact.id)).scalars().all()
    return {
        **run_summary(run),
        "workflow_hash": run.workflow_hash,
        "workflow_snapshot": run.workflow_snapshot,
        "seed": run.seed,
        "attempt": run.attempt,
        "cancel_requested": run.cancel_requested,
        "manifest": run.manifest,
        "nodes": [
            {
                "node_id": node.node_id,
                "type": node.node_type,
                "status": node.status,
                "progress": node.progress,
                "cached": node.cached,
                "cache_key": node.cache_key,
                "summary": node.summary,
                "error": node.error,
                "started_at": node.started_at.isoformat() + "Z" if node.started_at else None,
                "finished_at": node.finished_at.isoformat() + "Z" if node.finished_at else None,
            }
            for node in nodes
        ],
        "artifacts": [
            {
                "id": artifact.id,
                "rel_path": artifact.rel_path,
                "node_id": artifact.node_id,
                "kind": artifact.kind,
                "media_type": artifact.media_type,
                "size_bytes": artifact.size_bytes,
                "sha256": artifact.sha256,
            }
            for artifact in artifacts
        ],
    }


def queued_run_count(session: Session) -> int:
    return int(session.execute(select(func.count(Run.id)).where(Run.status == "queued")).scalar() or 0)
