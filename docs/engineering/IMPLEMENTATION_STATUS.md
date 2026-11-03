# Implementation status

Last updated: 2026-11-03. Version: `2.2.0`. `2.2.0` adds the hosted deployment of
the full application (SPA + `/api/v1` from one Vercel project), an external
database URL and inline run execution; see
[the plan](PLAN_2026-11-03_HOSTED_PARITY.md) and
[the release notes](../releases/v2.2.0.md).

This document is the honest feature ledger. It distinguishes what has been
exercised end-to-end from what is scaffolded, planned or deliberately absent.
"Working" means it has been run locally and is covered by at least one automated
test or a recorded manual check; it does not mean validated science.

## Summary

| Area | Status | Evidence |
|---|---|---|
| Environment audit | Done | `doctor` on Windows 11; versions recorded in AGENT_LOG |
| Repo skeleton and tooling | Done | `pyproject.toml`, lockfiles, Ruff, mypy, pytest, Vite, Playwright |
| Domain model and migrations | Done | SQLAlchemy models, Alembic revision, migration tests |
| Persistent queue | Done | Lease claim, heartbeat, recovery, cancellation, retry tests |
| RDKit import/standardise | Done | CSV/SDF/SMILES, row outcomes, descriptor tests |
| Workflow engine | Done | Validation, execution, cache, events, manifest tests |
| CPU scientific slice | Done | Descriptors → filters → Pareto/composite → summary with integrity checks |
| React UI | Done for shipped features | Visual QA: 18 routes × 6 widths × 2 themes, 0 automatic findings |
| CLI/API parity | Done for shipped actions | Shared services; CLI tests |
| Local LLM provider / Safe Research Agent | Done | Ask, Plan, Run modes with strict allowlisted tools |
| AutoDock Vina docking | Runs; reference-tested on one complex | Host-dependent binary; ligand PDBQT matches Meeko on 48/51 fixtures; 1IEP redocking ≤ 0.94 Å over 5 seeds, enforced in CI; not benchmarked |
| Property estimates | Runs; weak/approximate | Reduced ESOL measured (RMSE 0.97, R² 0.07, n=45); CNS MPO approximation |
| PubChem / ChEMBL connectors | Done | Policy-gated; mocked-transport tests; blocked by default |
| DAG Workflows | Done | Multi-branch DAGs, Kahn topological sort, and table.join with strict-key checks |
| HAEL adaptive scheduler | Experimental, library only | Typed evidence gates, cost model, deterministic trace, 94 property/guard tests ([design](../research/HAEL.md)); no workflow node, API, CLI or UI yet |
| GPU similarity search | Done (Tanimoto only) | Shared WGSL kernel via `wgpu-py`; `hcs_discovery.similarity` with k/threshold, resident library, exact CPU reference; BitBound prefilter for threshold searches (differential-tested, 32–88 % skipped on a density-varied library); `chem.similarity` engine option; `similarity search` CLI; bit-identical to RDKit; measured in [gpu-tanimoto.md](../validation/gpu-tanimoto.md) |
| Browser compute | Done (opt-in) | RDKit WebAssembly self-test and WebGPU Tanimoto benchmark on the Settings page, both covered by Playwright against the served app |
| GitHub CI | Pass on `main` | CI 40947455326 and CodeQL 40947455914 passed on commit `12febcf` |
| Public release | Pending | [`v1.0.0`](https://github.com/timfromhcs/hcs-discovery-studio/releases/tag/v1.0.0) published; `v2.0.0` not yet tagged or published |
| v2.0.0 Stable | Awaiting release candidate run and owner approval | Local gates pass on the merged SHA; tag/publication not performed |

## Working now

### Hosted deployment (verified 2026-11-03)

- The full application — SPA **and** `/api/v1` — runs from one Vercel project. The
  root `app.py` is the entrypoint; Vercel's Large Functions beta
  (`VERCEL_SUPPORT_LARGE_FUNCTIONS=1`, up to 5 GB) carries the RDKit dependency
  that the 500 MB Python limit used to block.
- Verified on the deployment: `/api/v1/health` → ok, `/api/v1/ready` →
  `database: ok`, `/api/v1/projects` → a demo project with 16 compounds and a
  computed triage run, `/` and `/lab` → the SPA shell, and a workflow submitted
  over HTTP finishing `succeeded` in 2.1 s with `HCS_RUN_MODE=inline`.
- `HCS_DATABASE_URL` switches the state to any SQLAlchemy URL (PostgreSQL via the
  `postgres` extra and the BSD-3-Clause `pg8000` driver). Engine caches are keyed
  by URL; `public_dict` reports the backend, never the URL. Unit-tested at the URL
  and engine layer only — no deployment against a real PostgreSQL server has been
  exercised, and there is no PostgreSQL migration test.
- Not durable on the host: the SQLite file and run artifacts live on `/tmp` and are
  rebuilt per instance. Object storage is not implemented. The deployment stays
  behind Vercel Authentication.

### Data

- Project create/list/show/delete.
- Dataset import from CSV, SDF and `.smi`, with auto-detection and explicit
  column mapping.
- Standardisation: salt stripping (default), optional neutralisation, optional
  canonical tautomer.
- Row-level outcomes, retained failures, duplicate retention, SHA-256 checksum.
- Dataset listing, error inspection and deletion.
- Compound library search/filter, compound detail, identifier copy and SVG
  depiction.

### Workflows

- Three built-in templates.
- Visual editor with add/remove nodes, config forms, validation and save.
- YAML/JSON validation with structured issue codes.
- Built-in nodes: RDKit descriptors, Morgan/Tanimoto similarity, rule filters,
  Pareto/composite ranking, Markdown/HTML summary.
- Save, show, update, delete; runs keep immutable snapshots.

### Execution

- Persistent SQLite queue with lease claim, heartbeat and expired-lease recovery.
- Embedded worker in `serve`, standalone worker, `--once` drain.
- Per-node timeout, cancellation at safe points, retry with a new run.
- Content-addressed node cache with implementation and engine versions.
- SSE event stream and CLI log following from the same rows.
- Results persisted as rows plus JSON/CSV; artifacts hashed and downloadable.
- Packed fingerprints stored once per dataset (checksummed), so repeated similarity
  searches do not re-fingerprint the library; a changed dataset or a damaged blob is
  detected and rebuilt.
- Manifest with workflow snapshot, dataset checksum, environment, hardware,
  cache keys, artifacts and limitations.

### Interface and automation

- Workspace, project, library, compound, workflows, editor, run monitor,
  results, runs, models, data sources, settings, about and not-found pages.
- Light/dark themes and narrow layout reviewed at 1440 and 390 widths.
- Versioned `/api/v1` API with OpenAPI at `/api/v1/openapi.json`.
- CLI commands for every shipped action, including destructive operations with
  confirmation and `--json`.
- HTML/Markdown/JSON/CSV report export.
- Loopback-only default, bearer token for non-loopback, CSP/security headers,
  redacted errors, request IDs.

### Packaging and quality

- Self-contained wheel bundling the built SPA; smoke-tested locally on port 8793
  and by the CI wheel job.
- <!-- gen:tests -->582 passed, 0 skipped<!-- /gen:tests --> backend tests on the
  development host (the live docking tests are deselected there because no Vina
  binary is installed), and the same suite in CI on Linux with the binary
  installed.
- <!-- gen:coverage -->83 % branch coverage<!-- /gen:coverage --> locally; the CI floor
  is 70 %.
- 11 Playwright end-to-end tests passing locally (studio journey, planned engines,
  unknown runs, RDKit WebAssembly self-test, WebGPU parity, the offline lab at
  360 px and the SEO/404 checks).
- Ruff format/check and mypy clean locally and in CI.
- Frontend typecheck and production build clean locally and in CI.
- Visual and accessibility QA: 18 routes × 6 widths (incl. 640 px = 200% zoom) ×
  2 themes = 192 captures, 0 automatic findings, screenshots reviewed by hand.
- Genuine screenshots in `docs/screenshots/`.
- GitHub Actions run
  [40677454655](https://github.com/timfromhcs/hcs-discovery-studio/actions/runs/40677454655)
  passed every required job on commit `2420016`: Ubuntu and Windows backend
  gates, frontend build, Playwright, clean SQLite migration, wheel smoke test,
  license policy, dependency audit, documentation links, secret scanning and the
  aggregate summary. CodeQL run
  [40677454641](https://github.com/timfromhcs/hcs-discovery-studio/actions/runs/40677454641)
  also passed.

### Published release

- Tag `v0.1.0` points at commit `2420016`. Release workflow run
  [40677691377](https://github.com/timfromhcs/hcs-discovery-studio/actions/runs/40677691377)
  built, attested and published the prerelease
  [`v0.1.0`](https://github.com/timfromhcs/hcs-discovery-studio/releases/tag/v0.1.0).
- Assets: `hcs_discovery_studio-0.1.0-py3-none-any.whl`
  (SHA-256 `c40674667d67a85409d70a36bba8fd28ae8933867f47f2885cd94ab09ec0e33e`),
  `sbom.cdx.json`
  (SHA-256 `17c668dec0808c1ccab6724aff6c69baaa34f5ebd3d40f6dd4a1d0a741087c96`)
  and `SHA256SUMS.txt`. The published checksums match the downloaded files.
- `gh attestation verify` succeeds for the wheel, so the SLSA build provenance
  is present and tied to this repository's release workflow.
- The downloaded wheel was installed into a fresh virtual environment and
  `hcs-discovery version` printed `HCS Discovery Studio 0.1.0`.

## Partial

| Feature | What exists | What is missing |
|---|---|---|
| Docking | Vina adapter, flexible-ligand PDBQT, per-ligand status, pose SDF with bonds, receptor confinement, single-complex redocking gate | Multi-target pose-recovery benchmark; receptor preparation; protonation/tautomer enumeration; flexible macrocycles |
| HAEL scheduler | Typed evidence with units/gates, acquisition rule, measured cost model, deterministic trace, synthetic matched-budget ablation, 94 tests | No workflow node, API route, CLI command or UI; two objective dimensions maximum; no evaluation on a real task |
| Property estimates | Reduced ESOL with measured independent-set metrics; CNS MPO approximation | Full published ESOL fit; computed ClogD/pKa; calibrated uncertainty |
| Research agent | Ask/Plan/Run with allowlisted tools, digest-bound plans, optional local LLM for Ask | LLM-based planning; resource estimates; a UI page |
| Auth | Static bearer token for non-loopback | No users, roles, per-project ACLs, token expiry or rotation |
| Audit | Audit rows for project/dataset/workflow/run mutations | No audit viewer or export |
| Target/structure records | Service + API + CLI with provenance, checksums and inspection | No UI page; no binding-site/box definition; no receptor preparation; PDB only (mmCIF refused) |
| Predictions table | Migrated schema | No writer and no UI |
| PostgreSQL | SQLAlchemy-compatible models | No tested PostgreSQL deployment or queue semantics |
| Observability | Metrics endpoint + structured logs + run events | `GET /api/v1/metrics` (Prometheus text) with build, uptime, entity counts, runs by status, queue depth, cache size and GPU availability; no traces, dashboards or alerting yet |

## Not implemented

- Molecular dynamics (OpenMM).
- Learned ADMET/activity prediction (Chemprop or any other model).
- Structure prediction (Boltz-2, Chai-1).
- GPU execution of any scientific engine other than the Tanimoto similarity kernel
  (descriptors, docking and property estimates run on the CPU).
- Popcount-bound prefiltering (BitBound), ANN indexes and GPU fingerprint
  generation for similarity search.
- Target explorer UI, pocket detection, binding-site definition and receptor preparation.
- Loops, conditionals, sub-workflow composition or parameter sweeps.
- Distributed workers, Redis/Celery, multi-tenant hosting.
- Docker image, Helm chart or cloud deployment.
- User accounts, SSO, collaboration, comments.
- Experimental validation of any score.
- Signed release artifacts (GPG or cosign) and container attestations. The wheel
  carries a GitHub build-provenance attestation.
- Published coverage badge or coverage upload to a third-party service.

## Release-gate assessment for v2.0.0

Evidence below was produced on `main` at commit `12febcf` and re-run locally on
2026-11-01 on the working tree that follows it.

| Gate | Status | Evidence |
|---|---|---|
| Lint, format, types | Pass locally and in CI | Ruff, mypy (89 source files) |
| Backend tests | Pass locally and in CI | <!-- gen:tests -->582 passed, 0 skipped<!-- /gen:tests --> on the development host (the skips are the live docking tests); <!-- gen:coverage -->83 % branch coverage<!-- /gen:coverage -->; Hypothesis properties for ranking and joins; HAEL modules ≥94% |
| Frontend build and E2E | Pass locally and in CI | typecheck, build, 3 Playwright tests on isolated data |
| Visual QA | Pass locally | `apps/web/scripts/visual_qa.mjs`: 18 routes × 6 widths (incl. 640 px = 200% zoom) × 2 themes = 192 captures, WCAG AA text contrast, heading order, keyboard focus; screenshots reviewed by hand |
| Fresh migration and wheel | Pass locally and in CI | Wheel ships Alembic scripts and records a revision; wheel installed into a clean venv and completed db upgrade → project → import → run → results |
| Cache provenance | Pass | Package fingerprint, detected Vina version and receptor hash in keys |
| CodeQL, secret scan, audits, licenses | Pass in CI | Required jobs on the PR and on `main` |
| Docking reference validation | Pass (one complex) | 1IEP redocking: HCS preparation 0.42–0.94 Å, Vina-example control 0.29–0.37 Å, 5 seeds; CI job `science-vina` enforces ≤ 2.0 Å ([report](../validation/vina-redocking-1iep.md)) |
| Release workflow | Hardened, untested end to end | Exact-SHA CI/CodeQL gate, draft-then-verify; the release-candidate run will be its first real execution |
| Release candidate published and verified | **Not met** | No tag pushed yet |

GEMINI.md required an executed Vina redocking/reference result before Stable;
that now exists for one complex. Publishing still requires a release-candidate
run of the release workflow and owner approval for tagging.

## Known defects and risks

- Project deletion removes run directories and uploads; shared node-cache
  entries remain until `hcs-discovery cache prune`.
- SQLite serialises writers; concurrency above 1 is not beneficial.
- The SPA is served from the wheel; a source sdist build without a prebuilt
  `apps/web/dist` has no UI.
- No TLS or reverse-proxy configuration is shipped.
- The LLM provider is untested against every compatible server.
- RDKit 2026.9.1 ships `rdkit-stubs` with invalid Python syntax
  (`rdkit.rdBase._vectunsigned int`), which aborts mypy. The backend CI job and
  `scripts/ci/prepare_typecheck.py` remove that stub package; RDKit remains an
  untyped dependency by design.
- Report tables truncate at 200 rows in Markdown and 500 in HTML; the JSON/CSV
  exports are complete.
- The `targets`, `structures` and `predictions` tables are reserved and may
  change before they are used.
- `rdkit.Chem.Draw` links against `libXrender`/Cairo. Hosts without it (the Vercel
  Python image, minimal containers) return `424 missing_dependency` from
  `/api/v1/compounds/{id}/depiction.svg`; depictions are unavailable there, and
  nothing else is affected because the import is lazy.
- On a serverless host, `HCS_RUN_MODE=inline` executes one run inside the
  submitting request. A run longer than the function duration is killed, its lease
  expires and stale-run recovery retries it; there is no background worker.

## How to verify a claim

Every "working" item above can be checked with a command in
`docs/user-guide/CLI.md` or a test in `docs/developer-guide/TESTING.md`. If a
claim cannot be reproduced, treat it as a documentation bug and open an issue.

