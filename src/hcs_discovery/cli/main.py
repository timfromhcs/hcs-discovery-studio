"""Headless CLI. The CLI and the API share the same service layer."""

from __future__ import annotations

import contextlib
import json
import shutil
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer
import uvicorn
from sqlalchemy import select

from .. import CREDIT, PRODUCT_NAME, __version__
from ..core.config import Settings, get_settings
from ..core.doctor import run_diagnostics
from ..core.errors import AppError, NotFoundError, ValidationError
from ..core.logging import configure_logging
from ..database.base import get_session_factory, init_db
from ..database.migrations import current_revision
from ..datasets.readers import ImportOptions
from ..jobs.queue import request_cancel
from ..jobs.worker import Worker, run_worker_loop
from ..services import (
    create_project,
    create_run,
    create_run_from_saved_workflow,
    dataset_rows,
    delete_dataset,
    delete_project,
    delete_workflow,
    get_run,
    import_dataset,
    list_datasets,
    list_models,
    list_projects,
    list_runs,
    results_page,
    run_detail,
    save_workflow,
    validate_molecules,
)
from ..workflow.schema import validate_workflow
from ..workflow.templates import templates

app = typer.Typer(
    help=f"{PRODUCT_NAME} - {CREDIT}",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_show_locals=False,
)
project_app = typer.Typer(help="Project management.", no_args_is_help=True)
dataset_app = typer.Typer(help="Dataset import and inspection.", no_args_is_help=True)
workflow_app = typer.Typer(help="Workflow validation and submission.", no_args_is_help=True)
run_app = typer.Typer(help="Run monitoring.", no_args_is_help=True)
report_app = typer.Typer(help="Report export.", no_args_is_help=True)
models_app = typer.Typer(help="Model/engine registry.", no_args_is_help=True)
config_app = typer.Typer(help="Configuration.", no_args_is_help=True)
cache_app = typer.Typer(help="Node cache.", no_args_is_help=True)
compounds_app = typer.Typer(help="Molecule utilities.", no_args_is_help=True)
db_app = typer.Typer(help="Database maintenance.", no_args_is_help=True)

for name, sub in (
    ("project", project_app),
    ("dataset", dataset_app),
    ("workflow", workflow_app),
    ("run", run_app),
    ("report", report_app),
    ("models", models_app),
    ("config", config_app),
    ("cache", cache_app),
    ("compounds", compounds_app),
    ("db", db_app),
):
    app.add_typer(sub, name=name)


def _force_utf8() -> None:
    """Windows consoles default to a legacy code page; never crash on the brand credit."""
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]


_force_utf8()


@dataclass
class State:
    json: bool = False


def _state(ctx: typer.Context) -> State:
    return ctx.obj if isinstance(ctx.obj, State) else State()


@app.callback()
def main(
    ctx: typer.Context,
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON on stdout; logs go to stderr."),
    debug: bool = typer.Option(False, "--debug", help="Show redacted internal error details."),
) -> None:
    ctx.obj = State(json=json_output)
    configure_logging(level="DEBUG" if debug else "INFO", json_output=True)


def _print(ctx: typer.Context, payload: Any, human: str) -> None:
    if _state(ctx).json:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    else:
        typer.echo(human)


def _fail(exc: AppError) -> None:
    typer.echo(json.dumps({"error": exc.to_dict()}, indent=2), err=True)
    raise typer.Exit(exc.exit_code)


def _run_cli(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except AppError as exc:
        _fail(exc)


# --------------------------------------------------------------------------- doctor / serve / worker
@app.command()
def doctor(
    ctx: typer.Context,
    check_vulkan: bool = typer.Option(False, "--check-vulkan", help="Probe Vulkan devices."),
    check_providers: bool = typer.Option(False, "--check-providers", help="Probe the configured LLM provider."),
) -> None:
    """Report what actually works on this machine."""
    settings = get_settings()
    report = run_diagnostics(settings, check_vulkan=check_vulkan, check_providers=check_providers)
    if _state(ctx).json:
        typer.echo(json.dumps(report, indent=2))
        raise typer.Exit(0 if report["status"] != "error" else 1)
    typer.echo(f"{PRODUCT_NAME} {__version__} - diagnostics ({report['status']})")
    typer.echo(f"Python {report['environment']['python']} | {report['environment']['platform']}")
    typer.echo("")
    for check in report["checks"]:
        marker = {"ok": "[ok]  ", "warning": "[warn]", "error": "[fail]"}.get(check["status"], "[?]   ")
        typer.echo(f"{marker} {check['label']}: {check['detail']}")
        if check.get("remediation") and check["status"] != "ok":
            typer.echo(f"        -> {check['remediation']}")
    typer.echo("")
    typer.echo(CREDIT)
    raise typer.Exit(0 if report["status"] != "error" else 1)


@app.command()
def serve(
    ctx: typer.Context,
    host: str = typer.Option(None, help="Bind address (default from settings, loopback)."),
    port: int = typer.Option(None, help="Port (default 8787)."),
    worker: bool = typer.Option(True, "--worker/--no-worker", help="Run an embedded worker in this process."),
) -> None:
    """Start the local web application."""
    from ..api.app import create_app

    settings = Settings(
        data_dir=get_settings().data_dir,
        host=host or get_settings().host,
        port=port or get_settings().port,
        network_policy=get_settings().network_policy,
        api_token=get_settings().api_token,
    )
    settings.ensure_dirs()
    application = create_app(settings)
    stop_event: threading.Event | None = None
    if worker:
        stop_event = threading.Event()
        thread = threading.Thread(
            target=run_worker_loop,
            kwargs={"settings": settings, "concurrency": 1, "stop_event": stop_event},
            daemon=True,
            name="hcs-worker",
        )
        thread.start()
    typer.echo(f"{PRODUCT_NAME} listening on http://{settings.host}:{settings.port}")
    try:
        uvicorn.run(application, host=settings.host, port=settings.port, log_level="info")
    finally:
        if stop_event is not None:
            stop_event.set()


@app.command()
def worker(
    ctx: typer.Context,
    concurrency: int = typer.Option(1, min=1, max=8, help="Parallel workers (SQLite: keep low)."),
    once: bool = typer.Option(False, "--once", help="Drain the queue and exit (CI/demo friendly)."),
) -> None:
    """Run a standalone job worker."""
    settings = get_settings()
    init_db(settings)
    if _state(ctx).json:
        typer.echo(json.dumps({"worker": "started", "concurrency": concurrency, "once": once}))
    if once:
        instance = Worker(settings=settings, worker_id="worker-once")
        processed = 0
        while (run := instance.run_once()) is not None:
            processed += 1
            if not _state(ctx).json:
                typer.echo(f"processed {run.id}")
        if _state(ctx).json:
            typer.echo(json.dumps({"worker": "stopped", "processed": processed}))
        return
    try:
        run_worker_loop(settings, concurrency=concurrency)
    except KeyboardInterrupt:
        typer.echo("worker stopped", err=True)


# --------------------------------------------------------------------------- projects
@project_app.command("list")
def project_list(ctx: typer.Context) -> None:
    with get_session_factory()() as session:
        items = list_projects(session)
    if _state(ctx).json:
        typer.echo(json.dumps({"items": items}, indent=2))
        return
    if not items:
        typer.echo('No projects yet. Create one with: hcs-discovery project create --name "My project"')
        return
    for item in items:
        typer.echo(f"{item['id']}  {item['name']}  ({item['compound_count']} compounds, {item['run_count']} runs)")


@project_app.command("create")
def project_create(
    ctx: typer.Context,
    name: str = typer.Option(..., help="Project name."),
    description: str = typer.Option("", help="Short description."),
) -> None:
    with get_session_factory()() as session:
        project = _run_cli(create_project, session, name=name, description=description)
    _print(
        ctx,
        {"id": project.id, "name": project.name},
        f"Created project {project.id} ({project.name})",
    )


@project_app.command("show")
def project_show(ctx: typer.Context, project_id: str) -> None:
    from ..services import project_overview

    with get_session_factory()() as session:
        overview = _run_cli(project_overview, session, project_id)
    if _state(ctx).json:
        typer.echo(json.dumps(overview, indent=2))
    else:
        typer.echo(f"{overview['project']['name']} ({overview['project']['id']})")
        typer.echo(json.dumps(overview["counts"], indent=2))


@project_app.command("delete")
def project_delete(
    ctx: typer.Context,
    project_id: str,
    yes: bool = typer.Option(False, "--yes", help="Skip the confirmation prompt."),
) -> None:
    """Delete a project and its database records. Run directories are kept."""
    if not yes:
        typer.confirm(f"Delete project {project_id} and all of its database records?", abort=True)
    with get_session_factory()() as session:
        _run_cli(delete_project, session, project_id)
    _print(ctx, {"id": project_id, "status": "deleted"}, f"Deleted project {project_id}. Run directories were kept.")


# --------------------------------------------------------------------------- datasets
@dataset_app.command("import")
def dataset_import(
    ctx: typer.Context,
    file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    project: str = typer.Option(..., "--project", help="Project id."),
    format: str = typer.Option("auto", help="csv|sdf|smi|auto"),
    smiles_column: str = typer.Option("", help="Structure column (CSV)."),
    name_column: str = typer.Option("", help="Name column (CSV)."),
    id_column: str = typer.Option("", help="Source id column (CSV)."),
    keep_salts: bool = typer.Option(False, "--keep-salts", help="Do not strip counter-ions."),
    neutralize: bool = typer.Option(False, help="Neutralise formal charges."),
    canonical_tautomer: bool = typer.Option(False, help="Apply canonical tautomer."),
) -> None:
    """Import a molecule library into a project."""
    settings = get_settings()
    options = ImportOptions(
        smiles_column=smiles_column or None,
        name_column=name_column or None,
        id_column=id_column or None,
        strip_salts=not keep_salts,
        neutralize=neutralize,
        canonical_tautomer=canonical_tautomer,
        max_rows=settings.max_import_rows,
    )
    with get_session_factory()() as session:
        dataset = _run_cli(
            import_dataset,
            session=session,
            settings=settings,
            project_id=project,
            filename=file.name,
            data=file.read_bytes(),
            fmt=format,
            options=options,
        )
        payload = {
            "id": dataset.id,
            "name": dataset.name,
            "records": dataset.record_count,
            "imported": dataset.imported_count,
            "errors": dataset.error_count,
        }
    _print(
        ctx,
        payload,
        f"Imported {payload['imported']}/{payload['records']} records into {dataset.id} "
        f"({payload['errors']} error rows).",
    )


@dataset_app.command("list")
def dataset_list(ctx: typer.Context, project: str = typer.Option(..., "--project")) -> None:
    with get_session_factory()() as session:
        items = list_datasets(session, project)
    if _state(ctx).json:
        typer.echo(json.dumps({"items": items}, indent=2))
        return
    for item in items:
        typer.echo(
            f"{item['id']}  {item['name']}  {item['imported_count']}/{item['record_count']} imported, "
            f"{item['error_count']} errors"
        )


@dataset_app.command("errors")
def dataset_errors(ctx: typer.Context, dataset_id: str, limit: int = typer.Option(100, min=1, max=1000)) -> None:
    with get_session_factory()() as session:
        payload = _run_cli(dataset_rows, session, dataset_id, status="error", limit=limit)
    if _state(ctx).json:
        typer.echo(json.dumps(payload, indent=2))
        return
    if not payload["items"]:
        typer.echo("No row-level errors.")
    for row in payload["items"]:
        typer.echo(f"row {row['row_index']}: {row['error']}")


@dataset_app.command("delete")
def dataset_delete(
    ctx: typer.Context,
    dataset_id: str,
    yes: bool = typer.Option(False, "--yes", help="Skip the confirmation prompt."),
) -> None:
    """Delete a dataset and its imported compounds."""
    if not yes:
        typer.confirm(f"Delete dataset {dataset_id} and its imported compounds?", abort=True)
    with get_session_factory()() as session:
        _run_cli(delete_dataset, session, dataset_id)
    _print(ctx, {"id": dataset_id, "status": "deleted"}, f"Deleted dataset {dataset_id}.")


@compounds_app.command("validate")
def compounds_validate(
    ctx: typer.Context,
    file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    format: str = typer.Option("auto"),
    smiles_column: str = typer.Option(""),
    output: Path | None = typer.Option(None, help="Write the per-row JSON report to this file."),
) -> None:
    """Validate and canonicalise a molecule file without touching the database."""
    payload = _run_cli(
        validate_molecules,
        file.read_bytes(),
        file.name,
        fmt=format,
        options=ImportOptions(smiles_column=smiles_column or None),
    )
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if _state(ctx).json:
        typer.echo(json.dumps(payload if not output else {**payload, "output": str(output)}, indent=2))
    else:
        typer.echo(f"{payload['imported_count']}/{payload['record_count']} valid, {payload['error_count']} errors.")
        for row in payload["rows"]:
            if row["status"] == "error":
                typer.echo(f"row {row['row_index']}: {row['error']}")
    raise typer.Exit(0 if payload["error_count"] == 0 else 1)


# --------------------------------------------------------------------------- workflows
@workflow_app.command("list")
def workflow_list(ctx: typer.Context, project: str | None = typer.Option(None, "--project")) -> None:
    from ..database.models import Workflow

    with get_session_factory()() as session:
        query = select(Workflow)
        if project:
            query = query.where(Workflow.project_id == project)
        workflows = session.execute(query.order_by(Workflow.updated_at.desc())).scalars().all()
        items = [
            {"id": w.id, "name": w.name, "project_id": w.project_id, "content_hash": w.content_hash} for w in workflows
        ]
    if _state(ctx).json:
        typer.echo(json.dumps({"items": items}, indent=2))
        return
    for item in items:
        typer.echo(f"{item['id']}  {item['name']}  ({item['content_hash'][:12]})")
    if not items:
        typer.echo("No saved workflows. Use `hcs-discovery workflow templates` or the UI.")


@workflow_app.command("templates")
def workflow_templates(
    ctx: typer.Context,
    export: Path | None = typer.Option(None, help="Directory to write YAML files to."),
) -> None:
    import yaml as yaml_module

    items = templates()
    if export:
        export.mkdir(parents=True, exist_ok=True)
        for item in items:
            (export / f"{item['id']}.yaml").write_text(yaml_module.safe_dump(item, sort_keys=False), encoding="utf-8")
    if _state(ctx).json:
        typer.echo(json.dumps({"items": items}, indent=2))
        return
    for item in items:
        typer.echo(f"{item['id']}: {item['name']}")


@workflow_app.command("show")
def workflow_show(ctx: typer.Context, workflow_id: str) -> None:
    """Print a saved workflow definition."""
    from ..database.models import Workflow

    with get_session_factory()() as session:
        workflow = session.get(Workflow, workflow_id)
        if workflow is None:
            _fail(NotFoundError(f"Workflow '{workflow_id}' does not exist."))
            return
        payload = {
            "id": workflow.id,
            "project_id": workflow.project_id,
            "name": workflow.name,
            "description": workflow.description,
            "content_hash": workflow.content_hash,
            "definition": workflow.definition,
        }
        hash_prefix = (workflow.content_hash or "")[:16]
    if _state(ctx).json:
        typer.echo(json.dumps(payload, indent=2))
        return
    typer.echo(f"{payload['name']} ({payload['id']}) hash={hash_prefix}")
    typer.echo(json.dumps(payload["definition"], indent=2))


@workflow_app.command("save")
def workflow_save(
    ctx: typer.Context,
    file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    project: str = typer.Option(..., "--project", help="Project id."),
    workflow_id: str = typer.Option("", "--id", help="Update this saved workflow instead of creating one."),
) -> None:
    """Validate and save a workflow definition."""
    payload = _load_workflow(file, None)
    with get_session_factory()() as session:
        workflow = _run_cli(
            save_workflow,
            session,
            project_id=project,
            payload=payload,
            workflow_id=workflow_id or None,
        )
    _print(
        ctx,
        {"id": workflow.id, "name": workflow.name, "content_hash": workflow.content_hash},
        f"Saved workflow {workflow.id} ({workflow.name}) hash={workflow.content_hash[:16]}",
    )


@workflow_app.command("delete")
def workflow_delete(
    ctx: typer.Context,
    workflow_id: str,
    yes: bool = typer.Option(False, "--yes", help="Skip the confirmation prompt."),
) -> None:
    """Delete a saved workflow. Existing runs keep their snapshots."""
    if not yes:
        typer.confirm(f"Delete workflow {workflow_id}? Existing runs keep their snapshots.", abort=True)
    with get_session_factory()() as session:
        _run_cli(delete_workflow, session, workflow_id)
    _print(ctx, {"id": workflow_id, "status": "deleted"}, f"Deleted workflow {workflow_id}.")


def _load_workflow(file: Path | None, workflow_id: str | None) -> dict[str, Any]:
    import yaml as yaml_module

    if workflow_id:
        with get_session_factory()() as session:
            from ..database.models import Workflow

            workflow = session.get(Workflow, workflow_id)
            if workflow is None:
                raise NotFoundError(f"Workflow '{workflow_id}' does not exist.")
            return workflow.definition
    if file is None:
        raise ValidationError("Provide a workflow file or --workflow-id.")
    if not file.exists():
        raise ValidationError(f"Workflow file '{file}' does not exist.")
    payload = yaml_module.safe_load(file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValidationError("Workflow file must contain a YAML/JSON mapping.")
    return payload


@workflow_app.command("validate")
def workflow_validate(ctx: typer.Context, file: Path = typer.Argument(..., exists=True, dir_okay=False)) -> None:
    payload = _load_workflow(file, None)
    validated = _run_cli(validate_workflow, payload)
    result = {
        "valid": True,
        "name": validated.spec.name,
        "content_hash": validated.content_hash,
        "order": [node.id for node in validated.order],
    }
    _print(
        ctx,
        result,
        f"Valid workflow '{validated.spec.name}' with {len(validated.order)} node(s). "
        f"hash={validated.content_hash[:16]}",
    )


@workflow_app.command("run")
def workflow_run(
    ctx: typer.Context,
    file: Path | None = typer.Argument(None, exists=True, dir_okay=False),
    project: str = typer.Option(..., "--project"),
    dataset: str = typer.Option(..., "--dataset"),
    workflow_id: str = typer.Option("", "--workflow-id", help="Run a saved workflow instead of a file."),
    follow: bool = typer.Option(True, "--follow/--no-follow"),
    seed: int | None = typer.Option(None, help="Recorded seed for reproducibility."),
) -> None:
    """Submit a workflow run and stream its progress."""
    payload = _load_workflow(file, workflow_id or None)
    with get_session_factory()() as session:
        if workflow_id:
            run = _run_cli(
                create_run_from_saved_workflow,
                session,
                workflow_id=workflow_id,
                dataset_id=dataset,
                seed=seed,
            )
        else:
            run = _run_cli(
                create_run,
                session,
                project_id=project,
                workflow=payload,
                dataset_id=dataset,
                seed=seed,
            )
        run_id = run.id
    if _state(ctx).json and not follow:
        typer.echo(json.dumps({"run_id": run_id, "status": "queued"}))
        return
    if not _state(ctx).json:
        typer.echo(f"Run {run_id} queued. Waiting for a worker...")
    status = _follow_run(run_id, json_mode=_state(ctx).json) if follow else "queued"
    if status != "succeeded":
        raise typer.Exit(8 if status == "failed" else 7 if status == "cancelled" else 1)


def _follow_run(run_id: str, *, json_mode: bool) -> str:
    last = 0
    with get_session_factory()() as session:
        while True:
            from ..services import events_after

            events = events_after(session, run_id, after_seq=last)
            run = get_run(session, run_id)
            for event in events:
                last = event["seq"]
                if json_mode:
                    typer.echo(json.dumps(event, ensure_ascii=False))
                elif event["type"].startswith("node.") or event["type"].startswith("run."):
                    stamp = time.strftime("%H:%M:%S", time.localtime())
                    typer.echo(f"[{stamp}] {event['level']:<7} {event['type']:<22} {event['message']}")
            if run.status in {"succeeded", "failed", "cancelled"} and not events:
                session.refresh(run)
                if not json_mode:
                    typer.echo(f"Run finished with status: {run.status}")
                    if run.error:
                        typer.echo(f"Error: {run.error.get('message')}", err=True)
                else:
                    typer.echo(json.dumps({"run_id": run.id, "status": run.status, "error": run.error}))
                return run.status
            time.sleep(0.4)


# --------------------------------------------------------------------------- runs
@run_app.command("status")
def run_status(ctx: typer.Context, run_id: str) -> None:
    with get_session_factory()() as session:
        detail = _run_cli(run_detail, session, run_id)
    if _state(ctx).json:
        typer.echo(json.dumps(detail, indent=2))
        return
    typer.echo(f"{detail['id']}  {detail['status']}  {detail['workflow_name']}")
    for node in detail["nodes"]:
        cached = " (cached)" if node["cached"] else ""
        typer.echo(f"  - {node['node_id']:<20} {node['status']:<10}{cached}")


@run_app.command("logs")
def run_logs(ctx: typer.Context, run_id: str, follow: bool = typer.Option(False, "--follow")) -> None:
    if follow:
        _follow_run(run_id, json_mode=_state(ctx).json)
        return
    with get_session_factory()() as session:
        from ..services import events_after

        events = events_after(session, run_id)
    for event in events:
        if _state(ctx).json:
            typer.echo(json.dumps(event, ensure_ascii=False))
        else:
            typer.echo(f"{event['ts']} {event['level']:<7} {event['message']}")


@run_app.command("cancel")
def run_cancel(ctx: typer.Context, run_id: str) -> None:
    with get_session_factory()() as session:
        run = _run_cli(request_cancel, session, run_id)
    _print(
        ctx,
        {"id": run.id, "status": run.status, "cancel_requested": run.cancel_requested},
        f"Cancellation requested for {run.id} (status: {run.status}).",
    )


@run_app.command("retry")
def run_retry(
    ctx: typer.Context,
    run_id: str,
    follow: bool = typer.Option(True, "--follow/--no-follow"),
) -> None:
    """Re-submit a run with its original workflow snapshot and dataset."""
    with get_session_factory()() as session:
        source = _run_cli(get_run, session, run_id)
        if not source.dataset_id:
            _fail(ValidationError("Run has no dataset to retry with."))
            return
        run = _run_cli(
            create_run,
            session,
            project_id=source.project_id,
            workflow=source.workflow_snapshot,
            dataset_id=source.dataset_id,
            seed=source.seed,
        )
        new_id = run.id
    if _state(ctx).json and not follow:
        typer.echo(json.dumps({"run_id": new_id, "status": "queued"}))
        return
    if not _state(ctx).json:
        typer.echo(f"Retry {new_id} queued. Waiting for a worker...")
    status = _follow_run(new_id, json_mode=_state(ctx).json) if follow else "queued"
    if status != "succeeded":
        raise typer.Exit(8 if status == "failed" else 7 if status == "cancelled" else 1)


@run_app.command("artifacts")
def run_artifacts(ctx: typer.Context, run_id: str, output: Path | None = typer.Option(None, "--output")) -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        detail = _run_cli(run_detail, session, run_id)
    if output:
        output.mkdir(parents=True, exist_ok=True)
        for artifact in detail["artifacts"]:
            source = settings.runs_dir / run_id / Path(artifact["rel_path"])
            if source.exists():
                destination = output / Path(artifact["rel_path"]).name
                shutil.copy2(source, destination)
    if _state(ctx).json:
        typer.echo(json.dumps({"items": detail["artifacts"], "output": str(output) if output else None}, indent=2))
        return
    for artifact in detail["artifacts"]:
        typer.echo(f"{artifact['rel_path']}  {artifact['size_bytes']} bytes  sha256={artifact['sha256'][:16]}")
    if output:
        typer.echo(f"Copied artifacts to {output}")


@run_app.command("results")
def run_results(ctx: typer.Context, run_id: str, limit: int = typer.Option(20, min=1, max=2000)) -> None:
    with get_session_factory()() as session:
        payload = _run_cli(results_page, session, run_id, limit=limit)
    if _state(ctx).json:
        typer.echo(json.dumps(payload, indent=2))
        return
    typer.echo(f"{'rank':<6}{'score':<9}{'pareto':<7}{'name':<28}smiles")
    for item in payload["items"]:
        typer.echo(
            f"{item['rank'] or '-'!s:<6}{item['composite_score'] if item['composite_score'] is not None else '-':<9}"
            f"{item['pareto_front'] or '-'!s:<7}{(item['name'] or '')[:26]:<28}{item['smiles']}"
        )


@run_app.command("list")
def run_list(
    ctx: typer.Context,
    project: str | None = typer.Option(None, "--project"),
    limit: int = typer.Option(20, min=1, max=200),
) -> None:
    with get_session_factory()() as session:
        items = list_runs(session, project_id=project, limit=limit)
    if _state(ctx).json:
        typer.echo(json.dumps({"items": items}, indent=2))
        return
    for item in items:
        typer.echo(f"{item['id']}  {item['status']:<10} {item['workflow_name']}  {item['created_at']}")


# --------------------------------------------------------------------------- reports / models / config / cache
@report_app.command("export")
def report_export(
    ctx: typer.Context,
    run_id: str,
    format: str = typer.Option("html", help="html|markdown|json|csv"),
    output: Path = typer.Option(..., "--output"),
) -> None:
    from ..reports.render import export_report

    settings = get_settings()
    fmt = "markdown" if format == "md" else format
    with get_session_factory()() as session:
        target = _run_cli(export_report, session, settings, run_id, fmt, output)
    _print(ctx, {"output": str(target), "format": fmt, "run_id": run_id}, f"Report written to {target}")


@models_app.command("list")
def models_list(ctx: typer.Context, probe: bool = typer.Option(False, "--probe")) -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        items = list_models(session, settings, probe=probe)
    if _state(ctx).json:
        typer.echo(json.dumps({"items": items}, indent=2))
        return
    for item in items:
        typer.echo(f"{item['status']:<22} {item['id']:<32} {item['display_name']}")
    typer.echo("\nStatus values come from local probes. 'planned' engines are not runnable.")


@models_app.command("inspect")
def models_inspect(ctx: typer.Context, adapter_id: str, probe: bool = typer.Option(False, "--probe")) -> None:
    from ..services import get_model

    settings = get_settings()
    with get_session_factory()() as session:
        card = _run_cli(get_model, session, settings, adapter_id, probe=probe)
    typer.echo(json.dumps(card, indent=2))


@config_app.command("show")
def config_show(
    ctx: typer.Context,
    redact_secrets: bool = typer.Option(True, "--redact-secrets/--no-redact-secrets"),
) -> None:
    settings = get_settings()
    values = settings.public_dict()
    if not redact_secrets:
        typer.echo("Refusing to print secrets. Values are always redacted.", err=True)
    if _state(ctx).json:
        typer.echo(json.dumps(values, indent=2))
        return
    for key, value in values.items():
        typer.echo(f"{key}: {value}")


@cache_app.command("status")
def cache_status(ctx: typer.Context) -> None:
    from ..workflow.cache import NodeCache

    stats = NodeCache(get_settings().cache_dir).stats()
    _print(ctx, stats, f"Cache: {stats['entries']} entries, {stats['bytes'] / 1024:.1f} KiB")


@cache_app.command("clear")
def cache_clear(ctx: typer.Context, dry_run: bool = typer.Option(False, "--dry-run")) -> None:
    from ..workflow.cache import NodeCache

    cache = NodeCache(get_settings().cache_dir)
    stats = cache.stats()
    if dry_run:
        _print(
            ctx,
            {**stats, "dry_run": True},
            f"Would remove {stats['entries']} entries ({stats['bytes']} bytes).",
        )
        return
    entries, size = cache.clear()
    _print(
        ctx,
        {"removed_entries": entries, "removed_bytes": size},
        f"Removed {entries} cache entries ({size} bytes).",
    )


@db_app.command("init")
def db_init(ctx: typer.Context) -> None:
    settings = get_settings()
    init_db(settings)
    _print(
        ctx,
        {"database": str(settings.db_path), "status": "initialised", "revision": current_revision(settings)},
        f"Database ready at {settings.db_path}",
    )


@db_app.command("upgrade")
def db_upgrade(ctx: typer.Context) -> None:
    """Apply pending Alembic migrations."""
    settings = get_settings()
    init_db(settings)
    _print(
        ctx,
        {"database": str(settings.db_path), "revision": current_revision(settings), "status": "up-to-date"},
        f"Database at {settings.db_path} is up to date ({current_revision(settings)}).",
    )


@db_app.command("current")
def db_current(ctx: typer.Context) -> None:
    """Print the applied migration revision."""
    settings = get_settings()
    revision = current_revision(settings)
    _print(
        ctx,
        {"database": str(settings.db_path), "revision": revision},
        f"Revision: {revision or 'not initialised'}",
    )


@app.command("version")
def version() -> None:
    typer.echo(f"{PRODUCT_NAME} {__version__} - {CREDIT}")


if __name__ == "__main__":  # pragma: no cover
    app()


def cli() -> None:  # pragma: no cover - console-script entry point
    """Console entry point that accepts ``--json`` before or after the subcommand."""
    argv = sys.argv[1:]
    global_flags = [flag for flag in ("--json", "--debug") if flag in argv]
    rest = [arg for arg in argv if arg not in global_flags]
    app(args=[*global_flags, *rest])
