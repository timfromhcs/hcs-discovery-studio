"""Compound library and detail routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ... import services
from ..deps import db

router = APIRouter(prefix="/api/v1", tags=["compounds"])


@router.get("/projects/{project_id}/compounds")
def list_compounds(
    project_id: str,
    q: str | None = Query(default=None, max_length=200),
    dataset_id: str | None = None,
    sort: str = Query(default="created_at"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(db),
) -> dict:
    services.get_project(session, project_id)
    return services.list_compounds(
        session,
        project_id,
        q=q,
        dataset_id=dataset_id,
        sort=sort,
        order=order,
        limit=limit,
        offset=offset,
    )


@router.get("/compounds/{compound_id}")
def compound_detail(compound_id: str, session: Session = Depends(db)) -> dict:
    return services.compound_detail(session, compound_id)


@router.get("/compounds/{compound_id}/depiction.svg")
def compound_depiction(
    compound_id: str,
    theme: str = Query(default="dark", pattern="^(dark|light)$"),
    width: int = Query(default=420, ge=120, le=1200),
    height: int = Query(default=300, ge=100, le=900),
    session: Session = Depends(db),
) -> Response:
    svg = services.render_depiction(session, compound_id, theme=theme, width=width, height=height)
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "private, max-age=3600"},
    )
