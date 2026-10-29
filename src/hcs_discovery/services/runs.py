"""Run creation, listing, event streaming and results queries."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.errors import NotFoundError, ValidationError
from ..core.hashing import new_id
from ..database.models import (
    Artifact,
    Compound,
    Dataset,
    Run,
    RunEvent,
    RunNode,
    RunResult,
    Workflow,
)
from ..workflow.registry import NodeRegistry, default_registry
from ..workflow.schema import validate_workflow
from .projects import audit, get_project, run_detail, run_summary


def create_run(
    session: Session,
    *,
    project_id: str,
    workflow: dict[str, Any],
    dataset_id: str,
    seed: int | None = None,
    registry: NodeRegistry | None = None,
    workflow_id: str | None = None,
) -> Run:
    registry = registry or default_registry()
    get_project(session, project_id)
    validated = validate_workflow(workflow, registry=registry)
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise NotFoundError(f"Dataset '{dataset_id}' does not exist.")
    if dataset.project_id != project_id:
        raise ValidationError("Dataset belongs to a different project.")
    compound_count = (
        session.execute(select(func.count(Compound.id)).where(Compound.dataset_id == dataset.id)).scalar() or 0
    )
    if not compound_count:
        raise ValidationError("Dataset contains no successfully imported compounds.")

    spec = validated.spec
    run = Run(
        id=new_id("run"),
        project_id=project_id,
        workflow_id=workflow_id,
        dataset_id=dataset.id,
        workflow_name=spec.name,
        workflow_snapshot=spec.model_dump(mode="json"),
        workflow_hash=spec.content_hash(),
        status="queued",
        parameters={"dataset_id": dataset.id},
        seed=seed,
    )
    session.add(run)
    for node in validated.order:
        session.add(
            RunNode(
                run_id=run.id,
                node_id=node.id,
                node_type=node.type,
                status="pending",
            )
        )
    audit(
        session,
        "run.create",
        "run",
        run.id,
        {"workflow": spec.name, "dataset": dataset.id, "compounds": int(compound_count)},
    )
    session.commit()
    session.refresh(run)
    return run


def create_run_from_saved_workflow(
    session: Session,
    *,
    workflow_id: str,
    dataset_id: str,
    seed: int | None = None,
    registry: NodeRegistry | None = None,
) -> Run:
    workflow = session.get(Workflow, workflow_id)
    if workflow is None:
        raise NotFoundError(f"Workflow '{workflow_id}' does not exist.")
    return create_run(
        session,
        project_id=workflow.project_id,
        workflow=workflow.definition,
        dataset_id=dataset_id,
        seed=seed,
        registry=registry,
        workflow_id=workflow.id,
    )


def list_runs(session: Session, *, project_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    query = select(Run)
    if project_id:
        query = query.where(Run.project_id == project_id)
    runs = session.execute(query.order_by(Run.created_at.desc()).limit(max(1, min(limit, 200)))).scalars().all()
    return [run_summary(run) for run in runs]


def get_run(session: Session, run_id: str) -> Run:
    run = session.get(Run, run_id)
    if run is None:
        raise NotFoundError(f"Run '{run_id}' does not exist.")
    return run


def get_run_detail(session: Session, run_id: str) -> dict[str, Any]:
    return run_detail(session, run_id)


def events_after(session: Session, run_id: str, after_seq: int = 0, limit: int = 500) -> list[dict[str, Any]]:
    get_run(session, run_id)
    events = (
        session.execute(
            select(RunEvent)
            .where(RunEvent.run_id == run_id, RunEvent.seq > after_seq)
            .order_by(RunEvent.seq)
            .limit(max(1, min(limit, 2000)))
        )
        .scalars()
        .all()
    )
    return [
        {
            "seq": event.seq,
            "ts": event.ts.isoformat() + "Z",
            "type": event.type,
            "level": event.level,
            "message": event.message,
            "node_id": event.node_id,
            "data": event.data,
        }
        for event in events
    ]


def artifact_path(session: Session, run_id: str, artifact_id: int) -> tuple[Artifact, str]:
    artifact = session.get(Artifact, artifact_id)
    if artifact is None or artifact.run_id != run_id:
        raise NotFoundError("Artifact does not exist for this run.")
    return artifact, artifact.rel_path


def _result_columns(run: Run) -> list[dict[str, Any]]:
    """Return column metadata, falling back to the persisted results artifact.

    Runs executed before column metadata was copied into the manifest still have
    ``results.json`` on disk; reading it keeps old runs fully inspectable.
    """

    if isinstance(run.manifest, dict):
        columns = run.manifest.get("columns")
        if isinstance(columns, list) and columns:
            return columns
    path = get_settings().runs_dir / run.id / "results.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    columns = payload.get("columns") if isinstance(payload, dict) else None
    return columns if isinstance(columns, list) else []


def results_page(
    session: Session,
    run_id: str,
    *,
    sort: str = "rank",
    order: str = "asc",
    only_passing: bool = False,
    limit: int = 100,
    offset: int = 0,
    q: str | None = None,
) -> dict[str, Any]:
    if order not in {"asc", "desc"}:
        raise ValidationError("Result order must be 'asc' or 'desc'.")
    run = get_run(session, run_id)

    filters = [RunResult.run_id == run.id]
    if only_passing:
        filters.append(RunResult.rejected.is_(False))
    if q:
        needle = f"%{q.lower()}%"
        filters.append(
            or_(
                func.lower(Compound.name).like(needle),
                func.lower(Compound.isomeric_smiles).like(needle),
                func.lower(RunResult.compound_id).like(needle),
            )
        )

    join_on = Compound.id == RunResult.compound_id
    total = session.execute(
        select(func.count()).select_from(RunResult).outerjoin(Compound, join_on).where(*filters)
    ).scalar_one()

    sortable = {
        "rank": RunResult.rank,
        "composite_score": RunResult.composite_score,
        "pareto_front": RunResult.pareto_front,
    }
    sort_column = sortable.get(sort)
    if sort_column is None:
        # Metric values live in the JSON payload; cast keeps numeric ordering while
        # still allowing NULLs to sort last on both directions.
        sort_column = RunResult.metrics[sort].as_float()

    direction = sort_column.asc() if order == "asc" else sort_column.desc()
    statement = (
        select(RunResult, Compound)
        .outerjoin(Compound, join_on)
        .where(*filters)
        .order_by(direction.nulls_last(), RunResult.id.asc())
        .offset(offset)
        .limit(max(1, min(limit, 2000)))
    )
    rows = session.execute(statement).all()
    items: list[dict[str, Any]] = [
        {
            "compound_id": result.compound_id,
            "name": compound.name if compound else None,
            "smiles": compound.isomeric_smiles if compound else None,
            "rank": result.rank,
            "composite_score": result.composite_score,
            "pareto_front": result.pareto_front,
            "rejected": result.rejected,
            "reasons": result.reasons,
            "metrics": result.metrics,
        }
        for result, compound in rows
    ]
    columns = _result_columns(run)
    return {
        "run": run_summary(run),
        "total": total,
        "limit": limit,
        "offset": offset,
        "sort": sort,
        "order": order,
        "columns": columns,
        "items": items,
    }
