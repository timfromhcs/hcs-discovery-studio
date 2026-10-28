# Plugin and node API

This document describes the in-process extension contracts shipped in 0.1.0.
There is no dynamic plugin discovery, sandbox or marketplace yet. Third-party
code must be installed into the same Python environment and registered before
the application starts.

## Node definition

A workflow node is a frozen `NodeDefinition`:

```python
from pydantic import BaseModel
from hcs_discovery.workflow.registry import NodeContext, NodeDefinition, NodeRegistry
from hcs_discovery.workflow.table import Column, Table


class MyConfig(BaseModel):
    column: str = "my_score"


def run_my_node(table: Table, config: MyConfig, ctx: NodeContext) -> Table:
    ctx.log("starting my node")
    output = table.copy()
    output.add_column(
        Column(
            config.column,
            "My score",
            "number",
            unit="0-1",
            direction="higher",
            method="my-method/1",
        )
    )
    for row in output.rows:
        row[config.column] = 0.5
    return output


definition = NodeDefinition(
    type="example.my_node",
    title="My node",
    category="example",
    version="1.0.0",
    description="An example node.",
    config_model=MyConfig,
    handler=run_my_node,
    requires=("smiles",),
    outputs=lambda config: [
        Column(config.column, "My score", "number", unit="0-1", direction="higher", method="my-method/1")
    ],
    documentation="Describe units, method and limitations here.",
)

registry = NodeRegistry()
registry.register(definition)
```

`NodeDefinition` fields:

| Field | Meaning |
|---|---|
| `type` | Stable identifier used in workflow YAML |
| `title` | Human label in the UI |
| `category` | Grouping label |
| `version` | Node version included in cache keys |
| `description` | Short explanation |
| `config_model` | Pydantic model for validated config |
| `handler` | `(Table, config, NodeContext) -> Table` |
| `requires` | Input columns that must exist |
| `extra_requires` | Optional callable for config-dependent requirements |
| `outputs` | Callable returning produced `Column`s |
| `documentation` | Longer text surfaced by the API |

Registration raises if a type is already registered unless `replace=True` is
explicitly passed. The default registry is a process-wide singleton built by
`register_builtin_nodes`.

## Handler contract

A handler must:

- treat the input table as read-only and return a new or copied table,
- declare every output column with a description, type and, where relevant,
  unit, direction and method,
- be deterministic for a given input, config and engine version, or explicitly
  record its seed and nondeterminism,
- call `ctx.check_cancel()` at safe points in long loops,
- write files only through `ctx.write_artifact`, which sanitises the name and
  records the SHA-256,
- raise an `AppError` subclass for expected failures so the user gets a stable
  error code,
- never log credentials or raw environment variables.

`NodeContext` exposes:

```python
ctx.run_id
ctx.node_id
ctx.work_dir
ctx.engine_versions
ctx.log(message, level="info", data=None)
ctx.report_progress(0.0..1.0)
ctx.check_cancel()
ctx.write_artifact(filename, content, media_type)
```

## Column contract

```python
Column(
    name="qed",
    description="Quantitative estimate of drug-likeness",
    type="number",  # number | string | boolean
    unit="0-1",
    direction="higher",  # higher | lower | None
    method="RDKit QED",
)
```

The UI uses `method`, `unit` and `direction` to render "Column meanings" and
chart axes. A number without a method is not acceptable for a scientific
column.

## Adapter cards (model registry)

Model and engine metadata is represented by `AdapterCard` in
`src/hcs_discovery/schemas/models.py`. It carries:

- `id`, `display_name`, `category`, `version`,
- `license` (code, weights, data),
- `capabilities`, `device_providers`, `network_required`,
- `resource_profile`, `status`, `citation_url`, `documentation_url`,
- `notes` and `implemented`.

Allowed statuses include `available`, `available_with_limits`, `not_configured`,
`unavailable`, `blocked_by_policy` and `planned`. A planned card must set
`implemented=False` and must not be exposed as a runnable node.

The registry is built from real local probes:

```bash
hcs-discovery models list
hcs-discovery models list --probe
hcs-discovery models inspect science:rdkit
```

## Adding an engine

1. Implement the adapter behind a node handler or a service.
2. Add a deterministic test with a fixture or fake.
3. Record the license of code, weights and data separately.
4. Add the adapter card with an honest status.
5. Document hardware requirements and failure modes.
6. Do not advertise GPU or Vulkan support unless the adapter has been proven on
   that backend.

## Current limitations

- No entry-point discovery, plugin manifest or version negotiation.
- No process or container isolation for third-party handlers.
- No plugin signing or provenance attestation.
- No stable third-party API guarantee before 1.0.
- Multi-input nodes are not part of the execution model.
