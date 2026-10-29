"""Run submission, monitoring (SSE), results, artifacts and reports."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session, sessionmaker

from ... import services
from ...core.config import Settings
from ...core.errors import NotFoundError, ValidationError
from ...core.paths import safe_join
from ...database.models import Run
from ...jobs.queue import request_cancel
from ...reports.render import (
    export_report,
    load_report_data,
    render_html,
    render_json,
    render_markdown,
    results_csv_path,
)
from ..deps import db, settings_dep
from ..schemas import CancelResponse, RunCreateRequest

router = APIRouter(prefix="/api/v1", tags=["runs"])

TERMINAL = {"succeeded", "failed", "cancelled"}


@router.post("/runs", status_code=202)
def create_run(payload: RunCreateRequest, request: Request, session: Session = Depends(db)) -> dict:
    if payload.workflow_id:
        run = services.create_run_from_saved_workflow(
            session,
            workflow_id=payload.workflow_id,
            dataset_id=payload.dataset_id,
            seed=payload.seed,
            registry=request.app.state.registry,
        )
    elif payload.workflow:
        run = services.create_run(
            session,
            project_id=payload.project_id,
            workflow=payload.workflow,
            dataset_id=payload.dataset_id,
            seed=payload.seed,
            registry=request.app.state.registry,
        )
    else:
        raise ValidationError("Provide either a workflow definition or a workflow_id.")
    return services.get_run_detail(session, run.id)


@router.get("/runs")
def list_runs(
    project_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(db),
) -> dict:
    return {"items": services.list_runs(session, project_id=project_id, limit=limit)}


@router.get("/runs/{run_id}")
def get_run(run_id: str, session: Session = Depends(db)) -> dict:
    return services.get_run_detail(session, run_id)


@router.post("/runs/{run_id}/cancel", response_model=CancelResponse)
def cancel_run(run_id: str, session: Session = Depends(db)) -> CancelResponse:
    run = request_cancel(session, run_id)
    return CancelResponse(id=run.id, status=run.status, cancel_requested=run.cancel_requested)


@router.get("/runs/{run_id}/events")
def get_events(
    run_id: str,
    after: int = Query(default=0, ge=0),
    limit: int = Query(default=500, ge=1, le=2000),
    session: Session = Depends(db),
) -> dict:
    events = services.events_after(session, run_id, after_seq=after, limit=limit)
    return {
        "items": events,
        "last_seq": events[-1]["seq"] if events else after,
        "run": services.run_summary(services.get_run(session, run_id)),
    }


@router.get("/runs/{run_id}/events/stream")
def stream_events(run_id: str, request: Request, after: int = Query(default=0, ge=0)) -> StreamingResponse:
    factory: sessionmaker[Session] = request.app.state.session_factory

    async def generator():
        last = after
        deadline = time.monotonic() + 900
        with factory() as session:
            if session.get(Run, run_id) is None:
                yield 'event: error\ndata: {"message":"run not found"}\n\n'
                return
        while time.monotonic() < deadline:
            if await request.is_disconnected():
                return
            with factory() as session:
                events = services.events_after(session, run_id, after_seq=last)
                run = services.get_run(session, run_id)
                status = run.status
            for event in events:
                last = event["seq"]
                payload = json.dumps(event, ensure_ascii=False)
                yield f"id: {last}\nevent: run-event\ndata: {payload}\n\n"
            if status in TERMINAL and not events:
                yield f"event: done\ndata: {json.dumps({'status': status})}\n\n"
                return
            yield ": keep-alive\n\n"
            await asyncio.sleep(0.4)
        yield 'event: timeout\ndata: {"message":"stream window ended"}\n\n'

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/runs/{run_id}/results")
def results(
    run_id: str,
    sort: str = Query(default="rank"),
    order: str = Query(default="asc", pattern="^(asc|desc)$"),
    only_passing: bool = Query(default=False),
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=100, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(db),
) -> dict:
    return services.results_page(
        session,
        run_id,
        sort=sort,
        order=order,
        only_passing=only_passing,
        limit=limit,
        offset=offset,
        q=q,
    )


@router.get("/runs/{run_id}/artifacts/{artifact_id}")
def download_artifact(
    run_id: str,
    artifact_id: int,
    session: Session = Depends(db),
    settings: Settings = Depends(settings_dep),
) -> FileResponse:
    artifact, rel_path = services.artifact_path(session, run_id, artifact_id)
    path: Path = safe_join(settings.runs_dir, run_id, *rel_path.split("/"))
    if not path.exists():
        raise NotFoundError("Artifact file is missing on disk.")
    return FileResponse(
        path,
        media_type=artifact.media_type,
        filename=Path(rel_path).name,
        headers={"X-Artifact-SHA256": artifact.sha256},
    )


@router.get("/runs/{run_id}/report")
def report(
    run_id: str,
    format: str = Query(default="html", pattern="^(html|markdown|md|json|csv)$"),
    download: bool = Query(default=False),
    session: Session = Depends(db),
    settings: Settings = Depends(settings_dep),
) -> Response:
    fmt = "markdown" if format == "md" else format
    data = load_report_data(session, run_id)
    if fmt == "html":
        content = render_html(data)
        media = "text/html; charset=utf-8"
    elif fmt == "markdown":
        content = render_markdown(data)
        media = "text/markdown; charset=utf-8"
    elif fmt == "json":
        content = render_json(data)
        media = "application/json"
    else:
        path = results_csv_path(settings, run_id)
        if not path.exists():
            raise NotFoundError("This run has no results.csv artifact.")
        content = path.read_text(encoding="utf-8")
        media = "text/csv; charset=utf-8"
    headers = {"Content-Disposition": f'attachment; filename="{run_id}.{fmt}"'} if download else {}
    return Response(content=content, media_type=media, headers=headers)


@router.post("/runs/{run_id}/retry", status_code=202)
def retry_run(run_id: str, request: Request, session: Session = Depends(db)) -> dict:
    source = services.get_run(session, run_id)
    if not source.dataset_id:
        raise ValidationError("Run has no dataset to retry with.")
    run = services.create_run(
        session,
        project_id=source.project_id,
        workflow=source.workflow_snapshot,
        dataset_id=source.dataset_id,
        seed=source.seed,
        registry=request.app.state.registry,
    )
    return services.get_run_detail(session, run.id)


@router.get("/runs/{run_id}/export/{fmt}")
def export(
    run_id: str,
    fmt: str,
    session: Session = Depends(db),
    settings: Settings = Depends(settings_dep),
) -> Response:
    if fmt not in {"markdown", "html", "json", "csv"}:
        raise ValidationError("Unsupported export format.")
    target = settings.data_dir / "exports" / f"{run_id}.{fmt}"
    export_report(session, settings, run_id, fmt, target)
    return FileResponse(target, filename=target.name)
