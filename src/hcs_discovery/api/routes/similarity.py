"""Similarity search over an imported dataset, with the same payload as the CLI."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.errors import NotFoundError, ValidationError
from ...database.models import Compound, Dataset
from ...gpu.device import probe_gpu
from ...services import load_dataset_fingerprints
from ...similarity import (
    SUPPORTED_BITS,
    SUPPORTED_RADIUS,
    GpuUnavailableError,
    TanimotoIndex,
    resolve_engine,
)
from ..deps import db

router = APIRouter(prefix="/api/v1", tags=["similarity"])

SCHEMA = "hcs.similarity-search.v1"


class SimilaritySearchRequest(BaseModel):
    dataset_id: str = Field(min_length=1, max_length=64)
    query_smiles: str = Field(min_length=1, max_length=4096)
    k: int = Field(default=10, ge=1, le=10_000)
    threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    engine: Literal["auto", "cpu", "gpu"] = "auto"
    boost: Literal["auto", "gpu", "cpu", "hybrid"] = "auto"


@router.get("/similarity/engines")
def similarity_engines() -> dict:
    """What this host can offer, and what the kernel accepts."""
    probe = probe_gpu()
    resolved = resolve_engine("auto") if probe.get("status") == "available" else None
    return {
        "probe": probe,
        "resolved": (
            None
            if resolved is None
            else {
                "name": resolved.name,
                "mode": resolved.mode,
                "adapter": resolved.adapter,
                "backend": resolved.backend,
            }
        ),
        "fingerprint": {"type": "morgan", "radius": SUPPORTED_RADIUS, "bits": SUPPORTED_BITS},
        "boost_modes": ["auto", "gpu", "cpu", "hybrid"],
        "scoped": "dataset",
    }


@router.post("/similarity/search")
def similarity_search(payload: SimilaritySearchRequest, session: Session = Depends(db)) -> dict:
    """Rank a dataset's compounds by Tanimoto similarity to one query structure.

    The GPU result is verified against the CPU reference before it is returned; a
    mismatch is an error, never a number. `engine="gpu"` fails when no hardware
    adapter exists instead of quietly using the CPU.
    """
    dataset = session.get(Dataset, payload.dataset_id)
    if dataset is None:
        raise NotFoundError("Dataset not found.", details={"dataset_id": payload.dataset_id})
    fingerprints = load_dataset_fingerprints(session, payload.dataset_id)
    rows = session.execute(
        select(Compound.id, Compound.name, Compound.isomeric_smiles).where(Compound.id.in_(fingerprints.compound_ids))
    ).all()
    by_id = {row.id: row for row in rows}
    if len(by_id) != fingerprints.count:
        raise ValidationError(
            "The dataset changed while the search was prepared; retry.",
            details={"dataset_id": payload.dataset_id},
        )
    prefiltered = False
    candidates = fingerprints.count
    try:
        with TanimotoIndex.from_packed(fingerprints.packed, prefer=payload.engine, boost=payload.boost) as index:
            resolved = index.engine
            if payload.threshold is not None:
                # BitBound only helps a threshold search; a k-nearest query needs the
                # full score vector to know which k are nearest.
                pruned = index.threshold_hits(payload.query_smiles, payload.threshold)
                raw_hits = pruned.hits[: payload.k]
                parity = pruned.parity_checked
                timings = pruned.timings_ms
                candidates = pruned.candidates
                prefiltered = pruned.prefiltered
            else:
                result = index.search(payload.query_smiles, k=payload.k, threshold=None)
                raw_hits = result.hits
                parity = result.parity_checked
                timings = result.timings_ms
    except GpuUnavailableError as exc:
        raise ValidationError(
            "A GPU engine was requested but no hardware GPU adapter is available.",
            details={"reason": str(exc)},
        ) from exc
    hits = [
        {
            "rank": rank,
            "compound_id": by_id[fingerprints.compound_ids[hit.index]].id,
            "name": by_id[fingerprints.compound_ids[hit.index]].name or "",
            "smiles": by_id[fingerprints.compound_ids[hit.index]].isomeric_smiles,
            "similarity": round(hit.similarity, 6),
        }
        for rank, hit in enumerate(raw_hits, start=1)
    ]
    return {
        "schema": SCHEMA,
        "dataset_id": payload.dataset_id,
        "query": payload.query_smiles,
        "n_library": fingerprints.count,
        "fingerprints": {
            "cached": fingerprints.cached,
            "checksum": fingerprints.checksum,
            "count": fingerprints.count,
            "radius": fingerprints.radius,
            "bits": fingerprints.bits,
        },
        "engine": {
            "name": resolved.name,
            "mode": resolved.mode,
            "workers": resolved.workers,
            "adapter": resolved.adapter,
            "backend": resolved.backend,
            "adapter_type": resolved.adapter_type,
            "detail": resolved.detail,
        },
        "parity_checked": parity,
        "prefilter": {"enabled": prefiltered, "candidates": candidates, "library": fingerprints.count},
        "k": payload.k,
        "threshold": payload.threshold,
        "timings_ms": {key: round(value, 3) for key, value in timings.items()},
        "hits": hits,
    }
