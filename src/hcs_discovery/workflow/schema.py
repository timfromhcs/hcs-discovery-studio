"""Workflow definition schema, validation and static column checking."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from ..core.errors import ValidationError
from ..core.hashing import stable_json_hash
from .registry import NodeRegistry, default_registry
from .table import Column, Table


class EdgeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    target: str


class NodeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,47}$")
    type: str
    title: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=300, ge=1, le=86_400)


class WorkflowSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    id: str = "workflow"
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    nodes: list[NodeSpec]
    edges: list[EdgeSpec] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def content_hash(self) -> str:
        return stable_json_hash(self.model_dump(mode="json", exclude_none=False))


@dataclass
class ValidatedWorkflow:
    spec: WorkflowSpec
    order: list[NodeSpec]
    columns_at: dict[str, list[Column]]
    registry: NodeRegistry
    parents_map: dict[str, list[str]] = field(default_factory=dict)
    children_map: dict[str, list[str]] = field(default_factory=dict)

    @property
    def root(self) -> NodeSpec:
        return self.order[0]

    def node(self, node_id: str) -> NodeSpec:
        for node in self.order:
            if node.id == node_id:
                return node
        raise ValidationError(f"Unknown node '{node_id}'.")

    @property
    def content_hash(self) -> str:
        return self.spec.content_hash()


def parse_workflow(payload: dict[str, Any]) -> WorkflowSpec:
    try:
        return WorkflowSpec.model_validate(payload)
    except PydanticValidationError as exc:
        raise ValidationError(
            "Workflow definition is not valid.", details={"issues": exc.errors(include_url=False)}
        ) from exc


def validate_workflow(
    payload: dict[str, Any] | WorkflowSpec,
    *,
    registry: NodeRegistry | None = None,
    input_columns: list[Column] | None = None,
) -> ValidatedWorkflow:
    registry = registry or default_registry()
    if input_columns is None:
        from .table import IDENTITY_COLUMNS

        input_columns = list(IDENTITY_COLUMNS)
    spec = payload if isinstance(payload, WorkflowSpec) else parse_workflow(payload)
    issues: list[dict[str, Any]] = []

    if spec.schema_version != 1:
        issues.append(
            {
                "code": "unsupported_schema",
                "message": f"Unsupported schema_version {spec.schema_version}.",
            }
        )

    nodes: dict[str, NodeSpec] = {}
    for node in spec.nodes:
        if node.id in nodes:
            issues.append(
                {
                    "code": "duplicate_node",
                    "node": node.id,
                    "message": f"Duplicate node id '{node.id}'.",
                }
            )
            continue
        nodes[node.id] = node
        if not registry.has(node.type):
            issues.append(
                {
                    "code": "unknown_node_type",
                    "node": node.id,
                    "message": f"Unknown node type '{node.type}'.",
                    "available": registry.types(),
                }
            )

    if not spec.nodes:
        issues.append({"code": "empty_workflow", "message": "A workflow needs at least one node."})

    parents: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    children: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    seen_edges: set[tuple[str, str]] = set()

    for edge in spec.edges:
        if edge.source not in nodes:
            issues.append(
                {
                    "code": "unknown_edge_source",
                    "message": f"Edge source '{edge.source}' does not exist.",
                }
            )
            continue
        if edge.target not in nodes:
            issues.append(
                {
                    "code": "unknown_edge_target",
                    "message": f"Edge target '{edge.target}' does not exist.",
                }
            )
            continue
        if edge.source == edge.target:
            issues.append(
                {
                    "code": "self_loop",
                    "node": edge.source,
                    "message": "A node cannot connect to itself.",
                }
            )
            continue
        if (edge.source, edge.target) in seen_edges:
            issues.append(
                {
                    "code": "duplicate_edge",
                    "message": f"Duplicate edge {edge.source} -> {edge.target}.",
                }
            )
            continue
        seen_edges.add((edge.source, edge.target))

        # Check multi-input rules: only table.join supports multiple parent edges
        if parents[edge.target] and nodes[edge.target].type != "table.join":
            issues.append(
                {
                    "code": "multiple_inputs_unsupported",
                    "node": edge.target,
                    "message": (
                        f"Node '{edge.target}' ({nodes[edge.target].type}) only accepts one input. "
                        "Use 'table.join' to merge multiple incoming branches."
                    ),
                }
            )
        parents[edge.target].append(edge.source)
        children[edge.source].append(edge.target)

    roots = [node_id for node_id, p_list in parents.items() if not p_list]
    if len(roots) > 1:
        issues.append(
            {
                "code": "multiple_roots",
                "nodes": roots,
                "message": "A workflow needs exactly one entry node that consumes the dataset.",
            }
        )
    elif not roots and nodes:
        issues.append({"code": "no_root", "message": "Every node has a parent, so the graph is cyclic."})

    # Kahn's algorithm for topological sorting of DAG
    order: list[NodeSpec] = []
    if roots and not any(i["code"] == "no_root" for i in issues):
        in_degree = {nid: len(parents[nid]) for nid in nodes}
        queue = [nid for nid in nodes if in_degree[nid] == 0]
        while queue:
            curr = queue.pop(0)
            order.append(nodes[curr])
            for ch in children[curr]:
                in_degree[ch] -= 1
                if in_degree[ch] == 0:
                    queue.append(ch)
        if len(order) != len(nodes):
            issues.append(
                {
                    "code": "cycle_or_disconnected",
                    "message": "Workflow graph contains a directed cycle or unreachable nodes.",
                }
            )

    columns_at: dict[str, list[Column]] = {}
    if not issues and order:
        for node in order:
            # Determine incoming columns for this node
            p_ids = parents[node.id]
            if not p_ids:
                node_in_cols = list(input_columns or [])
            elif len(p_ids) == 1:
                node_in_cols = list(columns_at.get(p_ids[0], []))
            else:
                # Merge columns from all parents
                seen_c: dict[str, Column] = {}
                for pid in p_ids:
                    for c in columns_at.get(pid, []):
                        if c.name not in seen_c:
                            seen_c[c.name] = c
                node_in_cols = list(seen_c.values())

            definition = registry.get(node.type)
            try:
                config = definition.parse_config(node.config)
            except ValidationError as exc:
                issues.append(
                    {
                        "code": "invalid_config",
                        "node": node.id,
                        "message": exc.message,
                        "details": exc.details,
                    }
                )
                continue

            available_col_names = {c.name for c in node_in_cols}
            missing = [name for name in definition.required_columns(config) if name not in available_col_names]
            if missing and not (not p_ids and not node_in_cols):
                issues.append(
                    {
                        "code": "missing_column",
                        "node": node.id,
                        "message": f"Node requires missing column(s): {', '.join(missing)}.",
                    }
                )
            try:
                produced = definition.produces(config)
            except Exception as exc:
                issues.append({"code": "invalid_config", "node": node.id, "message": str(exc)})
                continue

            # Output columns = incoming + produced
            out_cols = list(node_in_cols)
            out_names = {c.name for c in out_cols}
            for prod in produced:
                if prod.name not in out_names:
                    out_cols.append(prod)
                    out_names.add(prod.name)
            columns_at[node.id] = out_cols

    if issues:
        raise ValidationError(
            "Workflow validation failed.",
            details={"issues": issues},
        )

    return ValidatedWorkflow(
        spec=spec,
        order=order,
        columns_at=columns_at,
        registry=registry,
        parents_map=parents,
        children_map=children,
    )


def dataset_table(compounds: list[dict[str, Any]]) -> Table:
    from .table import IDENTITY_COLUMNS

    rows = [
        {
            "id": item["id"],
            "compound_id": item["id"],
            "smiles": item["isomeric_smiles"],
            "name": item.get("name"),
            "source_id": item.get("source_id"),
        }
        for item in compounds
    ]
    return Table(rows=rows, columns=list(IDENTITY_COLUMNS))
