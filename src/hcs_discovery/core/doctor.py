"""Environment diagnostics used by ``hcs-discovery doctor`` and the UI."""

from __future__ import annotations

import importlib.metadata
import os
import platform
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .. import PRODUCT_NAME, __version__
from ..core.config import Settings
from ..core.timeutil import db_now
from .config import get_settings
from .redaction import redact_text


def _check(id_: str, label: str, status: str, detail: str, remediation: str | None = None) -> dict[str, Any]:
    return {
        "id": id_,
        "label": label,
        "status": status,
        "detail": detail,
        "remediation": remediation,
    }


def _disk_free_gb(path: Path) -> float:
    try:
        return round(shutil.disk_usage(path).free / (1024**3), 1)
    except OSError:
        return 0.0


def _rdkit_check() -> dict[str, Any]:
    try:
        import rdkit
        from rdkit import Chem
        from rdkit.Chem import Descriptors

        mol = Chem.MolFromSmiles("CCO")
        if mol is None:
            return _check("rdkit", "RDKit chemistry engine", "error", "RDKit could not parse ethanol.")
        value = round(Descriptors.MolWt(mol), 3)
        return _check(
            "rdkit",
            "RDKit chemistry engine",
            "ok",
            f"RDKit {rdkit.__version__}; ethanol MW {value} g/mol.",
        )
    except Exception as exc:
        return _check(
            "rdkit",
            "RDKit chemistry engine",
            "error",
            redact_text(f"{type(exc).__name__}: {exc}"),
            "Reinstall the base dependencies with `uv sync`.",
        )


def _database_check(settings: Settings) -> dict[str, Any]:
    try:
        from sqlalchemy import inspect, text

        from ..database.base import get_engine

        engine = get_engine(settings)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            tables = inspect(connection).get_table_names()
        if "runs" not in tables:
            return _check(
                "database",
                "Local database",
                "warning",
                f"Database at {settings.db_path} is reachable but not initialised.",
                "Run `hcs-discovery db init` (or start the app once).",
            )
        return _check("database", "Local database", "ok", f"SQLite ready at {settings.db_path}.")
    except Exception as exc:
        return _check(
            "database",
            "Local database",
            "error",
            redact_text(f"{type(exc).__name__}: {exc}"),
            "Check that the data directory is writable.",
        )


def _data_dir_check(settings: Settings) -> dict[str, Any]:
    try:
        settings.ensure_dirs()
        with tempfile.NamedTemporaryFile(dir=settings.data_dir, prefix="doctor-", delete=True) as handle:
            handle.write(b"ok")
        return _check(
            "data_dir",
            "Local data directory",
            "ok",
            f"Writable: {settings.data_dir} ({_disk_free_gb(settings.data_dir)} GB free).",
        )
    except Exception as exc:
        return _check(
            "data_dir",
            "Local data directory",
            "error",
            redact_text(f"{type(exc).__name__}: {exc}"),
            "Set HCS_DATA_DIR to a writable directory.",
        )


def _queue_check(settings: Settings) -> dict[str, Any]:
    try:
        from sqlalchemy import func, select

        from ..database.base import get_engine
        from ..database.models import Run

        engine = get_engine(settings)
        with engine.connect() as connection:
            queued = connection.execute(select(func.count()).select_from(Run).where(Run.status == "queued")).scalar()
            running = connection.execute(select(func.count()).select_from(Run).where(Run.status == "running")).scalar()
            stale = connection.execute(
                select(func.count()).select_from(Run).where(Run.status == "running", Run.lease_expires_at < db_now())
            ).scalar()
        detail = f"{queued} queued, {running} running"
        if stale:
            detail += f", {stale} with an expired lease (recovered on the next worker poll)"
        return _check("queue", "Job queue", "ok" if not stale else "warning", detail + ".")
    except Exception as exc:
        return _check("queue", "Job queue", "warning", redact_text(f"{type(exc).__name__}: {exc}"))


def run_diagnostics(
    settings: Settings | None = None,
    *,
    check_providers: bool = False,
    check_vulkan: bool = False,
) -> dict[str, Any]:
    settings = settings or get_settings()
    checks = [
        _data_dir_check(settings),
        _database_check(settings),
        _rdkit_check(),
        _queue_check(settings),
    ]

    checks.append(
        _check(
            "network_policy",
            "Network policy",
            "ok",
            f"Policy: {settings.network_policy}. "
            + (
                "Remote providers and connectors are blocked."
                if settings.network_policy == "local"
                else "Remote access allowed."
            ),
        )
    )

    if check_providers:
        from ..plugins.llm.openai_compat import build_provider

        provider = build_provider(settings)
        health = provider.probe()
        checks.append(
            _check(
                "llm_provider",
                "LLM provider",
                "ok" if health.status == "available" else "warning" if health.status == "not_configured" else "error",
                f"{health.status}: {health.detail}",
                None
                if health.status in {"available", "not_configured"}
                else "Start the local server or check HCS_LLM_BASE_URL.",
            )
        )

    if check_vulkan:
        from ..plugins.science.vulkan import probe_vulkan

        vulkan = probe_vulkan()
        checks.append(
            _check(
                "vulkan",
                "Vulkan device probe",
                "ok" if vulkan["available"] else "warning",
                vulkan["detail"] + " Model support is not implied.",
                None if vulkan["available"] else vulkan.get("remediation"),
            )
        )

    error_count = sum(1 for check in checks if check["status"] == "error")
    warning_count = sum(1 for check in checks if check["status"] == "warning")
    return {
        "product": {"name": PRODUCT_NAME, "version": __version__},
        "status": "error" if error_count else "degraded" if warning_count else "ok",
        "generated_at": db_now().isoformat(timespec="seconds") + "Z",
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
            "packages": {name: _version(name) for name in ("fastapi", "sqlalchemy", "pydantic", "rdkit", "alembic")},
            "backend": "cpu",
        },
        "checks": checks,
    }


def _version(package: str) -> str:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return "missing"
