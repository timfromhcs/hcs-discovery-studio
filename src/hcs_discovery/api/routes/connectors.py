"""API routes for external public data connectors (PubChem and ChEMBL)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from ...core.config import Settings
from ...plugins.connectors.chembl import CHEMBL_LICENSE, ChEMBLConnector
from ...plugins.connectors.pubchem import PUBCHEM_LICENSE, PubChemConnector
from ..deps import settings_dep

router = APIRouter(prefix="/api/v1/connectors", tags=["connectors"])


@router.get("/status")
def connector_status(settings: Settings = Depends(settings_dep)) -> dict[str, Any]:
    """Report external connector status and active network policy."""
    remote_enabled = settings.network_policy == "remote"
    return {
        "network_policy": settings.network_policy,
        "remote_enabled": remote_enabled,
        "connectors": [
            {
                "id": "pubchem",
                "display_name": "NCBI PubChem",
                "status": "ready" if remote_enabled else "blocked_by_policy",
                "license": PUBCHEM_LICENSE,
                "endpoints": ["search_compound"],
            },
            {
                "id": "chembl",
                "display_name": "EMBL-EBI ChEMBL",
                "status": "ready" if remote_enabled else "blocked_by_policy",
                "license": CHEMBL_LICENSE,
                "endpoints": ["search_targets", "search_compounds", "get_activities"],
            },
        ],
    }


@router.get("/pubchem/search")
def search_pubchem(
    query: str = Query(..., min_length=1, description="Compound name or SMILES"),
    settings: Settings = Depends(settings_dep),
) -> dict[str, Any]:
    """Search compounds in PubChem by chemical or common name."""
    connector = PubChemConnector(settings=settings)
    records = connector.search_compound_by_name(query)
    return {
        "query": query,
        "count": len(records),
        "license": PUBCHEM_LICENSE,
        "items": [r.as_dict() for r in records],
    }


@router.get("/chembl/targets")
def search_chembl_targets(
    query: str = Query(..., min_length=1, description="Target name, gene, or organism"),
    limit: int = Query(default=20, ge=1, le=100),
    settings: Settings = Depends(settings_dep),
) -> dict[str, Any]:
    """Search biological targets in ChEMBL."""
    connector = ChEMBLConnector(settings=settings)
    records = connector.search_targets(query, limit=limit)
    return {
        "query": query,
        "count": len(records),
        "license": CHEMBL_LICENSE,
        "items": [r.as_dict() for r in records],
    }


@router.get("/chembl/compounds")
def search_chembl_compounds(
    query: str = Query(..., min_length=1, description="Compound name or synonym"),
    limit: int = Query(default=20, ge=1, le=100),
    settings: Settings = Depends(settings_dep),
) -> dict[str, Any]:
    """Search small molecule compounds in ChEMBL."""
    connector = ChEMBLConnector(settings=settings)
    records = connector.search_compounds(query, limit=limit)
    return {
        "query": query,
        "count": len(records),
        "license": CHEMBL_LICENSE,
        "items": [r.as_dict() for r in records],
    }


@router.get("/chembl/activities")
def get_chembl_activities(
    target_id: str = Query(..., min_length=1, description="ChEMBL Target ID (e.g. CHEMBL203)"),
    limit: int = Query(default=50, ge=1, le=200),
    settings: Settings = Depends(settings_dep),
) -> dict[str, Any]:
    """Fetch experimental bioactivities for a ChEMBL target."""
    connector = ChEMBLConnector(settings=settings)
    records = connector.get_target_activities(target_id, limit=limit)
    return {
        "target_chembl_id": target_id,
        "count": len(records),
        "license": CHEMBL_LICENSE,
        "items": [r.as_dict() for r in records],
    }
