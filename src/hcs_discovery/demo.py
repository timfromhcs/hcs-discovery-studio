"""Seeded demo workspace for hosted previews.

A hosted preview has no user data and no writable database that survives a cold
start. Rather than shipping screenshots or hard-coded "results", this module
builds a real workspace once per instance:

1. create a project that says in its own name and description that it is demo
   data,
2. import the checked-in synthetic library through the normal import service,
3. submit the normal triage template and let the normal worker execute it.

Everything the UI then shows was computed by this instance. Nothing is
pre-rendered, and the data is disposable by construction. The demo is bounded:
one project, the shipped library, one workflow, no network, no optional engines.

Enable with ``HCS_DEMO_MODE=true``. It is off by default and refuses to run when
the data directory already contains a real project, so it cannot overwrite work.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from .core.config import Settings
from .core.errors import AppError
from .database.base import get_session_factory, init_db
from .database.models import Project
from .jobs.worker import Worker
from .services import create_project, create_run, import_dataset, list_projects
from .workflow.templates import templates

logger = logging.getLogger("hcs.demo")

DEMO_PROJECT_NAME = "Demo workspace (synthetic)"
DEMO_PROJECT_DESCRIPTION = (
    "Generated on this instance from the checked-in synthetic example library. "
    "Real local computation, disposable data, no experimental measurements."
)

_lock = threading.Lock()
_state: dict[str, dict[str, Any]] = {}


def _state_for(settings: Settings) -> dict[str, Any]:
    """Per-data-directory state, so tests and separate instances cannot collide."""
    return _state.setdefault(str(settings.data_dir), {"ready": False, "project_id": None, "error": None})


def demo_library_path() -> Path:
    """The synthetic library that ships with the repository."""
    return Path(__file__).resolve().parents[2] / "examples" / "datasets" / "demo_library.csv"


def _already_seeded(settings: Settings) -> str | None:
    factory = get_session_factory(settings)
    with factory() as session:
        total = session.execute(select(func.count(Project.id))).scalar() or 0
        if not total:
            return None
        existing = session.execute(select(Project).where(Project.name == DEMO_PROJECT_NAME)).scalar_one_or_none()
        if existing is not None:
            return existing.id
        # A real project exists. Never touch it.
        return "__occupied__"


def ensure_demo_workspace(settings: Settings) -> dict[str, Any]:
    """Create the demo workspace once per process; safe to call repeatedly."""
    with _lock:
        state = _state_for(settings)
        if state["ready"]:
            return {"status": "ready", "project_id": state["project_id"], "error": state["error"]}
        try:
            init_db(settings)
            existing = _already_seeded(settings)
            if existing == "__occupied__":
                state.update(ready=True, project_id=None, error="data directory already holds a project")
                return {"status": "skipped", "project_id": None, "error": state["error"]}
            if existing:
                state.update(ready=True, project_id=existing, error=None)
                return {"status": "ready", "project_id": existing, "error": None}

            project_id = _seed(settings)
            state.update(ready=True, project_id=project_id, error=None)
            logger.info("seeded demo workspace", extra={"project_id": project_id})
            return {"status": "ready", "project_id": project_id, "error": None}
        except Exception as exc:  # never break the app because the demo failed
            message = f"{type(exc).__name__}: {exc}"
            logger.warning("demo seeding failed", extra={"error": message})
            state.update(ready=True, project_id=None, error=message)
            return {"status": "failed", "project_id": None, "error": message}


def _seed(settings: Settings) -> str:
    library = demo_library_path()
    if not library.is_file():
        raise AppError(f"Demo library missing at {library}")

    factory = get_session_factory(settings)
    with factory() as session:
        project = create_project(
            session,
            name=DEMO_PROJECT_NAME,
            description=DEMO_PROJECT_DESCRIPTION,
            purpose="Show a real import, workflow run and evidence trail on synthetic input.",
        )
        dataset = import_dataset(
            session=session,
            settings=settings,
            project_id=project.id,
            filename=library.name,
            data=library.read_bytes(),
            name="Synthetic demo library",
            license="project-internal synthetic example",
        )
        template = next(item for item in templates() if item["id"] == "triage-basic")
        run = create_run(
            session,
            project_id=project.id,
            workflow=template,
            dataset_id=dataset.id,
            seed=20261101,
        )
        run_id = run.id

    # Execute it for real, through the same worker the CLI uses.
    worker = Worker(settings=settings, worker_id="demo-seed")
    for _ in range(3):  # bounded: one queued run, at most a retry
        if worker.run_once() is None:
            break

    with factory() as session:
        from .services import run_detail

        detail = run_detail(session, run_id)
        if detail["status"] != "succeeded":
            raise AppError(f"Demo run {run_id} finished as {detail['status']}")
    return project.id


def demo_status(settings: Settings) -> dict[str, Any]:
    """Read-only view for diagnostics; never triggers seeding."""
    try:
        items = list_projects(get_session_factory(settings)())
    except Exception:  # pragma: no cover - defensive for an uninitialised database
        return {"enabled": True, "state": {}, "projects": 0}
    return {"enabled": True, "state": _state_for(settings), "projects": len(items)}
