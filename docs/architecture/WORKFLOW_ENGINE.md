# Workflow engine

The workflow engine turns a declarative YAML/JSON definition plus an imported
dataset into a reproducible, inspectable run. It is deliberately small: a linear
single-input chain of typed nodes, persisted state, and a content-addressed
cache. Multi-input merge nodes are rejected rather than approximated.

## Definition format

```yaml
schema_version: 1
id: triage-basic
name: Basic triage
description: Compute descriptors, filter, rank and summarise.
nodes:
  - id: descriptors
    type: chem.descriptors
    config:
      descriptors: [mw, logp, tpsa, qed]
  - id: filters
    type: filter.rules
    config:
      mode: flag
      rules:
        - {column: mw, op: between, value: 150, value2: 600, label: "MW 150-600"}
  - id: ranking
    type: rank.pareto
    config:
      objectives:
        - {column: qed, direction: higher, weight: 1.5}
  - id: summary
    type: report.summary
    config:
      title: Triage summary
      top_n: 10
edges:
  - {source: descriptors, target: filters}
  - {source: filters, target: ranking}
  - {source: ranking, target: summary}
```

Node IDs match `^[a-z][a-z0-9_]{0,47}$`. `timeout_seconds` defaults to 300 and
is capped at 86,400. Unknown fields are rejected (`extra="forbid"`) so typos
cannot silently change a scientific result.

## Validation

`validate_workflow` performs static checks before a run is queued:

- supported `schema_version` (currently `1`),
- unique node IDs and known node types,
- edges reference existing nodes; no self-loops or duplicate edges,
- exactly one root (the dataset entry point),
- no cycles or disconnected nodes,
- each node's config validates against its Pydantic model,
- required input columns are present in the propagated table schema,
- multi-input targets are rejected with `multiple_inputs_unsupported`.

The CLI exposes the same check:

```bash
hcs-discovery workflow validate examples/workflows/triage.yaml
```

Validation returns the topological order, the workflow content hash and, on
failure, a structured list of issues. The UI shows the same issue codes.

## Execution

`RunExecutor` runs in a worker process or in the thread started by
`hcs-discovery serve`. For each run it:

1. reloads the immutable workflow snapshot from the database,
2. re-validates against the current registry,
3. loads the dataset's compounds in source-row order,
4. computes a cache key for each node,
5. restores a cached table or executes the handler,
6. persists node status, summary, duration, artifacts and events,
7. persists results and the manifest.

A node handler receives a copy of the input `Table` and a `NodeContext` with
logging, progress, cancellation checks, artifact writing and engine versions.
Handlers must not mutate global state or rely on wall-clock time for scientific
output.

## Cache keys

```text
sha256({
  node_type, node_version, implementation_hash,
  config, input_hash, engine_versions, schema_version
})
```

- `implementation_hash` is derived from the handler source and config schema, so
  editing a handler invalidates old entries.
- `engine_versions` includes RDKit, Python and every registered node version.
- `input_hash` is the content hash of the entire input table, not just row count.
- Cache entries are stored under `data/cache/<first two hex chars>/<key>/`.

Cache hits are visible in the UI and in `run status` as `(cached)`. Clearing the
cache is explicit:

```bash
hcs-discovery cache status
hcs-discovery cache clear --dry-run
hcs-discovery cache clear
```

## Queue and leases

The queue lives in SQLite. A worker claims the oldest queued run with a
conditional `UPDATE ... WHERE status='queued'`, so two workers cannot claim the
same row. Claiming increments `attempt` and sets a lease expiry.

- A heartbeat extends the lease while the worker is alive.
- An expired lease is recovered on the next worker poll: the open node is marked
  failed, and the run is requeued or failed once `HCS_MAX_RUN_ATTEMPTS` is
  exhausted.
- Execution is at-least-once. Handlers are either deterministic or protected by
  the cache key; duplicate execution must not corrupt results.
- `hcs-discovery worker --once` drains the queue and exits, which is useful in
  CI and demos.

The default concurrency is 1. SQLite serialises writers, so higher concurrency
is not a performance win for this release.

## Cancellation and timeouts

- Cancellation is a persisted flag. A queued run is cancelled immediately; a
  running run stops at the next safe point between nodes and inside handlers
  that call `check_cancel`.
- The API returns `409` when cancelling a terminal run.
- A node that exceeds `timeout_seconds` fails the run with a structured error.
- Failures retain the failing node, a redacted message and any completed
  artifacts. Partial results are not presented as a successful run.

## Events

Every transition is appended to `run_events` with a monotonically increasing
`seq`:

```text
run.started, run.validated, node.started, log, node.succeeded,
node.failed, node.cancelled, run.cancel_requested, run.cancelled,
run.requeued, run.failed, run.succeeded
```

The API streams them as Server-Sent Events at
`GET /api/v1/runs/{run_id}/events/stream`. The CLI polls the same rows with
`run logs --follow`, so the two views cannot disagree.

## Results and provenance

A successful run writes:

| Artifact | Purpose |
|---|---|
| `results.json` | rows plus column descriptions, units and methods |
| `results.csv` | flat table for spreadsheets and downstream tools |
| `manifest.json` | workflow snapshot, dataset checksum, environment, hardware, cache keys, artifact checksums, limitations |
| node artifacts | summaries or other files written by a node |

The manifest is the reproducibility contract. It records the exact workflow
hash, dataset SHA-256, Python and RDKit versions, CPU description and the
backend (`cpu`). It does not claim that a result is experimentally valid.

## Known limits

- One input per node; no joins, merges or branching fan-in.
- One root; the dataset is always the entry point.
- No distributed workers, no PostgreSQL queue, no multi-tenant isolation.
- Node handlers run in-process. There is no OS sandbox for third-party nodes.
- A crashed process can leave a run queued for one lease period before recovery.
