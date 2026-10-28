"""Allowlisted, strictly validated server-side tools for the research agent.

All tool executions pass through narrow typed Python functions with strict schema
validation. Arbitrary shell or Python code execution is strictly forbidden.
Untrusted input strings and dataset records are treated strictly as data payloads.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from ... import services
from ...core.config import Settings
from ...core.errors import PolicyError, ValidationError
from ...workflow.registry import default_registry
from ...workflow.schema import validate_workflow

# ---------------------------------------------------------------------------
# Tool Parameter Schemas
# ---------------------------------------------------------------------------


class ListProjectsParams(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)


class ListDatasetsParams(BaseModel):
    project_id: str = Field(min_length=1, max_length=128)


class GetDatasetSummaryParams(BaseModel):
    dataset_id: str = Field(min_length=1, max_length=128)


class ListEnginesParams(BaseModel):
    pass


class ValidateWorkflowSpecParams(BaseModel):
    definition: dict[str, Any] = Field(description="DAG workflow dictionary specification")


class CreateWorkflowParams(BaseModel):
    project_id: str = Field(min_length=1, max_length=128)
    definition: dict[str, Any] = Field(description="DAG workflow dictionary specification")


class SubmitRunParams(BaseModel):
    project_id: str = Field(min_length=1, max_length=128)
    dataset_id: str = Field(min_length=1, max_length=128)
    workflow_id: str | None = Field(default=None, max_length=128)
    workflow: dict[str, Any] | None = Field(default=None)
    seed: int | None = Field(default=None, ge=0)


class GetRunStatusParams(BaseModel):
    run_id: str = Field(min_length=1, max_length=128)


class GetRunResultsParams(BaseModel):
    run_id: str = Field(min_length=1, max_length=128)
    limit: int = Field(default=50, ge=1, le=500)


class ExportReportParams(BaseModel):
    run_id: str = Field(min_length=1, max_length=128)
    format: Literal["markdown", "html", "json", "csv", "sdf"] = Field(default="markdown")


# ---------------------------------------------------------------------------
# Tool Metadata & Registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    param_cls: type[BaseModel]
    handler: Callable[..., dict[str, Any]]
    is_mutating: bool = False
    requires_approval: bool = False
    high_impact: bool = False

    def schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "is_mutating": self.is_mutating,
            "requires_approval": self.requires_approval,
            "high_impact": self.high_impact,
            "parameters": self.param_cls.model_json_schema(),
        }


def _tool_list_projects(
    session: Session, settings: Settings, params: ListProjectsParams, **_kwargs: Any
) -> dict[str, Any]:
    projects = services.list_projects(session)
    return {
        "count": len(projects),
        "projects": [
            {"id": p.get("id"), "name": p.get("name"), "description": p.get("description")}
            for p in projects[: params.limit]
        ],
    }


def _tool_list_datasets(
    session: Session, settings: Settings, params: ListDatasetsParams, **_kwargs: Any
) -> dict[str, Any]:
    datasets = services.list_datasets(session, project_id=params.project_id)
    return {
        "project_id": params.project_id,
        "count": len(datasets),
        "datasets": [
            {
                "id": d.get("id"),
                "name": d.get("name"),
                "row_count": d.get("row_count"),
                "status": d.get("status"),
            }
            for d in datasets
        ],
    }


def _tool_get_dataset_summary(
    session: Session, settings: Settings, params: GetDatasetSummaryParams, **_kwargs: Any
) -> dict[str, Any]:
    dataset = services.get_dataset(session, dataset_id=params.dataset_id)
    summary = services.dataset_dict(dataset)
    return {
        "id": summary.get("id"),
        "name": summary.get("name"),
        "row_count": summary.get("row_count"),
        "format": summary.get("format"),
        "status": summary.get("status"),
        "columns": [col.get("name") for col in summary.get("columns", []) if isinstance(col, dict)],
    }


def _tool_list_engines(
    session: Session, settings: Settings, params: ListEnginesParams, **_kwargs: Any
) -> dict[str, Any]:
    models = services.list_models(session, settings, probe=False)
    return {
        "engines": [
            {
                "id": m.get("id"),
                "display_name": m.get("display_name"),
                "category": m.get("category"),
                "version": m.get("version"),
                "status": m.get("status"),
                "backend": m.get("backend"),
            }
            for m in models
        ]
    }


def _tool_validate_workflow_spec(
    session: Session, settings: Settings, params: ValidateWorkflowSpecParams, **_kwargs: Any
) -> dict[str, Any]:
    validated = validate_workflow(params.definition, registry=default_registry())
    return {
        "valid": True,
        "content_hash": validated.content_hash,
        "order": [node.id for node in validated.order],
        "nodes": [
            {
                "id": node.id,
                "type": node.type,
                "columns_after": [column.name for column in validated.columns_at.get(node.id, [])],
            }
            for node in validated.order
        ],
    }


def _tool_create_workflow(
    session: Session, settings: Settings, params: CreateWorkflowParams, **_kwargs: Any
) -> dict[str, Any]:
    workflow = services.save_workflow(
        session, project_id=params.project_id, payload=params.definition, registry=default_registry()
    )
    return {
        "id": workflow.id,
        "name": workflow.name,
        "project_id": workflow.project_id,
        "content_hash": workflow.content_hash,
        "schema_version": workflow.schema_version,
    }


def _tool_submit_run(session: Session, settings: Settings, params: SubmitRunParams, **_kwargs: Any) -> dict[str, Any]:
    if params.workflow_id:
        run = services.create_run_from_saved_workflow(
            session,
            dataset_id=params.dataset_id,
            workflow_id=params.workflow_id,
            seed=params.seed,
            registry=default_registry(),
        )
    elif params.workflow:
        run = services.create_run(
            session,
            project_id=params.project_id,
            dataset_id=params.dataset_id,
            workflow=params.workflow,
            seed=params.seed,
            registry=default_registry(),
        )
    else:
        raise ValidationError("Either workflow_id or workflow definition must be supplied.")

    return {
        "run_id": run.id,
        "status": run.status,
        "project_id": run.project_id,
        "dataset_id": run.dataset_id,
        "seed": run.seed,
    }


def _tool_get_run_status(
    session: Session, settings: Settings, params: GetRunStatusParams, **_kwargs: Any
) -> dict[str, Any]:
    detail = services.get_run_detail(session, run_id=params.run_id)
    return {
        "run_id": detail.get("id"),
        "status": detail.get("status"),
        "workflow_name": detail.get("workflow_name"),
        "started_at": detail.get("started_at"),
        "finished_at": detail.get("finished_at"),
        "error": detail.get("error"),
        "nodes": [
            {
                "node_id": n.get("node_id"),
                "status": n.get("status"),
                "duration_ms": n.get("duration_ms"),
            }
            for n in detail.get("nodes", [])
        ],
    }


def _tool_get_run_results(
    session: Session, settings: Settings, params: GetRunResultsParams, **_kwargs: Any
) -> dict[str, Any]:
    page = services.results_page(session, run_id=params.run_id, limit=params.limit)
    return {
        "run_id": params.run_id,
        "total_records": page.get("total"),
        "items": [
            {
                "rank": item.get("rank"),
                "compound_id": item.get("compound_id"),
                "composite_score": item.get("composite_score"),
                "pareto_front": item.get("pareto_front"),
                "rejected": item.get("rejected"),
                "metrics": item.get("metrics"),
            }
            for item in page.get("items", [])
        ],
    }


def _tool_export_report(
    session: Session, settings: Settings, params: ExportReportParams, **_kwargs: Any
) -> dict[str, Any]:
    from ...reports.render import load_report_data, render_markdown

    data = load_report_data(session, params.run_id)
    summary_md = render_markdown(data)
    # Truncate summary if very long for tool response
    preview = summary_md[:2000] + ("\n... [truncated]" if len(summary_md) > 2000 else "")
    return {
        "run_id": params.run_id,
        "format": params.format,
        "preview": preview,
        "total_records": len(data.get("results", [])),
    }


# ---------------------------------------------------------------------------
# Registry Map
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, ToolSpec] = {
    "list_projects": ToolSpec(
        name="list_projects",
        description="List projects in the current workspace.",
        param_cls=ListProjectsParams,
        handler=_tool_list_projects,
        is_mutating=False,
    ),
    "list_datasets": ToolSpec(
        name="list_datasets",
        description="List datasets registered in a project.",
        param_cls=ListDatasetsParams,
        handler=_tool_list_datasets,
        is_mutating=False,
    ),
    "get_dataset_summary": ToolSpec(
        name="get_dataset_summary",
        description="Inspect a dataset, returning record counts and column headers.",
        param_cls=GetDatasetSummaryParams,
        handler=_tool_get_dataset_summary,
        is_mutating=False,
    ),
    "list_engines": ToolSpec(
        name="list_engines",
        description="List computational engines and their availability on this host.",
        param_cls=ListEnginesParams,
        handler=_tool_list_engines,
        is_mutating=False,
    ),
    "validate_workflow_spec": ToolSpec(
        name="validate_workflow_spec",
        description="Validate a DAG workflow definition without executing it.",
        param_cls=ValidateWorkflowSpecParams,
        handler=_tool_validate_workflow_spec,
        is_mutating=False,
    ),
    "create_workflow": ToolSpec(
        name="create_workflow",
        description="Persist a new workflow DAG definition in a project.",
        param_cls=CreateWorkflowParams,
        handler=_tool_create_workflow,
        is_mutating=True,
        requires_approval=True,
    ),
    "submit_run": ToolSpec(
        name="submit_run",
        description="Queue a workflow run for asynchronous execution on a dataset.",
        param_cls=SubmitRunParams,
        handler=_tool_submit_run,
        is_mutating=True,
        requires_approval=True,
        high_impact=True,
    ),
    "get_run_status": ToolSpec(
        name="get_run_status",
        description="Query the execution status and event details of a run.",
        param_cls=GetRunStatusParams,
        handler=_tool_get_run_status,
        is_mutating=False,
    ),
    "get_run_results": ToolSpec(
        name="get_run_results",
        description="Retrieve ranked output rows and metric scores from a run.",
        param_cls=GetRunResultsParams,
        handler=_tool_get_run_results,
        is_mutating=False,
    ),
    "export_report": ToolSpec(
        name="export_report",
        description="Generate a formatted summary report for a completed run.",
        param_cls=ExportReportParams,
        handler=_tool_export_report,
        is_mutating=False,
    ),
}


def get_tool_catalog() -> list[dict[str, Any]]:
    """Return catalog of all available agent tools with parameter schemas."""
    return [spec.schema() for spec in _REGISTRY.values()]


def execute_tool(
    name: str,
    arguments: dict[str, Any],
    session: Session,
    settings: Settings,
    *,
    approved: bool = False,
) -> dict[str, Any]:
    """Execute an allowlisted tool with strict validation and security policy check."""
    spec = _REGISTRY.get(name)
    if spec is None:
        raise ValidationError(f"Tool '{name}' is not an allowlisted agent tool.")

    if spec.requires_approval and not approved:
        raise PolicyError(
            f"Tool '{name}' requires explicit approval before execution.",
            details={"tool": name, "high_impact": spec.high_impact},
        )

    try:
        parsed_params = spec.param_cls.model_validate(arguments)
    except PydanticValidationError as exc:
        raise ValidationError(f"Invalid arguments for tool '{name}': {exc.errors()}") from exc

    return spec.handler(session=session, settings=settings, params=parsed_params)
