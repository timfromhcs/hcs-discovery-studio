"""Versioned adapter metadata schema (Section 4.4 of the build directive)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AdapterStatus = Literal[
    "available",
    "available_with_limits",
    "needs_install",
    "needs_credentials",
    "needs_hardware",
    "experimental",
    "disabled_by_policy",
    "unavailable",
    "planned",
    "not_configured",
]


class LicenseInfo(BaseModel):
    code: str
    weights: str = "unknown"
    data: str = "unknown"


class ResourceProfile(BaseModel):
    ram_mb_min: int | None = None
    vram_mb_min: int | None = None


class AdapterCard(BaseModel):
    id: str
    display_name: str
    category: Literal[
        "chemistry",
        "target_evidence",
        "structure",
        "docking",
        "property",
        "admet",
        "simulation",
        "reporting",
        "llm",
    ]
    version: str
    license: LicenseInfo
    capabilities: list[str] = Field(default_factory=list)
    device_providers: list[str] = Field(default_factory=lambda: ["cpu"])
    network_required: bool = False
    resource_profile: ResourceProfile = Field(default_factory=ResourceProfile)
    status: AdapterStatus
    citation_url: str | None = None
    documentation_url: str | None = None
    notes: list[str] = Field(default_factory=list)
    implemented: bool = True

    def as_dict(self) -> dict:
        return self.model_dump(mode="json")
