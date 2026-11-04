# Implementation status

Last updated: 2026-11-04. Version: `3.0.0`. `3.0.0` adds exact bound-pruned k-NN,
the batched multi-query kernel, RO-Crate provenance export, the MCP `2026-07-28`
protocol, the full Delaney ESOL benchmark and a four-platform release matrix; see
[the release notes](../releases/v3.0.0.md) and
[the plan](PLAN_2026-11-04_SOTA_V3.md).

This document is the honest feature ledger. It distinguishes what has been exercised
end-to-end from what is scaffolded, planned or deliberately absent. "Working" means it
has been run locally and is covered by at least one automated test or a recorded manual
check; it does not mean validated science.

## Summary

| Area | Status | Evidence |
|---|---|---|
| Environment audit | Done | `doctor` on Windows 11; versions recorded in AGENT_LOG |
| Repo skeleton and tooling | Done | `pyproject.toml`, lockfiles, Ruff, mypy, pytest, Vite, Playwright |
| Domain model and migrations | Done | SQLAlchemy models, Alembic revisions, migration tests |
| Persistent queue | Done | Lease claim, heartbeat, recovery, cancellation, retry tests |
| RDKit import/standardise | Done | CSV/SDF/SMILES, row outcomes, descriptor tests |
| Workflow engine | Done | Validation, execution, cache, events, manifest tests |
| CPU scientific slice | Done | Descriptors → filters → Pareto/composite → summary with integrity checks |
| React UI | Done for shipped features | Visual QA + axe gate; run timeline; four-platform screenshots |
| CLI/API parity | Done for shipped actions | Shared services; CLI tests; new `similarity screen` |
| Local LLM provider / Safe Research Agent | Done | Ask, Plan, Run modes with strict allowlisted tools |
| AutoDock Vina docking | Runs; reference-tested on one complex | Host-dependent binary; ligand PDBQT matches Meeko on 48/51 fixtures; 1IEP redocking ≤ 0.94 Å over 5 seeds, enforced in CI; not benchmarked across targets |
| Property estimates | Runs; one measured reproduction and one approximation | Delaney ESOL: full-set RMSE 1.099 / R² 0.725, held-out scaffold split RMSE 1.201 / R² 0.640, published with baseline; CNS MPO approximation |
| PubChem / ChEMBL connectors | Done | Policy-gated; mocked-transport tests; blocked by default |
| DAG Workflows | Done | Multi-branch DAGs, Kahn topological sort, `table.join` with strict-key checks |
| HAEL adaptive scheduler | Experimental, library only | Typed evidence gates, cost model, deterministic trace, 94 property/guard tests ([design](../research/HAEL.md)); no workflow node, API, CLI or UI yet |
| GPU similarity search | Done (Tanimoto only) | Shared WGSL kernel via `wgpu-py`; exact k/threshold search with the popcount bound; bit-identical to RDKit; measured in [gpu-tanimoto.md](../validation/gpu-tanimoto.md) |
| Batched multi-query | Done | `tanimoto_batch.wgsl`, `search_many`, `similarity screen`; 10.9× (100k) and 9.7× (500k) over per-query; parity per query |
| Browser compute | Done (opt-in) | RDKit WebAssembly self-test and WebGPU Tanimoto benchmark on the Settings page |
| RO-Crate export | Done (RO-Crate 1.1, not WRROC-profile) | CLI, API, UI; JSON-LD, PROV mapping, artifact hashes, deterministic ZIP; missing artifacts abort |
| MCP server | Done (dual-era) | stdio; `2026-07-28` `server/discover` + legacy `initialize`; tests for both eras |
| Observability | Metrics endpoint + run latency histograms | `/api/v1/metrics`; no traces, dashboards or alerting |
| PostgreSQL | Done (real server) | Disposable `postgres:16-alpine` container: migrations, a full run, four workers racing one claim (exactly one wins), `/ready` and stale-lease recovery; `HCS_DATABASE_URL` now actually reaches the setting (regression test) |
| Performance budgets | Done | Lighthouse on the static build: workspace 96 / lab 98 performance, 100 accessibility, LCP 2.4 s / 1.8 s, CLS 0.007 / 0, TBT 104 / 36 ms; budgets and caveats in [lighthouse.md](../validation/lighthouse.md) |
| GitHub CI | Green on `main` @ `da8e079` | CI 41803154577 (Windows + Linux, Vina, E2E, wheel, EXE, docs, licenses, secrets) and CodeQL 41803154693 |
| Public release | `2.2.1` is published; `3.0.0` is prepared on `main` | Tag/upload are owner-gated; the release workflow builds four binaries and the container |

## Working now

### Similarity search

- Exact Tanimoto search over Morgan/ECFP r=2, 2048-bit fingerprints.
- CPU reference and a Vulkan/D3D12/Metal kernel through `wgpu-py`; every GPU count is
  compared with the CPU reference before a value is returned.
- Threshold search with the BitBound prefilter.
- Exact k-NN with the popcount bound, staged into few large dispatches (the naive
  ring-per-dispatch version was 14× slower and is not shipped).
- Batched multi-query search (`search_many`, `similarity screen`) with per-query
  parity.
- Dataset fingerprint cache with a compound-set checksum and a blob checksum.
- CLI, API and MCP use the pruned path whenever a full score vector is not requested.

### Provenance and automation

- Run manifests with workflow snapshot, dataset checksum, environment, hardware,
  cache keys and artifact hashes.
- RO-Crate 1.1 export (ZIP): JSON-LD context, `CreateAction`/`prov:Activity`,
  `prov:Plan`, software/environment records, artifact SHA-256. Not claimed as
  Workflow Run RO-Crate conformant.
- MCP stdio server: `2026-07-28` discovery and per-request versioning, plus the
  legacy handshake; read-only tools with bounded inputs.
- Prometheus text metrics, including run and node latency histograms derived from
  persisted timestamps.

### Data, workflows, execution and interface

- Project/dataset/compound lifecycle; CSV/SDF/SMILES import with row-level outcomes.
- Standardisation (salt stripping, neutralisation, tautomer) with transformation
  records.
- DAG workflow editor, validation with structured issues, immutable run snapshots.
- Persistent SQLite queue with lease claim, heartbeat, expiry recovery and
  cancellation.
- Content-addressed node cache with atomic publication and tamper detection.
- SSE events, CLI log following, retry, report export (HTML/Markdown/JSON/CSV/SDF/
  RO-Crate).
- Workspace, project, library, compound, workflows, editor, run monitor, results,
  runs, models, data sources, settings, about, lab and not-found pages.
- Light/dark themes, narrow layouts, focus handling, axe gate.

### Hosted deployment (verified 2026-11-03)

- One Vercel project serves the SPA and `/api/v1`; Large Functions carry RDKit.
- `/api/v1/health`, `/api/v1/ready`, the SPA shell and a submitted workflow were
  verified on the deployment.
- Not durable: SQLite and run artifacts live on `/tmp`; object storage is a follow-up.

## Partial

| Feature | What exists | What is missing |
|---|---|---|
| Docking | Vina adapter, PDBQT preparation, per-ligand status, pose SDF, receptor confinement, 1IEP redocking gate | Multi-target pose-recovery benchmark; receptor preparation from PDB; protonation/tautomer enumeration |
| Property estimates | Delaney ESOL reproduction with a full-set benchmark and a held-out split; CNS MPO approximation | A learned model (Chemprop/TDC) and calibrated uncertainty |
| HAEL scheduler | Typed evidence, acquisition rule, cost model, deterministic trace, synthetic ablation | Workflow node, API, CLI, UI, real-task evaluation |
| Research agent | Ask/Plan/Run with allowlisted tools, digest-bound plans | LLM-based planning; a UI page |
| Auth | Static bearer token for non-loopback | Users, roles, ACLs, expiry, rotation |
| Audit | Audit rows for mutations | Viewer and export |
| Target/structure records | Service + API + CLI with provenance and inspection | UI page, binding-site definition, receptor preparation, mmCIF |
| PostgreSQL | SQLAlchemy-compatible models, tested against a real 16 container | No managed/production deployment exercised; no distributed workers |
| Observability | Metrics + histograms + structured logs | Traces, dashboards, alerting |
| RO-Crate | RO-Crate 1.1 with PROV mapping | Workflow Run RO-Crate per-step profile |

## Not implemented

- Molecular dynamics (OpenMM).
- Learned ADMET/activity prediction (Chemprop or any other model).
- Structure prediction (Boltz-2, Chai-1).
- GPU execution of any scientific engine other than the Tanimoto kernel.
- ANN indexes (deliberately absent: exact bounds keep recall at 1.0; see the 2020
  indexing benchmark in the plan).
- GPU fingerprint generation (RDKit has no Vulkan path).
- Multi-target docking accuracy claims.
- Target explorer UI, pocket detection, receptor preparation.
- Loops, conditionals, sub-workflow composition or parameter sweeps.
- Distributed workers, Redis/Celery, multi-tenant hosting.
- User accounts, SSO, collaboration, comments.
- Experimental validation of any score.
- HTTP MCP transport and MCP tasks extension.
- i18n of the UI (the guides are EN/DE/FR).
- Signed artifacts with GPG/cosign (GitHub build provenance attestations exist).

## Release-gate assessment for 3.0.0

| Gate | Status | Evidence |
|---|---|---|
| Lint, format, types | Pass locally | Ruff (229 files), mypy (103 source files) |
| Backend tests | Pass locally | <!-- gen:tests -->635 passed, 4 skipped<!-- /gen:tests --> backend tests; <!-- gen:coverage -->83 % branch coverage<!-- /gen:coverage -->; Hypothesis properties for ranking, joins and similarity |
| Frontend build and E2E | Pass locally | typecheck, build, Playwright suite |
| Visual QA | Pass locally | routes × widths × themes; axe gate over the main routes; bundle budget |
| Fresh migration and wheel | Pass locally | Wheel ships Alembic scripts; installed into a clean venv; PostgreSQL migrations run in G16 |
| PostgreSQL | Pass locally and in CI | G16 / `postgres` job: real server, run, claim exclusivity, lease recovery |
| Lighthouse budgets | Pass locally | G17 / `lighthouse` job: performance, accessibility, LCP, CLS, TBT on the static build |
| Docking reference validation | Pass (one complex) | 1IEP redocking ≤ 0.94 Å over 5 seeds; CI job `science-vina` |
| Similarity parity | Pass | Exact counts and top-10 identity on the adapter; CLI/API/MCP share the path |
| RO-Crate | Pass | Structure, hashes, determinism and missing-artifact refusal tests |
| MCP | Pass | Modern and legacy sessions in one stdio subprocess test |
| ESOL benchmark | Pass | `validate_esol_delaney.py --check` matches the committed report |
| Platform binaries | Prepared | Release workflow builds Windows x64, Linux x64, macOS arm64/x64 and GHCR |
| Release published | **Owner-gated** | Tag `v3.0.0` and PyPI/DOI require the owner |

## Known defects and risks

- SQLite serialises writers; concurrency above 1 is not beneficial.
- The SPA is served from the wheel; a source sdist without `apps/web/dist` has no UI.
- No TLS or reverse-proxy configuration is shipped.
- The LLM provider is not tested against every compatible server.
- RDKit 2026.9.1 ships stubs that mypy cannot parse; CI removes them.
- Report tables truncate at 200 rows in Markdown and 500 in HTML; JSON/CSV are
  complete.
- `rdkit.Chem.Draw` needs `libXrender`; hosts without it return `424
  missing_dependency` from the depiction endpoint.
- On a serverless host, `HCS_RUN_MODE=inline` executes one run inside the submitting
  request; a longer run is retried after its lease expires.
- The k-NN bound costs about 15 % on an unclustered library (measured 0.85×); the
  report states this rather than hiding it.

## How to verify a claim

Every "working" item above can be checked with a command in
`docs/user-guide/CLI.md` or a test in `docs/developer-guide/TESTING.md`. If a claim
cannot be reproduced, treat it as a documentation bug and open an issue.
