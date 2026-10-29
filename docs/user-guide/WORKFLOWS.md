# Workflows

A workflow is a declarative YAML or JSON document. It has one entry node that
consumes the dataset and a linear chain of typed nodes. The engine validates the
document before queuing a run.

## Minimal example

```yaml
schema_version: 1
id: descriptors-only
name: Descriptors only
description: Compute RDKit descriptors and export the table.
nodes:
  - id: descriptors
    type: chem.descriptors
    config:
      descriptors: [mw, logp, tpsa, qed]
edges: []
```

Validate and run:

```bash
hcs-discovery workflow validate my-workflow.yaml
hcs-discovery workflow run my-workflow.yaml --project <project-id> --dataset <dataset-id>
```

## Structure rules

- `schema_version` must be `1`.
- `name` is required and limited to 200 characters.
- Node IDs match `^[a-z][a-z0-9_]{0,47}$` and must be unique.
- There must be exactly one root node (no incoming edge).
- The graph must be a connected chain; cycles and disconnected nodes fail.
- Each node has at most one incoming edge. Multi-input merge nodes are rejected
  with `multiple_inputs_unsupported`.
- `timeout_seconds` is optional per node (1–86,400; default 300).
- Unknown fields are rejected.

The first node receives the dataset table with these identity columns:

| Column | Meaning |
|---|---|
| `compound_id` | Internal `cmp_...` ID |
| `smiles` | Standardised isomeric SMILES |
| `name` | Imported name, if any |
| `source_id` | Imported source identifier, if any |

## Built-in nodes

### `chem.descriptors` — RDKit descriptors

```yaml
- id: descriptors
  type: chem.descriptors
  config:
    descriptors: [mw, logp, tpsa, hbd, hba, rotb, qed]
```

Available keys:

| Key | Label | Unit | Direction |
|---|---|---|---|
| `mw` | Molecular weight | g/mol | neutral |
| `logp` | cLogP | log10 | lower |
| `tpsa` | TPSA | Å² | lower |
| `hbd` | H-bond donors | count | lower |
| `hba` | H-bond acceptors | count | lower |
| `rotb` | Rotatable bonds | count | lower |
| `rings` | Ring count | count | neutral |
| `aromatic_rings` | Aromatic rings | count | neutral |
| `heavy_atoms` | Heavy atoms | count | neutral |
| `fsp3` | Fraction sp3 | fraction | higher |
| `qed` | QED | score (0-1) | higher |
| `formal_charge` | Formal charge | e | neutral |
| `mr` | Molar refractivity | cm³/mol | neutral |

Values are computed with the installed RDKit version, which is recorded in the
run manifest. A structure that cannot be re-parsed gets empty values and a
warning event; the row is not silently removed.

### `chem.similarity` — Tanimoto similarity

```yaml
- id: similarity
  type: chem.similarity
  config:
    query_smiles: "CC(=O)Oc1ccccc1C(=O)O"
    column: similarity_query
    radius: 2
    bits: 2048
    metric: tanimoto
```

| Field | Default | Range |
|---|---|---|
| `query_smiles` | required | valid SMILES |
| `column` | `similarity_query` | `^[a-z][a-z0-9_]{0,47}$` |
| `radius` | 2 | 1–4 |
| `bits` | 2048 | 256–8192 |
| `metric` | `tanimoto` | only `tanimoto` |

Morgan/ECFP fingerprint similarity is a structural heuristic. It is not a
measure of biological activity.

### `filter.rules` — explicit thresholds

```yaml
- id: filters
  type: filter.rules
  config:
    mode: flag          # flag | drop
    rules:
      - {column: mw, op: between, value: 150, value2: 600, label: "MW 150-600"}
      - {column: logp, op: between, value: -1.0, value2: 5.5, label: "cLogP -1..5.5"}
      - {column: tpsa, op: le, value: 160}
```

Operators: `le`, `lt`, `ge`, `gt`, `eq`, `ne`, `between`.

- `mode: flag` keeps every row and adds `filter_pass` and `filter_reasons`.
- `mode: drop` removes failing rows after flagging them; the dropped count is
  logged.
- A missing or non-numeric value fails a numeric rule.
- `eq`/`ne` compare case-insensitively as strings when the threshold is not
  numeric.
- Thresholds are project criteria. They are not universal medicinal-chemistry
  laws and must be justified for your use case.

Output columns: `filter_pass` (boolean) and `filter_reasons` (string).

### `rank.pareto` — Pareto fronts and composite score

```yaml
- id: ranking
  type: rank.pareto
  config:
    objectives:
      - {column: qed, direction: higher, weight: 1.5}
      - {column: tpsa, direction: lower, weight: 1.0}
      - {column: logp, direction: lower, weight: 1.0}
    pareto_front_limit: 10
```

- Each objective must reference a numeric column.
- Weights are 0–100 and at least one must be positive.
- Composite score is a weighted average of min-max normalised objectives. If an
  objective value is missing, the composite score is empty. Normalisation uses
  the rows of the current run, so scores are not comparable across runs or
  datasets and shift when rows are added.
- Pareto fronts use the raw objective vectors (direction-normalised) and are
  computed only among filter-passing rows.
- Filter-failing rows get `pareto_rank = null` and are ranked after passing
  rows.
- `pareto_front_limit` is 1–50. Rows beyond the limit get no front and a warning
  is logged.
- If a column's metadata direction conflicts with the objective direction, the
  explicit objective wins and a warning is logged.

Output columns: `composite_score`, `pareto_rank`, `rank`.

### `report.summary` — Markdown and HTML summary

```yaml
- id: summary
  type: report.summary
  config:
    title: Triage summary
    top_n: 10
```

Writes `summary.md` and `summary.html` as node artifacts. `top_n` is 1–100.
The summary includes column definitions and the scientific caveat.

## Templates

The UI and CLI expose three templates:

| ID | Purpose |
|---|---|
| `triage-basic` | Descriptors → thresholds → Pareto/composite → summary |
| `similarity-triage` | Similarity to a query → ranking |
| `descriptors-only` | Descriptor table only |

```bash
hcs-discovery workflow templates
hcs-discovery workflow templates --export ./workflows
```

## Validation errors

Common issue codes:

| Code | Meaning |
|---|---|
| `unsupported_schema` | `schema_version` is not 1 |
| `duplicate_node` | Two nodes share an ID |
| `unknown_node_type` | Type is not registered |
| `empty_workflow` | No nodes |
| `unknown_edge_source` / `unknown_edge_target` | Edge references a missing node |
| `self_loop` | Node connects to itself |
| `duplicate_edge` | Same edge repeated |
| `multiple_inputs_unsupported` | A node has more than one parent |
| `multiple_roots` | More than one entry node |
| `no_root` / `cycle_or_disconnected` | Cyclic or disconnected graph |
| `invalid_config` | Config fails the node's Pydantic model |
| `missing_column` / `missing_input_column` | Required column is absent |

The API returns the same codes under `error.details.issues`.

## Reproducibility

- The run stores an immutable workflow snapshot and content hash.
- Node cache keys include the config, input hash, engine versions and handler
  implementation hash.
- The manifest records dataset SHA-256, Python/RDKit versions and hardware.
- Editing a saved workflow does not change existing runs.
- Deleting a saved workflow does not delete existing runs.

## Current limits

- One dataset per run, one input per node, no joins or branching fan-in.
- No loops, conditionals or parameter sweeps.
- No sub-workflow composition.
- Node handlers run in the application process; there is no sandbox.
