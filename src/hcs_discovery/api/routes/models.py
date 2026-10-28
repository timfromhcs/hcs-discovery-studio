"""Model/engine registry routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ... import services
from ...core.config import Settings
from ..deps import db, settings_dep

router = APIRouter(prefix="/api/v1/models", tags=["models"])


@router.get("")
def list_models(
    probe: bool = Query(default=False),
    session: Session = Depends(db),
    settings: Settings = Depends(settings_dep),
) -> dict:
    return {
        "items": services.list_models(session, settings, probe=probe),
        "note": "Status is derived from real local probes. Planned engines are not runnable.",
    }


@router.get("/{adapter_id:path}")
def inspect_model(
    adapter_id: str,
    probe: bool = Query(default=False),
    session: Session = Depends(db),
    settings: Settings = Depends(settings_dep),
) -> dict:
    return services.get_model(session, settings, adapter_id, probe=probe)
