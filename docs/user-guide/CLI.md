# CLI reference

The CLI is installed as `hcs-discovery` and shares the service layer with the
HTTP API. From a source checkout, prefix commands with `uv run`:

```bash
uv run hcs-discovery --help
```

Global options:

| Option | Meaning |
|---|---|
| `--json` | Machine-readable JSON on stdout; logs go to stderr |
| `--debug` | Include redacted internal error details |
| `--help` | Command help |

`--json` is accepted before or after the subcommand.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Generic failure, or a followed run that did not start |
| 3 | Validation error |
| 4 | Not found or conflict |
| 5 | Missing optional dependency |
| 6 | Blocked by policy |
| 7 | Run cancelled |
| 8 | Run failed |

## Diagnostics and serving

```bash
hcs-discovery doctor
hcs-discovery doctor --check-vulkan
hcs-discovery doctor --check-providers
hcs-discovery doctor --json
hcs-discovery serve
hcs-discovery serve --port 8788 --no-worker
hcs-discovery worker
hcs-discovery worker --once
hcs-discovery version
```

`doctor --check-vulkan` reports device presence only. It does not imply that a
model can use Vulkan.

## Projects

```bash
hcs-discovery project list
hcs-discovery project create --name "Kinase leads" --description "Fragment screen"
hcs-discovery project show <project-id>
hcs-discovery project delete <project-id> --yes
```

`project delete` removes database rows. Run directories remain on disk.

## Datasets

```bash
hcs-discovery dataset import library.csv --project <project-id>
hcs-discovery dataset import library.sdf --project <project-id> --format sdf
hcs-discovery dataset import structures.smi --project <project-id>
hcs-discovery dataset import library.csv --project <project-id> \
  --smiles-column "Structure" --name-column "Compound" --id-column "ID"
hcs-discovery dataset list --project <project-id>
hcs-discovery dataset errors <dataset-id>
hcs-discovery dataset delete <dataset-id> --yes
```

Import options:

| Option | Default | Meaning |
|---|---|---|
| `--format` | `auto` | `csv`, `sdf`, `smi` or `auto` |
| `--smiles-column` | auto-detect | Structure column for CSV |
| `--name-column` | auto-detect | Name column for CSV |
| `--id-column` | auto-detect | Source identifier column for CSV |
| `--keep-salts` | off | Do not strip counter-ions |
| `--neutralize` | off | Neutralise formal charges |
| `--canonical-tautomer` | off | Apply RDKit canonical tautomer |

Limits come from `HCS_MAX_IMPORT_ROWS` (default 50,000) and
`HCS_MAX_UPLOAD_MB` (default 64).

## Molecule validation

```bash
hcs-discovery compounds validate library.csv
hcs-discovery compounds validate library.sdf --output validation.json
```

This does not write to the database. It exits `1` if any row fails.

## Workflows

```bash
hcs-discovery workflow list
hcs-discovery workflow list --project <project-id>
hcs-discovery workflow templates
hcs-discovery workflow templates --export ./workflow-templates
hcs-discovery workflow validate examples/workflows/triage.yaml
hcs-discovery workflow save examples/workflows/triage.yaml --project <project-id>
hcs-discovery workflow save updated.yaml --project <project-id> --id <workflow-id>
hcs-discovery workflow show <workflow-id>
hcs-discovery workflow delete <workflow-id> --yes
hcs-discovery workflow run examples/workflows/triage.yaml \
  --project <project-id> --dataset <dataset-id>
hcs-discovery workflow run --workflow-id <workflow-id> \
  --project <project-id> --dataset <dataset-id>
hcs-discovery workflow run examples/workflows/triage.yaml \
  --project <project-id> --dataset <dataset-id> --no-follow --json
```

`workflow run` follows the run by default and exits non-zero on failure.
`--seed` records an integer seed in the manifest.

## Runs

```bash
hcs-discovery run list
hcs-discovery run list --project <project-id> --limit 50
hcs-discovery run status <run-id>
hcs-discovery run logs <run-id>
hcs-discovery run logs <run-id> --follow
hcs-discovery run results <run-id>
hcs-discovery run results <run-id> --limit 100
hcs-discovery run artifacts <run-id>
hcs-discovery run artifacts <run-id> --output ./exports
hcs-discovery run cancel <run-id>
hcs-discovery run retry <run-id>
hcs-discovery run retry <run-id> --no-follow --json
```

`run retry` creates a new run from the original workflow snapshot and dataset.
It does not reuse the previous run ID.

## Reports

```bash
hcs-discovery report export <run-id> --format html --output reports/run.html
hcs-discovery report export <run-id> --format markdown --output reports/run.md
hcs-discovery report export <run-id> --format json --output reports/run.json
hcs-discovery report export <run-id> --format csv --output reports/results.csv
```

## Models and configuration

```bash
hcs-discovery models list
hcs-discovery models list --probe
hcs-discovery models inspect science:rdkit
hcs-discovery models inspect llm:openai-compatible --probe
hcs-discovery config show
```

`models list` marks unimplemented engines as `planned`. `config show` always
redacts secret values, even with `--no-redact-secrets`.

## Cache and database

```bash
hcs-discovery cache status
hcs-discovery cache clear --dry-run
hcs-discovery cache clear
hcs-discovery db init
hcs-discovery db upgrade
hcs-discovery db current
```

## JSON automation example

```bash
PROJECT=$(hcs-discovery --json project create --name "Automation" | jq -r .id)
DATASET=$(hcs-discovery --json dataset import examples/datasets/demo_library.csv \
  --project "$PROJECT" | jq -r .id)
RUN=$(hcs-discovery --json workflow run examples/workflows/triage.yaml \
  --project "$PROJECT" --dataset "$DATASET" --no-follow | jq -r .run_id)
hcs-discovery --json run status "$RUN" | jq '.status'
```

`jq` is optional; any JSON parser works. On Windows PowerShell, use
`ConvertFrom-Json` instead.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `HCS_DATA_DIR` | `./data` | Database, runs, cache and logs |
| `HCS_NETWORK_POLICY` | `local` | `local` blocks non-loopback providers |
| `HCS_HOST` | `127.0.0.1` | Bind address |
| `HCS_PORT` | `8787` | Bind port |
| `HCS_CPU_THREADS` | unset | Thread limit for CPU work |
| `HCS_MAX_IMPORT_ROWS` | `50000` | Import row limit |
| `HCS_MAX_UPLOAD_MB` | `64` | Upload size limit |
| `HCS_LLM_BASE_URL` | unset | Local OpenAI-compatible endpoint |
| `HCS_LLM_MODEL` | unset | Model name sent to the provider |
| `HCS_LLM_API_KEY` | unset | Provider key; never printed |
| `HCS_REMOTE_LLM_ENABLED` | `false` | Explicit opt-in for remote LLM |
| `HCS_API_TOKEN` | unset | Required for non-loopback binding |
| `HCS_ALLOW_EXTERNAL_RECEPTOR_PATHS` | `false` | Let `dock.vina` read receptor files outside `<HCS_DATA_DIR>/receptors`; trusted local installs only |

See `.env.example` for a documented template.
