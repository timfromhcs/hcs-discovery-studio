# Testing

The test strategy is layered: fast unit tests for invariants, integration tests
for persistence and HTTP/CLI behavior, security tests for policy and redaction,
and a small browser end-to-end suite for the main user journey.

## Commands

Backend:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest -q
uv run pytest --cov=hcs_discovery --cov-report=term-missing
```

Frontend:

```bash
cd apps/web
npm run typecheck
npm run build
npm run test:e2e
```

Wheel:

```bash
uv build --wheel
```

## Backend layout

| File | Focus |
|---|---|
| `tests/unit/test_chemistry.py` | Standardisation, descriptor metadata, invalid structures |
| `tests/unit/test_workflow.py` | Schema validation, graph rules, ranking, filters, cache keys |
| `tests/unit/test_security_primitives.py` | Redaction, safe paths, URL/network helpers |
| `tests/integration/test_api.py` | HTTP contract, errors, auth, SSE, artifacts |
| `tests/integration/test_cli.py` | Exit codes, JSON output, CLI/service parity |
| `tests/integration/test_runs.py` | Queue, leases, cancellation, retry, manifests |
| `tests/integration/test_migrations.py` | Fresh database and legacy stamping |
| `tests/security/test_reports_and_policy.py` | HTML escaping, secret absence, policy blocks |

The suite is deterministic and offline. Tests that would use the network are
marked `network` and excluded from the default run. Scientific benchmarks are
marked `scientific`; they are not correctness tests.

## What is covered

- Import of CSV, SDF and SMILES, including row-level errors and duplicates.
- RDKit standardisation options and descriptor column metadata.
- Workflow graph validation: unknown types, duplicate IDs, multiple roots,
  multiple inputs, cycles, missing columns, invalid config.
- Pareto ranking excludes filter failures and leaves their rank empty.
- Cache keys change with config, input, engine versions and implementation hash.
- Run execution, node events, cancellation, lease recovery and retry.
- Manifest fields: workflow hash, dataset checksum, environment, artifacts.
- API error envelope, 404/409/422 behavior, bearer auth, CORS restrictions.
- Report HTML escaping and absence of registered secrets.
- Alembic upgrade from empty and legacy database handling.

## What is not covered

- Numerical accuracy against experimental data. No such claim is made.
- Docking, MD or learned models, because they are not implemented.
- Multi-user concurrency or PostgreSQL. The product targets one local user.
- Browser visual regression snapshots. Screenshots are reviewed manually.
- Performance benchmarks. Timings in the UI are observed durations, not
  benchmark results.

## End-to-end suite

`apps/web/playwright.config.ts` starts its own server:

- host `127.0.0.1`, port `8791`,
- data directory `.e2e-data` (cleaned before the run),
- one worker, retries 0,
- built SPA from `apps/web/dist`,
- command `uv run hcs-discovery serve --port 8791`.

The three tests are:

1. workspace → create project → import fixture → pick template → save → run →
   monitor → results;
2. planned engines are visible but not runnable;
3. an unknown run ID shows a real error instead of a fabricated record.

Traces and screenshots are written on failure under `apps/web/test-results`.

## Test data

- `tests/fixtures/e2e_library.csv` — six valid compounds for the browser flow.
- `examples/datasets/demo_library.csv` — 17 rows including one intentional
  invalid structure, used for manual demos.
- No restricted or proprietary dataset is used.

## Adding tests

- Prefer a service-level test for behavior and an API/CLI test for the contract.
- Use `tmp_path` and the `settings` fixture; never write to the repository
  `data/` directory.
- Do not assert on wall-clock durations.
- Do not assert on RDKit log text.
- For a new error code, assert both the code and the exit/HTTP status.
- For a new scientific column, assert its method, unit and direction.
- For a security fix, add a regression test that fails without the fix.

## Interpreting results

`pytest` prints warnings from dependencies (for example Alembic and Starlette).
Warnings are not failures. The gate is the final `passed` count and a zero exit
code.

The recorded local baseline for 0.1.0 is:

```text
82 passed
3 Playwright tests passed
ruff format --check: clean
ruff check: clean
mypy: clean
npm run typecheck: clean
npm run build: clean
```

CI runs the same commands on Linux and Windows for the backend, and Linux for
the browser suite. A local pass is not a substitute for the cloud run; check the
Actions result for the commit you are releasing.

## CI notes

- Playwright installs Chromium with `npx playwright install --with-deps chromium`.
- The E2E job builds the frontend before starting the server.
- CI uses a temporary data directory and never receives model API keys.
- A failing E2E job uploads traces and screenshots as artifacts.
