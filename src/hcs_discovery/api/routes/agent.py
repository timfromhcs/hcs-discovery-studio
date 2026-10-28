"""Research Agent API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...core.config import Settings
from ...plugins.llm.agent import AgentRequest, ResearchAgent
from ...plugins.llm.openai_compat import build_provider
from ...plugins.llm.tools import get_tool_catalog
from ..deps import db, settings_dep

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


@router.get("/status")
def agent_status(
    settings: Settings = Depends(settings_dep),
) -> dict[str, Any]:
    provider = build_provider(settings)
    health = provider.probe()
    return {
        "modes": ["ask", "plan", "run"],
        "default_mode": "ask",
        "provider": provider.metadata(),
        "provider_health": health.as_dict(),
        "tools_count": len(get_tool_catalog()),
        "network_policy": settings.network_policy,
    }


@router.get("/tools")
def list_tools() -> dict[str, Any]:
    return {"tools": get_tool_catalog()}


@router.post("/query")
def agent_query(
    payload: AgentRequest,
    session: Session = Depends(db),
    settings: Settings = Depends(settings_dep),
) -> dict[str, Any]:
    agent = ResearchAgent(settings=settings)
    response = agent.handle(payload, session=session)
    return response.model_dump()
