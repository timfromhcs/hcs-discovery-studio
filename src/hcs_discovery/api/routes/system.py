"""System, diagnostics, settings and cache routes."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ... import CREDIT, PRODUCT_NAME, TAGLINE, __version__
from ...core.config import Settings
from ...core.doctor import run_diagnostics
from ...core.errors import ValidationError
from ...database.models import Compound, Dataset, Project, Run
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


@router.get("/gpu")
def gpu_probe() -> dict:
    """Which hardware adapter the shared Tanimoto kernel would use (no benchmark)."""
    from ...gpu.device import probe_gpu

    return probe_gpu()


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


def _prometheus_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


@router.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
def metrics(request: Request, session: Session = Depends(db), settings: Settings = Depends(settings_dep)) -> str:
    """Prometheus text exposition (version 0.0.4) with local counters only.

    Deliberately small and dependency-free: counts an operator can act on, no
    per-request labels (cardinality), no paths, no tokens, no user data. Scraping
    works on loopback and over the same bearer-token rule as the rest of `/api/v1`.
    """
    from ...similarity import device_probe

    def count(model) -> int:
        return int(session.execute(select(func.count()).select_from(model)).scalar() or 0)

    runs_by_status = {
        str(status): int(total)
        for status, total in session.execute(select(Run.status, func.count()).group_by(Run.status)).all()
    }
    cache = NodeCache(settings.cache_dir).stats()
    try:
        gpu_available = 1 if device_probe().get("status") == "available" else 0
    except Exception:
        gpu_available = 0
    uptime = int((datetime.now(UTC) - request.app.state.started_at).total_seconds())

    lines: list[str] = [
        "# HELP hcs_build_info Build information.",
        "# TYPE hcs_build_info gauge",
        f'hcs_build_info{{version="{_prometheus_escape(__version__)}",product="{_prometheus_escape(PRODUCT_NAME)}"}} 1',
        "# HELP hcs_uptime_seconds Seconds since this process started.",
        "# TYPE hcs_uptime_seconds gauge",
        f"hcs_uptime_seconds {uptime}",
        "# HELP hcs_projects Number of projects.",
        "# TYPE hcs_projects gauge",
        f"hcs_projects {count(Project)}",
        "# HELP hcs_datasets Number of imported datasets.",
        "# TYPE hcs_datasets gauge",
        f"hcs_datasets {count(Dataset)}",
        "# HELP hcs_compounds Number of compounds.",
        "# TYPE hcs_compounds gauge",
        f"hcs_compounds {count(Compound)}",
        "# HELP hcs_runs Number of runs by status.",
        "# TYPE hcs_runs gauge",
    ]
    for status in sorted(runs_by_status):
        lines.append(f'hcs_runs{{status="{_prometheus_escape(status)}"}} {runs_by_status[status]}')
    lines += [
        "# HELP hcs_queue_depth Runs waiting or executing.",
        "# TYPE hcs_queue_depth gauge",
        f'hcs_queue_depth{{status="queued"}} {runs_by_status.get("queued", 0)}',
        f'hcs_queue_depth{{status="running"}} {runs_by_status.get("running", 0)}',
        "# HELP hcs_node_cache_entries Content-addressed node-cache entries.",
        "# TYPE hcs_node_cache_entries gauge",
        f"hcs_node_cache_entries {int(cache.get('entries', 0))}",
        "# HELP hcs_node_cache_bytes Node-cache size in bytes.",
        "# TYPE hcs_node_cache_bytes gauge",
        f"hcs_node_cache_bytes {int(cache.get('bytes', 0))}",
        "# HELP hcs_gpu_available 1 when a hardware GPU adapter is usable for the similarity kernel.",
        "# TYPE hcs_gpu_available gauge",
        f"hcs_gpu_available {gpu_available}",
    ]
    return "\n".join(lines) + "\n"
