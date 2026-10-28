"""System, diagnostics, settings and cache routes."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ... import CREDIT, PRODUCT_NAME, TAGLINE, __version__
from ...core.config import Settings
from ...core.doctor import run_diagnostics
from ...core.errors import ValidationError
from ...database.models import Compound, Project, Run
from ...workflow.cache import NodeCache
from ..deps import db, settings_dep

router = APIRouter(prefix="/api/v1", tags=["system"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "product": PRODUCT_NAME, "version": __version__}


@router.get("/ready")
def ready(request: Request, session: Session = Depends(db)) -> dict:
    session.execute(text("SELECT 1"))
    return {
        "status": "ready",
        "database": "ok",
        "uptime_seconds": int((datetime.now(UTC) - request.app.state.started_at).total_seconds()),
    }


@router.get("/diagnostics")
def diagnostics(
    check_providers: bool = Query(default=False),
    check_vulkan: bool = Query(default=False),
    settings: Settings = Depends(settings_dep),
) -> dict:
    return run_diagnostics(settings, check_providers=check_providers, check_vulkan=check_vulkan)


@router.get("/settings")
def settings_view(settings: Settings = Depends(settings_dep)) -> dict:
    runs_size = sum(path.stat().st_size for path in settings.runs_dir.rglob("*") if path.is_file())
    return {
        "values": settings.public_dict(),
        "storage": {
            "database_bytes": settings.db_path.stat().st_size if settings.db_path.exists() else 0,
            "runs_bytes": runs_size,
            "cache": NodeCache(settings.cache_dir).stats(),
        },
        "product": {
            "name": PRODUCT_NAME,
            "version": __version__,
            "tagline": TAGLINE,
            "credit": CREDIT,
        },
    }


@router.get("/stats")
def stats(session: Session = Depends(db), settings: Settings = Depends(settings_dep)) -> dict:
    def count(model) -> int:
        return int(session.execute(select(func.count()).select_from(model)).scalar() or 0)

    queued = int(session.execute(select(func.count()).select_from(Run).where(Run.status == "queued")).scalar() or 0)
    running = int(session.execute(select(func.count()).select_from(Run).where(Run.status == "running")).scalar() or 0)
    return {
        "projects": count(Project),
        "compounds": count(Compound),
        "runs": count(Run),
        "queued_runs": queued,
        "running_runs": running,
        "data_dir": str(settings.data_dir),
        "cache": NodeCache(settings.cache_dir).stats(),
    }


@router.get("/cache")
def cache_status(settings: Settings = Depends(settings_dep)) -> dict:
    return NodeCache(settings.cache_dir).stats()


@router.delete("/cache")
def cache_clear(confirm: bool = Query(default=False), settings: Settings = Depends(settings_dep)) -> dict:
    if not confirm:
        raise ValidationError("Cache clear requires confirm=true.")
    entries, size = NodeCache(settings.cache_dir).clear()
    return {"removed_entries": entries, "removed_bytes": size}
