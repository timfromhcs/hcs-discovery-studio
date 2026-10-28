"""Compound library queries and detail views."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..chemistry.depiction import depiction_svg
from ..chemistry.descriptors import DESCRIPTORS, compute_descriptors
from ..core.errors import NotFoundError
from ..database.models import Compound, Dataset, Run, RunResult

SORTABLE = {
    "name": Compound.name,
    "created_at": Compound.created_at,
    "formula": Compound.formula,
    "source_id": Compound.source_id,
    "smiles": Compound.isomeric_smiles,
}


def list_compounds(
    session: Session,
    project_id: str,
    *,
    q: str | None = None,
    dataset_id: str | None = None,
    sort: str = "created_at",
    order: str = "desc",
    limit: int = 50,
    offset: int = 0,
    include_descriptors: bool = True,
) -> dict[str, Any]:
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    filters = [Compound.project_id == project_id]
    if dataset_id:
        filters.append(Compound.dataset_id == dataset_id)
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(
                Compound.name.ilike(pattern),
                Compound.isomeric_smiles.ilike(pattern),
                Compound.source_id.ilike(pattern),
                Compound.inchikey.ilike(pattern),
                Compound.formula.ilike(pattern),
            )
        )
    base = select(Compound).where(*filters)
    total = int(session.execute(select(func.count(Compound.id)).where(*filters)).scalar() or 0)
    column = SORTABLE.get(sort, Compound.created_at)
    base = base.order_by(column.desc() if order == "desc" else column.asc(), Compound.id)
    compounds = session.execute(base.limit(limit).offset(offset)).scalars().all()
    items = []
    for compound in compounds:
        item: dict[str, Any] = {
            "id": compound.id,
            "name": compound.name,
            "smiles": compound.isomeric_smiles,
            "canonical_smiles": compound.canonical_smiles,
            "formula": compound.formula,
            "source_id": compound.source_id,
            "inchikey": compound.inchikey,
            "dataset_id": compound.dataset_id,
            "warnings": compound.warnings,
            "created_at": compound.created_at.isoformat() + "Z",
        }
        if include_descriptors:
            try:
                item["descriptors"] = {
                    key: value["value"] for key, value in compute_descriptors(compound.isomeric_smiles).items()
                }
            except Exception:
                item["descriptors"] = {}
        items.append(item)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
        "sort": sort if sort in SORTABLE else "created_at",
        "order": order,
    }


def get_compound(session: Session, compound_id: str) -> Compound:
    compound = session.get(Compound, compound_id)
    if compound is None:
        raise NotFoundError(f"Compound '{compound_id}' does not exist.")
    return compound


def compound_detail(session: Session, compound_id: str) -> dict[str, Any]:
    compound = get_compound(session, compound_id)
    dataset = session.get(Dataset, compound.dataset_id) if compound.dataset_id else None
    descriptors = compute_descriptors(compound.isomeric_smiles, list(DESCRIPTORS))
    appearances = session.execute(
        select(RunResult, Run)
        .join(Run, Run.id == RunResult.run_id)
        .where(RunResult.compound_id == compound.id)
        .order_by(Run.created_at.desc())
        .limit(20)
    ).all()
    return {
        "id": compound.id,
        "project_id": compound.project_id,
        "name": compound.name,
        "input_smiles": compound.input_smiles,
        "canonical_smiles": compound.canonical_smiles,
        "isomeric_smiles": compound.isomeric_smiles,
        "inchi": compound.inchi,
        "inchikey": compound.inchikey,
        "formula": compound.formula,
        "formal_charge": compound.formal_charge,
        "warnings": compound.warnings,
        "created_at": compound.created_at.isoformat() + "Z",
        "source": {
            "dataset_id": dataset.id if dataset else None,
            "dataset_name": dataset.name if dataset else None,
            "source_format": dataset.source_format if dataset else None,
            "source_row_index": compound.source_row_index,
            "source_id": compound.source_id,
            "source_url": dataset.source_url if dataset else None,
            "license": dataset.license if dataset else "unknown",
            "dataset_sha256": dataset.sha256 if dataset else None,
        },
        "descriptors": descriptors,
        "runs": [
            {
                "run_id": run.id,
                "workflow_name": run.workflow_name,
                "status": run.status,
                "rank": result.rank,
                "composite_score": result.composite_score,
                "pareto_front": result.pareto_front,
                "rejected": result.rejected,
                "reasons": result.reasons,
                "metrics": result.metrics,
                "created_at": run.created_at.isoformat() + "Z",
            }
            for result, run in appearances
        ],
        "depiction_url": f"/api/v1/compounds/{compound.id}/depiction.svg",
    }


def render_depiction(
    session: Session, compound_id: str, *, theme: str = "dark", width: int = 420, height: int = 300
) -> str:
    compound = get_compound(session, compound_id)
    return depiction_svg(compound.isomeric_smiles, width=width, height=height, theme=theme)
