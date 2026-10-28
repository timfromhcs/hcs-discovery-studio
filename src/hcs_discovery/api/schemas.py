"""API request/response schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    purpose: str = Field(default="", max_length=2000)


class WorkflowSaveRequest(BaseModel):
    project_id: str
    definition: dict[str, Any]
    workflow_id: str | None = None


class WorkflowValidateRequest(BaseModel):
    definition: dict[str, Any]


class RunCreateRequest(BaseModel):
    project_id: str
    dataset_id: str
    workflow: dict[str, Any] | None = None
    workflow_id: str | None = None
    seed: int | None = None


class CancelResponse(BaseModel):
    id: str
    status: str
    cancel_requested: bool


class ValidateMoleculesResponse(BaseModel):
    format: str
    record_count: int
    imported_count: int
    error_count: int
    rows: list[dict[str, Any]]


class MessageResponse(BaseModel):
    ok: bool = True
    message: str


SortOrder = Literal["asc", "desc"]
