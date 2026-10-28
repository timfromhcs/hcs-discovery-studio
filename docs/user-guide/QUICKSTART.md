# Quickstart

This walkthrough runs the full CPU demo offline: create a project, import a
small library, run a triage workflow, inspect provenance and export a report.
It needs no GPU, no API key and no network access.

## 1. Install and verify

```bash
uv sync --dev
uv run hcs-discovery doctor
```

`doctor` should report `diagnostics (ok)`. A warning about a missing LLM
provider is expected and harmless.

## 2. Create a project

```bash
uv run hcs-discovery project create --name "Demo project"
```

Copy the printed `prj_...` identifier. List projects at any time:

```bash
uv run hcs-discovery project list
```

## 3. Import the example library

```bash
uv run hcs-discovery dataset import examples/datasets/demo_library.csv --project <project-id>
```

The example file has 17 molecule rows. It intentionally contains one invalid
structure, so the expected result is `Imported 16/17 records ... (1 error rows)`.
This is a feature: failed rows are retained and reported, not silently dropped.

Inspect the row-level error:

```bash
uv run hcs-discovery dataset errors <dataset-id>
```

## 4. Validate the workflow

```bash
uv run hcs-discovery workflow validate examples/workflows/triage.yaml
```

Validation checks node types, graph shape, config schemas and required columns.
It prints the node order and a content hash.

## 5. Run it

The `serve` command starts an embedded worker. If you do not have a server
running, start one first:

```bash
uv run hcs-discovery serve
```

In another terminal:

```bash
uv run hcs-discovery workflow run examples/workflows/triage.yaml \
  --project <project-id> \
  --dataset <dataset-id>
```

The CLI follows the run, prints node events and exits non-zero on failure.
`--no-follow` returns the run ID immediately.

To run without the web server, use a standalone worker:

```bash
uv run hcs-discovery worker --once
```

## 6. Inspect results

```bash
uv run hcs-discovery run status <run-id>
uv run hcs-discovery run results <run-id>
uv run hcs-discovery run logs <run-id>
uv run hcs-discovery run artifacts <run-id> --output ./exports
```

`run results` shows rank, composite score, Pareto front, name and SMILES.
Rejected rows are kept with their reasons and are not assigned a Pareto front.

## 7. Open the UI

Visit <http://127.0.0.1:8787>. The workspace lists the project. Open it to see
the library, workflows and runs. The run monitor streams logs; the results page
shows the ranked table and Pareto scatter.

The same data is available through the API:

```bash
curl http://127.0.0.1:8787/api/v1/runs/<run-id>/results
curl http://127.0.0.1:8787/api/v1/runs/<run-id>/report
```

## 8. Export a report

```bash
uv run hcs-discovery report export <run-id> --format html --output reports/demo.html
```

Formats: `html`, `markdown`, `json`, `csv`. The report includes the pipeline,
results, artifact checksums, environment, hardware and limitations.

## 9. Reproduce it

A second run with the same dataset and workflow should hit the node cache. The
run monitor and `run status` mark cached nodes. To prove the cache is not
required for correctness:

```bash
uv run hcs-discovery cache clear
uv run hcs-discovery workflow run examples/workflows/triage.yaml \
  --project <project-id> --dataset <dataset-id>
```

Compare `results.csv` between the two runs. Deterministic RDKit descriptors and
the same workflow configuration should produce the same values.

## 10. Clean up

Deleting a project removes its database rows:

```bash
uv run hcs-discovery project delete <project-id>
```

Run directories are not removed automatically. Delete `data/runs/<run-id>` if
you no longer need the artifacts.

## Next steps

- `WORKFLOWS.md` — node reference and YAML examples.
- `CLI.md` — every command and option.
- `SCIENTIFIC_LIMITATIONS.md` — what the scores do and do not mean.
- `../architecture/OVERVIEW.md` — how the pieces fit together.
