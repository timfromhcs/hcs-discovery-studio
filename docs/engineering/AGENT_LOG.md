# Agent log

Chronological engineering log for HCS Discovery Studio. Dates are local
(Windows 11, UTC+1 unless noted). This log records what was actually run and
observed; it is not a marketing summary.

## 2026-10-28 — Phase 0: environment audit

- Confirmed working directory `D:\DrugsDisc`, created
  `D:\DrugsDisc\hcs-discovery-studio`, copied `GEMINI.md` into it.
- Host: Windows 11 build 26200, AMD Ryzen 7 7735HS, 19.8 GB RAM.
- Vulkan 1.4.357 detected on the AMD Radeon integrated GPU via `vulkaninfo`.
  Recorded as hardware presence only; no model support implied.
- No CUDA toolkit. No Docker requirement adopted.
- Installed/verified: git, GitHub CLI, uv, Node 22.23.1, npm 10.9.8.
- Decision: Python 3.12 via uv; RDKit 2026.9.1; CPU baseline.

## 2026-10-28 — Phase 1: skeleton and contracts

- Created `pyproject.toml` with FastAPI, Uvicorn, Pydantic, SQLAlchemy,
  Alembic, RDKit, Typer, PyYAML, Jinja2 and python-multipart.
- Created `apps/web` with React 19, TypeScript, Vite, React Router and TanStack
  Query.
- Chose an original CSS design-token system over Tailwind, inline SVG icons over
  an icon package, and SVG charts/DAG over React Flow. Reason: fewer
  dependencies, full control of the visual language, no license surprises.
- Console script is `hcs-discovery`. `uv run hcs ...` is not a valid command.
- Added `.env.example`, `.editorconfig`, `.gitattributes` and `.gitignore`.

## 2026-10-28 — Phase 2: domain model, queue, migrations

- Implemented SQLAlchemy models for projects, datasets, dataset rows, compounds,
  workflows, runs, run nodes, run events, run results, artifacts, audit events,
  plus reserved targets/structures/predictions.
- IDs use prefixes: `prj_`, `dts_`, `cmp_`, `wfl_`, `run_`.
- Implemented a lease-based SQLite queue: conditional claim, heartbeat, expiry
  recovery, at-least-once execution.
- Implemented a content-addressed node cache keyed by node type/version,
  implementation hash, config, input hash, engine versions and schema version.
- Alembic is the schema authority. `init_db` upgrades, stamps legacy databases
  and falls back to `create_all` only when migration assets are absent.
- Added the initial migration `20261028_558a25772f08_initial_schema.py`.

## 2026-10-28 — Phase 3: scientific vertical slice

- Implemented CSV/SDF/SMILES import with per-row outcomes and standardisation.
- Implemented RDKit descriptors, Morgan/Tanimoto similarity, rule filters,
  Pareto fronts, weighted composite score and summary artifacts.
- Imported the demo library: 16 of 17 rows valid, one intentional invalid row
  retained as an error.
- Ran a four-node triage workflow successfully; Naproxen ranked first under the
  configured weights. This is a prioritisation result, not an efficacy claim.
- Added run manifests with workflow snapshot, dataset SHA-256, Python/RDKit
  versions, CPU description, artifact checksums and limitations.

## 2026-10-28 — Phase 4: UI and visual QA

- Built 13 routes: workspace, project, library, compound, workflows, workflow
  editor, run monitor, results, runs, models, data sources, settings, about,
  plus not-found.
- Added light/dark themes (`hcs.theme` localStorage key) and a narrow layout.
- Captured genuine screenshots with Playwright at 1440 and 390 widths. No
  screenshots of unimplemented features were created.
- Visual defects found and fixed:
  - project danger-zone layout and two-up grid spacing;
  - toolbar/select stretching and palette search-field stretching;
  - table spacing and sub-second duration formatting;
  - `1 project` grammar;
  - compound identifier copy buttons (`.copy-inline`, `.identifier-row`);
  - horizontal page overflow in run monitor/project (`min-width: 0` on grid
    children);
  - `.overview-grid.two-up` collapse at ≤820 px;
  - narrow scatter chart minimum width;
  - horizontal scrollbar styling.
- Results page: Pareto scatter uses `pareto_front === 1`; rejected rows show `—`
  and are described as not ranked.

## 2026-10-28 — Phase 5: CLI/API parity and provider probe

- Implemented `/api/v1` routes for projects, datasets, compounds, workflows,
  runs, models, system, cache and reports.
- Implemented CLI commands for doctor, serve, worker, projects, datasets,
  compounds, workflows, runs, reports, models, config, cache and database.
- `--json` is hoisted so it works before or after the subcommand.
- Added a local OpenAI-compatible provider with policy enforcement. There is no
  chat UI or LLM node; the probe is the only network path.
- Added redaction for logs, events, errors and config output.
- Added bearer-token enforcement for non-loopback binds, CORS for loopback dev,
  security headers, request IDs, rate limiting and upload limits.
- Added CLI parity commands during the release pass: `project delete`,
  `dataset delete`, `workflow show/save/delete`, `run retry`.

## 2026-10-28 — Phase 6: engine registry

- RDKit is the only runnable scientific engine.
- Added adapter cards with license, capabilities, device providers, network
  requirement and status.
- Added planned cards for AutoDock Vina, OpenMM, Chemprop, Boltz-2 and Chai-1.
  They are `planned`, `implemented=false` and not offered as workflow nodes.
- Added a Vulkan probe that reports devices and explicitly sets
  `model_support: "unknown"`.

## 2026-10-28 — Phase 7: tests and resilience

- Backend gates run locally:
  - `uv run pytest -q` → **82 passed** (warnings from Alembic/Starlette).
  - `uv run ruff format --check .` → clean.
  - `uv run ruff check .` → clean.
  - `uv run mypy` → clean.
- Frontend gates run locally:
  - `npm run typecheck` → clean.
  - `npm run build` → clean.
  - `npm run test:e2e` → **3 passed** on a dedicated server at
    `127.0.0.1:8791` with `.e2e-data`.
- E2E covers the main journey, planned-engine visibility and an unknown-run
  error state.
- Fixed the results `columns` payload for legacy runs by falling back to
  `results.json`; the Results page now renders 16 columns and the column
  meanings panel.
- Corrected Pareto semantics: filter-failing rows are excluded and receive
  `pareto_rank = null`.
- Added `min-width: 0` and responsive fixes after real screenshots exposed
  horizontal overflow.

## 2026-10-28 — Packaging

- Added `[tool.hatch.build.targets.wheel.force-include]` to bundle
  `apps/web/dist` as `hcs_discovery/web`.
- Changed `api/app.py` to resolve the packaged SPA first and fall back to the
  repo build. Initially placed the `WEB_DIST` assignment before the function
  definition; fixed the `NameError` and rebuilt.
- Built `dist/hcs_discovery_studio-0.1.0-py3-none-any.whl`.
- Inspected the wheel: `hcs_discovery/web/index.html`,
  `hcs_discovery/web/favicon.svg` and both assets are present.
- Installed the wheel with `--no-deps` into a temp venv and ran the server on
  port 8792 with `PYTHONPATH` pointing at the wheel site-packages:
  - `/` → HTTP 200 and the SPA root element present;
  - `/api/v1/health` → `{"status":"ok",...}`.
- Confirmed the app imported from the temp wheel, not the repo.

## 2026-10-28 — Documentation and release preparation

- Wrote root `LICENSE` (Apache-2.0), `NOTICE`, `CITATION.cff`, `CHANGELOG.md`,
  `SECURITY.md`, `CODE_OF_CONDUCT.md` and `CONTRIBUTING.md`.
- Wrote the required docs set: architecture (overview, workflow engine, plugin
  API, data model), user guide (Windows/Linux install, quickstart, CLI,
  workflows, local models, scientific limitations), developer guide
  (contributing, testing), research audit, validation protocol, threat model and
  engineering status/log.
- Added CI/release/CodeQL workflows and Dependabot configuration. Actions are
  pinned to commit SHAs resolved from the GitHub API.
- Decision: release as `0.1.0` preview, not `1.0.0`, because only RDKit is
  runnable and no predictive validation exists.

## 2026-10-28 — Responsive audit, CI hardening and release candidate

- Re-ran the frontend typecheck and production build after the responsive CSS
  changes; both are clean.
- Added a temporary Playwright overflow audit and ran it against every main
  route at 390 px. It reported real overflow in the project datasets table, the
  compound library, the workflow node table and the settings environment table.
  The audit script was deleted after use; it is not part of the shipped tooling.
- Fixed narrow layouts by hiding secondary columns deliberately, ellipsizing
  identifiers, stacking card headers when their actions do not fit, and letting
  the environment table stack label above value. The library now states that
  narrow screens show name and structure and points to the compound page for
  descriptors.
- Re-captured all 28 documentation screenshots from the running application and
  inspected the narrow captures. No page-level horizontal overflow remains.
- Removed the stale `results-light.png`; the README references
  `results-fixed-light.png`, which is the current capture.
- Fixed `uv sync --frozen` on a fresh checkout: the Hatch wheel target
  force-includes `apps/web/dist`, which does not exist before the SPA is built.
  Added `hatch_build.py` to create the directory during editable installs.
  Release builds still compile the frontend before building the wheel.
- Fixed CI mypy failures caused by RDKit 2026.9.1's bundled `rdkit-stubs`
  (invalid `rdkit.rdBase._vectunsigned int` syntax and incomplete descriptors).
  Added `scripts/ci/prepare_typecheck.py` and a backend CI step that removes
  only that stub package before mypy.
- Shortened the secret-redaction test fixture so it no longer resembles a real
  GitHub token and cannot trip the gitleaks scan.
- Initialized Git, scanned the staged tree for credentials and large files,
  committed, and published the public repository
  `timfromhcs/hcs-discovery-studio`.
- Cloud CI run
  [40676916640](https://github.com/timfromhcs/hcs-discovery-studio/actions/runs/40676916640)
  is green: Ubuntu and Windows backend gates, frontend build, Playwright E2E,
  clean SQLite migration, wheel smoke test, license policy, dependency audit,
  documentation links, secret scanning and the aggregate summary. CodeQL run
  [40676916587](https://github.com/timfromhcs/hcs-discovery-studio/actions/runs/40676916587)
  is also green.
- Committed the release candidate as `2420016` and confirmed the follow-up CI
  run
  [40677454655](https://github.com/timfromhcs/hcs-discovery-studio/actions/runs/40677454655)
  and CodeQL run
  [40677454641](https://github.com/timfromhcs/hcs-discovery-studio/actions/runs/40677454641)
  were green before tagging.
- Pushed tag `v0.1.0`. Release workflow run
  [40677691377](https://github.com/timfromhcs/hcs-discovery-studio/actions/runs/40677691377)
  built the wheel, generated a CycloneDX SBOM and `SHA256SUMS.txt`, attested the
  build provenance and published the prerelease at
  <https://github.com/timfromhcs/hcs-discovery-studio/releases/tag/v0.1.0>.
- Downloaded every release asset and verified it: the wheel SHA-256 is
  `c40674667d67a85409d70a36bba8fd28ae8933867f47f2885cd94ab09ec0e33e`, the SBOM
  SHA-256 is
  `17c668dec0808c1ccab6724aff6c69baaa34f5ebd3d40f6dd4a1d0a741087c96`, and both
  match `SHA256SUMS.txt`. `gh attestation verify` passes for the wheel.
- Installed the downloaded wheel into a fresh virtual environment; the packaged
  SPA is present and `hcs-discovery version` prints
  `HCS Discovery Studio 0.1.0`.
- Found the `Dependency review` job failing on every pull request because the
  repository had Dependabot alerts and the dependency graph disabled. Enabled
  Dependabot alerts through the API; the dependency graph then reported 189
  packages and dependency review passes.
- Merged the three Dependabot major upgrades after their PR workflows went green:
  Vite 8.3.5 (#2), `@vitejs/plugin-react` 6.1.2 (#3) and TypeScript 7.0.2 (#1).
  Rebuilt the SPA locally with the new toolchain; the production build succeeds
  and the Playwright suite passes in CI.
- Untracked `apps/web/tsconfig.tsbuildinfo`, which had been committed by mistake,
  and added `*.tsbuildinfo` to `.gitignore`.
- Re-captured the documentation screenshots against the rebuilt SPA to confirm
  visual parity, then discarded them because the only difference was relative
  timestamps ("2 h ago" versus "3 h ago"). The committed images remain the ones
  captured for the release.

## 2026-10-28 — Phase 0: v1.0.0 Stable baseline audit

- Mandate adopted: `GEMINI.md` Autonomous Stable v1.0.0 Engineering Mandate.
- Confirmed environment: Windows 11 Build 26200, AMD Ryzen 7 7735HS, 19.8 GB RAM.
- Vulkan 1.4.315 / 1.4.357 verified on AMD Radeon Graphics iGPU via `vulkaninfo`.
- Baseline gates reproduced locally:
  - `uv run ruff format --check .` -> clean (108 files)
  - `uv run ruff check .` -> clean
  - `uv run mypy` -> clean (62 source files)
  - `uv run pytest` -> 82 passed, 0 failed, 75% coverage
  - Frontend: `npm run typecheck` & `npm run build` -> clean (187ms)
  - Playwright E2E: 3 passed (11.2s) on port 8791 with `.e2e-data`
  - Wheel build: `hcs_discovery_studio-0.1.0-py3-none-any.whl`
  - Clean venv wheel install smoke: `/api/v1/health` 200 OK, root SPA served
  - CPU smoke test: project create -> import demo library -> triage workflow -> worker execution -> HTML/MD reports
- Proven defects identified:
  - `OperationalError: no such table: audit_events` when CLI commands like `project create` run on uninitialized DB (init_db was not invoked by get_session_factory).
  - Pareto nondominated sorting order-dependence (needs Deb Fast Non-dominated Sorting algorithm).
  - Filter validation missing strict operator-to-value typing prior to execution.
  - Exception swallowing in descriptor loop.
  - Residual files on deletion and unbounded cache.
- Produced `docs/engineering/STABLE_V1_GAP_ANALYSIS.md`. Entering Phase 1.

## 2026-10-28 — Phase 1: Unit 1 & 2 foundations and scientific correctness

- Unit 1: Database auto-initialization & migration idempotence:
  - Added `ensure_database_initialized` to `src/hcs_discovery/database/base.py`.
  - Added `path_separator = os` to `alembic.ini` to resolve deprecation warnings.
  - Added regression test `test_cli_on_uninitialized_database` in `tests/integration/test_cli.py`.
- Unit 2: Pareto nondominated sorting correctness & objective semantics:
  - Replaced the order-dependent greedy Pareto comparison in `src/hcs_discovery/workflow/nodes.py` with Deb's Fast Non-dominated Sorting algorithm (`fast_nondominated_sort`).
  - Added mathematical property tests proving permutation invariance across 20 shuffles and dominance invariance.
  - Added explicit objective directions and types: `maximize`, `minimize`, `target_range` (with continuous trapezoidal satisfaction formula), `constraint`, and `informational`.
  - Excluded zero-weight objectives from participating in Pareto dominance by default to prevent unintentional distortion.
  - Strengthened `RuleConfig` with Pydantic model validators enforcing finite numeric bounds, automatic bound ordering for `between`, and explicit missing-value handling.
  - Hardened descriptor exception boundaries against catching arbitrary unexpected system exceptions.
  - Test suite expanded to 87 passing tests with 100% clean formatting and mypy.

## 2026-10-28 — Phase 1: Unit 3 Lifecycle, bounded cache & storage hygiene

- Unit 3: Bounded cache management & cascade file deletion:
  - Added configurable `cache_max_mb` (1024 MB) and `cache_max_age_days` (30 days) to `Settings`.
  - Implemented `NodeCache.prune()` with LRU eviction and corrupt entry detection.
  - Implemented `preview_project_deletion()` and updated `delete_project` / `delete_dataset` to safely cascade removal of run directories, artifacts, and uploads without leaving orphaned files.
  - Added CLI `cache prune` and `project delete --dry-run` commands.
  - Added 5 integration tests in `tests/integration/test_lifecycle.py` (92 passing tests). Commit `cf7fe9e`.

## 2026-10-28 — Phase 2: Unit 4 AutoDock Vina CPU docking adapter & workflow node

- Unit 4: AutoDock Vina CPU docking integration:
  - Implemented PDBQT ligand preparation (`prepare_ligand_pdbqt`) with RDKit 3D conformer embedding, MMFF94 force field optimization, Gasteiger charges, and AutoDock atom typing.
  - Implemented receptor PDBQT inspection and spatial bounding box computation (`validate_receptor_pdbqt`).
  - Implemented `VinaAdapter` with CPU execution, subprocess timeouts, cancellation checks, and pose parsing.
  - Implemented `pose_pdbqt_to_sdf` converting docked poses into standard multi-record SDF artifacts with `VINA_AFFINITY_KCAL_MOL` tags.
  - Registered `dock.vina` workflow step in `src/hcs_discovery/workflow/nodes.py`.
  - Updated model registry in `src/hcs_discovery/services/models.py` with honest probing (`available` or `not_configured`, `implemented=True`).
  - Added 8 scientific contract and live docking smoke tests in `tests/scientific/test_vina_adapter.py`.
  - Full test suite: 100 passing tests, 0 warnings (excluding FastAPI testclient deprecation), clean mypy and ruff. Commit `930cfed`.

## 2026-10-28 — Phase 2: Units 5 & 6 property prediction and connectors

- Unit 5: Learned property prediction & scaffold splitting:
  - Implemented Delaney ESOL aqueous solubility model (`esol_solubility`) with leverage-based uncertainty calibration and applicability domain checks.
  - Implemented Wager et al. CNS MPO multi-parameter optimization model (`cns_mpo_bbb`) for blood-brain barrier permeability scoring.
  - Implemented Bemis-Murcko generic/canonical scaffold extraction and leakage-free dataset splitting.
  - Registered `predict.property` workflow step and `science:property-predict` in model catalog.
  - Added 7 scientific validation, contract, and benchmark protocol tests in `tests/scientific/test_property_prediction.py`. Commit `2cd4fe3`.

- Unit 6: Public data connectors (PubChem & ChEMBL):
  - Added strict outbound network policy check (default local-only, explicit opt-in for remote).
  - Implemented PubChem PUG REST client with CC0 license attribution and rate-limiting.
  - Implemented EMBL-EBI ChEMBL client for targets, compounds, and bioactivities with CC-BY-SA 3.0 attribution.
  - Added API routes under `/api/v1/connectors` for status, search, and activity inspection.
  - Added CLI command group `hcs-discovery fetch pubchem` and `hcs-discovery fetch chembl`.
  - Added 7 integration tests with mock transports and policy gating in `tests/integration/test_connectors.py`. Commit `4614d1c`.
  - Full test suite: 114 passing tests, 0 warnings (excluding FastAPI testclient deprecation), clean mypy and ruff.

## 2026-10-28 — Phase 3: Unit 7 Workflow DAG branching, Kahn sorting & table.join

- Unit 7: Workflow DAG branching and key-based join:
  - Implemented Kahn's algorithm for topological sorting of workflow DAGs with cycle and disconnected node detection.
  - Enabled branching / fan-out: multiple child nodes can consume the output table from a single parent or entry node.
  - Implemented `Table.join()` with key-based row alignment (`id`, `smiles`, etc.) supporting `left`, `inner`, and `outer` join semantics.
  - Implemented `table.join` workflow node and updated `RunExecutor` with dictionary-based table routing across DAG branches.
  - Added 4 integration tests in `tests/integration/test_dag_workflow.py` testing DAG branching, Kahn sort, cycle detection, and live worker DAG execution.
  - Full test suite: 118 passing tests, clean mypy and ruff formatting. Commit `1556d89`.

## 2026-10-28 — Phase 5: Safe Research Assistant & Report Truncation Disclosures

- Safe Research Agent:
  - Implemented `ResearchAgent` (`src/hcs_discovery/plugins/llm/agent.py`) supporting three strict operational modes:
    - `Ask`: Read-only queries over available models, dataset summaries, and computational metrics.
    - `Plan`: Formulates validated DAG workflows with schema validation, resource estimates, and limitation disclosures.
    - `Run`: Executes approved typed allowlisted tools with human approval gating.
  - Implemented 10 allowlisted server-side tools in `src/hcs_discovery/plugins/llm/tools.py`.
  - Added prompt-injection defense by isolating untrusted data in `<untrusted_data>` blocks.
  - Added API routes under `/api/v1/agent` and CLI commands `hcs-discovery agent status`, `tools`, `ask`, `plan`, `run`.
  - Added 10 integration tests in `tests/integration/test_agent.py`.
- Report Table Truncation Disclosure:
  - Added prominent disclosure notices in Markdown (>200 rows) and HTML (>500 rows) reports informing users of rendering truncation.
  - Added full complete exports in CSV, JSON, and SDF (`export_report(..., fmt='sdf')`) formats.
  - Commit `abaa3b4`.

## 2026-10-28 — Phase 6: Visual Identity Branding & v1.0.0 Stable Transition

- Original Branding Assets:
  - Designed vector mark `apps/web/public/brand/hcs-discovery-mark.svg` and `docs/assets/branding/hcs-discovery-mark.svg`.
  - Designed wordmark `apps/web/public/brand/hcs-discovery-wordmark.svg` with official brand line:
    `Open science. Reproducible discovery. Made with ❤️ by hcsmedia.`
  - Generated crisp 1280x640 OpenGraph social preview card `docs/assets/branding/social-preview.png` (51.7 KB, well under 1MB GitHub limit).
  - Commit `e4b5864`.
- Version Bump to 1.0.0 Stable:
  - Updated `pyproject.toml` version to `1.0.0` and classifier to `Development Status :: 5 - Production/Stable`.
  - Updated `src/hcs_discovery/__init__.py`, `apps/web/package.json`, `apps/web/src/lib/constants.ts`, and `CITATION.cff`.
  - Re-locked dependencies with `uv lock` (resolved clean).
  - Updated `CHANGELOG.md` with comprehensive release notes for `[1.0.0] - 2026-10-28`.
  - Created `docs/releases/v1.0.0.md` release notes.
  - Verified tag compatibility with `scripts/release/verify_version.py v1.0.0` (PASS).
  - Updated `README.md` and `docs/engineering/IMPLEMENTATION_STATUS.md`.

## Security notes

- A GitHub token was supplied in chat earlier in the project. It was never
  written to a file, committed, printed in a report or included in a screenshot.
  Authentication used the `GH_TOKEN` environment variable as `timfromhcs`.
  Rotation is recommended regardless, because the token appeared in chat.
- No provider API key is configured or required for the demo.
- Local data lives under `data/` and is ignored by Git.

## 2026-10-29 — Phase 8: integrity hardening and measured validation

- Removed fabricated scaffold-test metrics from ESOL model; replaced with 45-molecule independent challenge set from AqSolDB/Llinas et al. 2008, with recomputed RMSE 0.968, R² 0.072 and documented bootstrap CI.
- Model uncertainty column now explicitly labelled as a heuristic descriptor-distance error scale, not a calibrated confidence interval.
- Every workflow node config and agent tool payload now enforces `extra="forbid"`; unknown fields are rejected rather than silently ignored.
- Constraint objectives now gate eligibility: weight forced to zero, excluded from composite scores and Pareto front, exposed via `constraint_pass` / `constraint_reasons` columns.
- `table.join` now rejects duplicate right-side keys and suffix collisions with `ValidationError`.
- Cache entries record table `content_hash` and artifact SHA-256; missing/tampered artifacts are cache misses; partial entries are refused.
- Background `_LeaseHeartbeat` renews leases; `LeaseLostError` prevents stale owners from writing terminal run state.
- Vina probe requires exit code 0 + recognised version output; fabricated `ENGINE_VERSION` removed.
- Connectors block 3xx redirects, raise honest 404 unless `allow_not_found=True`, convert malformed JSON to `ValidationError`, require JSON objects, and normalise allowlisted hosts against case, trailing dot, ports and IDNA lookalikes.
- Agent plans are persisted under `data_dir/agent_plans` with a digest. `run` requires `plan_id` and rejects missing, mutated, reordered or tampered calls. Tool payloads use `extra="forbid"`.
- SSE generator made async with `request.is_disconnected()` and `asyncio.sleep`; stops on client disconnect.
- ESOL metadata updated with measured independent-challenge metrics and citation to Sorkun et al. 2019 AqSolDB.
- New file `scripts/science/validate_esol.py` regenerates `docs/validation/esol-solubility.md` and `esol-solubility.json` from the checked-in fixture.

## 2026-10-29 — Phase 9: local gate audit before first v2 push

Local gates on Windows 11, Python via uv 0.12.3: `uv lock --check`, Ruff format
and lint, mypy, pytest (164 passed, 77% line coverage), license checks, `npm ci`,
`npm audit`, typecheck, build, Playwright E2E (3 passed), wheel build/install
smoke test. Defects found and fixed:

- Installed wheels shipped no Alembic scripts, fell back to `create_all` and never
  recorded a revision (`db current` → "not initialised"), so future migrations
  would not reach wheel installs. Migration scripts are now packaged under
  `hcs_discovery/_alembic`; regression test covers the wheel layout.
- E2E `globalSetup` pointed at `apps/.e2e-data` and never cleaned anything; the
  web server also starts before `globalSetup`, so runs reused stale databases.
  Each invocation now gets its own `.e2e-data/run-*` directory and older ones are
  removed.
- E2E expected the pre-v2 Pareto description; updated to the constraint-aware
  wording the backend now emits.
- README and implementation status claimed a published, verified `v2.0.0`
  release that does not exist (and linked to it with a broken relative URL).
  Status now says release candidate; cloud CI and publication are outstanding.

## 2026-10-29 — Phase 10: GEMINI.md P0/P1 work on `release/v2.0.0`

Each item has a commit on the branch with tests that fail without the fix.

- CI on PR timfromhcs/hcs-discovery-studio#4: the ESOL report recorded the hash
  of a CRLF working copy (fixed by regenerating from the LF bytes); CodeQL
  py/path-injection on agent plan ids (safe_join now uses realpath + prefix).
- Cache keys: package fingerprint, detected Vina version and receptor SHA-256.
  A replaced receptor previously reused stale docking results.
- Receptor paths confined to `<data_dir>/receptors` unless the operator opts in.
- Ligand PDBQT had no torsion tree (all atoms in ROOT). New preparation matches
  Meeko 0.8.0 on 48/51 fixture ligands; 3 differ only by rigid 7+-rings. Root
  causes found on the way: MMFF setup rewrites RDKit aromaticity flags, and
  Meeko picks the root before folding terminal atoms.
- NaN/Infinity rejected in every node config (Vina accepted NaN box centres).
- CNS MPO used invented ClogD/pKa proxies and a fixed uncertainty; replaced by a
  labelled approximation with exact Wager functions.
- Release workflow: exact-SHA CI/CodeQL gate, no release modification, wheel
  smoke test, draft-then-verify. RC tags now map to PEP 440.
- Visual QA sweep (170 captures): className override in Input/Select/Textarea,
  unlabeled Node ID field, 320 px overflow, hidden editor table actions,
  flex `<td>` misalignment.
- Agent Ask hid provider failures; responses now state their source.
- Documentation reconciled with the above.

Open: no Vina redocking benchmark has been run (requires a legally usable
reference complex and receptor preparation). Stable is blocked on it; an RC can
be published with the limitation stated.

## Phase 11 — 2026-10-29, branch `fix/v2-stable-gates` from `556c76d`

Worked through GEMINI.md again from the merged `main`.

- P0 docking: added the 1IEP redocking check (official Vina example, Apache-2.0,
  commit `bb64e5e`, SHA-256 pinned). The acceptance criterion (top pose ≤ 2.0 Å
  for every seed, per arm) was written into the script before the first run.
  `python scripts/science/redock_vina_reference.py --vina bin/vina.exe --gate`,
  Vina 1.2.5 (binary SHA-256 `b5a23b22…`, identical to the official release),
  exit 0: HCS 0.42/0.94/0.87/0.82/0.65 Å, control 0.29/0.37/0.32/0.37/0.30 Å.
  Seed 1 reproduced exactly across two runs. New CI job `science-vina`.
- P0 cache: staged, atomic entry publication; accounting ignores staging.
- P0 ranking/joins: Hypothesis tests against the definition of non-dominated
  fronts, front-limit truncation, permutation invariance, ties, constraint
  separation, aliases and join cardinality. Found and fixed: outer join dropped
  unkeyed right rows; single-input join nodes were accepted.
- P0 chemistry: narrowed `except Exception` in standardisation; tests for
  valence errors, explicit H, stereo, charges, tautomers, uncommon elements.
- P1 connectors: PubChem's 2025 property rename meant every lookup returned no
  structure; mocks still used the old format, so tests passed. Fixed and
  confirmed with a live opt-in test. Policy now applies with mock transports.
- P1 agent: digest-bound, single-use plans; CLI multi-step runs work.
- P1 paths, ESOL domain, misleading Vina RMSD columns.
- Visual QA extended with contrast, headings, keyboard focus and a 640 px
  (200 % zoom) width; fixed the contrast tokens and error-page headings.
- Local gates on Windows 11, Python 3.12.13, uv 0.12.3, Node 22.23.1: ruff,
  mypy, 295 pytest (79.2 % coverage), typecheck, build, 3 Playwright tests,
  wheel `hcs_discovery_studio-2.0.0-py3-none-any.whl` in a fresh venv (version,
  db upgrade to `558a25772f08`, doctor, `/ready`, SPA), full CLI journey
  (import 17 records/16 imported/1 duplicate, run, cache reuse of all 4 nodes,
  manifest artifact hashes verified), 192 visual QA captures with 0 findings.
- Not done: `actionlint` could not be run here (fetching it was not permitted);
  the release workflow has still not run end to end.

## 2026-11-01 — WP0: v2.0.0 release-truth audit and local re-verification

- Ground truth: `main` = `12febcf` (PR #7 merged). Tags exist only for `v0.1.0`
  and `v1.0.0`; `v2.0.0` is **not** tagged or published. CI 40947455326 and
  CodeQL 40947455914 passed on `12febcf`.
- Re-ran every local gate on the working tree: `ruff format --check` (148 files),
  `ruff check`, `mypy` (79 files), `pytest` (297 passed with the Vina binary,
  295 passed + 2 skipped without it, 79% branch coverage), `npm ci`,
  `npm run typecheck`, `npm run build`, 3 Playwright E2E tests,
  `check_licenses.py` (51 packages), `check_licenses.mjs` (11 packages),
  `check_links.py` (35 files), `uv build --wheel`.
- Wheel `hcs_discovery_studio-2.0.0-py3-none-any.whl` installed into a fresh
  Python 3.12 venv; ran `version`, `db upgrade` (→ `558a25772f08`), project
  create, 6/6 row import, workflow submit, `worker --once`, run succeeded.
- Defect found and fixed (1): the library search field had no *instantaneous*
  focus indicator — `.search-field input` has `outline: none` and the wrapper's
  ring was coupled to a 140 ms `box-shadow` transition. Visual QA flagged
  "no visible focus indicator on input" at 1280 px light. Only the resting
  border now animates; the focus ring is immediate.
- Defect found and fixed (2): `workflow run --no-follow` and `run retry
  --no-follow` printed "Waiting for a worker…" and exited 1 in human mode even
  though the run was accepted (`--json` was correct). Both now report the queued
  run with an actionable hint and exit 0; two regression tests added.
- Defect found and fixed (3): following a run with no worker running looked like
  a hang. `_follow_run` now prints a one-time hint after ~5 s that no worker has
  claimed the run.
- Docking evidence reproduced on this host: downloaded the official
  `vina_1.2.5_win.exe` (SHA-256 `b5a23b22…b38f`, the hash already recorded in the
  report), 13/13 live adapter tests pass with `HCS_REQUIRE_VINA=1`, and
  `redock_vina_reference.py --gate` reproduced the published 1IEP numbers
  (hcs 0.42–0.94 Å, vina_example 0.29–0.37 Å, `overall: pass`).
- Documentation drift corrected: `WORKFLOW_ENGINE.md` claimed a linear
  single-input engine with joins rejected; `README.md` and
  `IMPLEMENTATION_STATUS.md` claimed 82 tests and 75–79% coverage on stale
  evidence. All three now state the measured values and the real DAG +
  `table.join` semantics.
- Not done: tag/publication of `v2.0.0` — AGENTS.md §0.2 and §30.4 require
  owner approval for a Stable tag, and the release workflow's first real run is
  the release-candidate run itself.

## 2026-11-01 — WP6: HAEL evidence ladder and scheduler (experimental)

- Added `src/hcs_discovery/hael/`: `units` (registry, no implicit conversion),
  `evidence` (typed items, evaluation failures, objective vectors, gates, Pareto
  frontier, content digest), `cost` (measured p90 with an explicit cold-start
  policy that refuses to guess), `acquisition` (1-D closed-form EI, 2-D seeded
  Monte-Carlo EHVI, analytic Gaussian EIG, scaffold/pocket novelty) and
  `scheduler` (deterministic trace, budget, cancellation, failure recovery).
- 94 tests in `tests/unit/test_hael_{evidence,acquisition,scheduler,guards}.py`.
  Branch coverage: acquisition 99%, evidence 99%, scheduler 94%, cost 95%,
  units 96%.
- Deliberate refusals, each covered by a test: >2 objective dimensions raises
  `UnsupportedObjectiveDimensionError`; an unmeasured and unconfigured cost is
  `unknown_cost` and the action is skipped; an exploratory or out-of-domain item
  cannot enter the validated frontier; several validated values for one
  candidate/dimension are omitted instead of averaged.
- Two bugs found by the tests while writing them: (a) `ledger or EvidenceLedger()`
  silently discards an empty ledger because `__len__ == 0` makes it falsy —
  fixed in the test helper and documented; (b) the no-incumbent EI branch was
  degenerate (it returned `3σ` regardless of the prediction), so a stronger
  prediction did not score higher; it now measures against the dimension's zero
  point.
- Ablation (`scripts/science/benchmark_hael.py`, 20 seeds, synthetic): mean
  regret of the selected candidate — hael −0.285, hael_cost_unaware −0.498,
  descriptor_only −0.519, random −1.140, static_cascade −1.450. HAEL leads, but
  only clearly against uninformed policies; on synthetic data. Recorded as a
  finding, not a promotion: HAEL remains experimental.
- Docs: `docs/research/HAEL.md`, `docs/research/RESEARCH_REGISTER.md`.
- Not done: workflow node, API route, CLI command, UI, real-task evaluation.

## 2026-11-01 — WP2 backbone: targets and structures with provenance

- Added `src/hcs_discovery/structures/pdb.py`: dependency-free PDB inspection
  (models, chains, residues, missing-residue gaps, ligands, waters, ions,
  alternate locations, HEADER/TITLE), 64 MiB size guard, and an explicit
  `unsupported_format` refusal for mmCIF rather than a partial parse.
- Added `src/hcs_discovery/services/targets.py`: target CRUD with provenance and
  case-insensitive duplicate protection; structure import that hashes the exact
  bytes, inspects before writing, and removes the artifact if the file is
  rejected; `target delete` detaches structures instead of destroying evidence.
- Added migration `9f3c1a7d2b48` (`structures.license`). The license was only in
  the audit log before, so a redistribution decision could not be read back per
  structure. `tests/integration/test_migrations.py` now upgrades a legacy
  database, keeps the existing structure row and asserts `license='unknown'`.
- Added `src/hcs_discovery/api/routes/targets.py` and `api/schemas.py` target
  models, wired into `create_app`.
- Added the `hcs-discovery target` CLI family (create/list/show/update/delete,
  import-structure, structures, structure, delete-structure) with `--json`,
  confirmation prompts and stable exit codes.
- Tests: 11 unit (`tests/unit/test_structure_inspection.py`) and 18 integration
  (`tests/integration/test_targets.py`) covering service, API and CLI parity,
  cross-project attachment refusal, duplicate names, deletion semantics and the
  "rejected import leaves no file and no row" rule. Fixture
  `tests/fixtures/structures/tiny_two_chain.pdb` is hand-written synthetic data
  (REMARK-marked), not a real structure.
- Gates on the branch: 418 passed / 2 skipped, 81% branch coverage, ruff, mypy,
  docs links.
- Not done: target UI page, binding-site/box definition, receptor preparation,
  UniProt/RCSB metadata connectors, E2E journey.

## 2026-11-02 — R0.1/R0.3/R0.5/R0.6: gate runner, generated numbers, preview smoke

- Branch/SHA: `feat/target-explorer-api` @ `1efca60` after merging `origin/main`
  (`4e5b625`, dependabot #12); worktree dirty with exactly the files below.
- Hypothese (falsifizierbar): Ein einziger lokaler Gate-Runner, der `ci.yml`
  spiegelt, und Zahlen, die aus dem Messbericht generiert werden, beenden die
  Dokumentationsdrift aus F5 — und ein absichtlich veralteter Wert wird rot.
- Geändert:
  - `scripts/gates.py` — Gate-Runner mit G0–G14, Leveln `fast|full|science|release`,
    `--only`, `--json`, `--keep-going`; schreibt `build/gate-report.json` mit SHA,
    Dirty-Flag, Level, je Gate Befehl/Exit/Dauer/Kurzfassung. Gates, die ein
    optionales Werkzeug brauchen (`gitleaks`), werden `skipped` mit Grund, nie
    `passed`. Jede App-Gate bekommt ein Wegwerf-`HCS_DATA_DIR` (F6).
  - `scripts/gates_wheel.py` — Wheel-Install/Smoke/Metadaten ohne Bash, damit G8
    auch auf Windows dasselbe prüft wie der Linux-CI-Job.
  - `scripts/ci/check_doc_claims.py` — generierte Blöcke
    `<!-- gen:tests -->…<!-- /gen:tests -->` und `gen:coverage` in README,
    `IMPLEMENTATION_STATUS.md`, `RELEASE_EVIDENCE.md`; `--write` rendert sie aus
    `build/junit.xml` + `build/coverage.json`, ohne `--write` wird nur geprüft.
  - `scripts/ci/smoke_preview.py` — liest Health/Ready/SPA, Projektliste,
    Demo-Projekt, einen beendeten Run und das Wort „synthetic"; schreibt nichts.
  - `docs/engineering/evidence.json` — die eine Quelle der Zahlen.
  - `.github/workflows/ci.yml` — der Docs-Job ruft zusätzlich
    `check_doc_claims.py` auf, damit die Drift auch in der Cloud auffällt.
  - Tests: `tests/unit/test_gates_runner.py` (6), `tests/unit/test_doc_claims.py`
    (5), `tests/unit/test_smoke_preview.py` (5).
- Befehle und Ergebnis:
  - `uv run python scripts/ci/check_doc_claims.py` → exit 1:
    „gen:tests says '426 passed, 2 skipped', measured is '432 passed, 2 skipped'"
    (der absichtlich stehen gelassene alte Wert), danach `--write` → exit 0. Das ist
    die Abnahme aus R0.5, rot vor grün beobachtet.
  - `uv run python scripts/gates.py --level fast` → exit 0 (G1–G4 grün).
  - `uv run python scripts/gates.py --level full --keep-going` → erster Lauf exit 1:
    G10 scheiterte, weil `pip-audit` lokal nicht installiert ist; Gate auf
    `uvx --from pip-audit==2.10.1 … --strict` umgestellt (genau der CI-Befehl),
    danach G10 grün. Zweiter Gesamtlauf: G0–G11 grün, G13 `skipped`
    (`gitleaks` fehlt lokal), Laufzeit ≈ 2 min ohne G12.
  - `uv run pytest -q tests/unit/test_gates_runner.py tests/unit/test_doc_claims.py
    tests/unit/test_smoke_preview.py` → 16 passed.
  - `uv run ruff format --check .` / `ruff check .` / `mypy` → grün über die
    getrackten Dateien; `PLAN.md` und `AGENTS.md` bleiben bewusst untracked und
    werden vom Runner ausgenommen, weil CI sie nie sieht.
- Evidenz: `build/gate-report.json` (Level `full`, SHA `1efca60`),
  `docs/engineering/evidence.json` (442 passed, 2 skipped, 81,4 % Branch-Coverage).
- Nicht getan / Restrisiko:
  - R0.2 (PR #10 schneiden) braucht Owner-Entscheidung D2.
  - R0.4 (Vina lokal) nicht ausgeführt: kein Binary auf diesem Host, das
    Wissenschafts-Gate bleibt `NOT RUN` und steht so in `RELEASE_EVIDENCE.md`.
  - R0.6 ist als Skript fertig und getestet, aber gegen keine echte Preview-URL
    gelaufen — die Verknüpfung des Vercel-Projekts ist D7.
  - R0.7 (RC-Commit, Tags) ist vorbereitet, aber Tag und Release sind D1 und
    werden nicht autonom ausgelöst.
  - PR #11 (dependabot, Python-Minor) bleibt offen: der Release-Kandidat wird nach
    Pfad A von `f023c70` geschnitten, das Lockfile dort ist stabil; die
    Entscheidung darüber gehört zum Release-Termin.

## 2026-11-03 — GPU similarity as a product path (local → browser → Vercel → exe)

- Branch/SHA: `feat/v2-stable-readiness`, Ausgangspunkt `2758178` (WGSL-Kernel,
  Vulkan-Engine, PyInstaller-Exe, statisches Vercel-SPA), Arbeitsbaum mit den
  unfertigen Browser-Dateien (`GpuBenchmark.tsx`, `gpuTanimoto.ts`, `gpu.spec.ts`).
- Recherche: `docs/research/SOTA_GAP_ANALYSIS.md`. Kurzfassung — SOTA bei
  Ähnlichkeitssuche heißt GPU-Kernel für Morgan/Tanimoto plus BitBound (nvMolKit:
  CUDA-only, H100-Zahlen; chemfp: ~130M 1024-bit-Tanimotos/s auf einem Kern,
  k=1000 über 1.8M ChEMBL in 27 ms). Unser Kernel war vorhanden, aber nur als
  Benchmark erreichbar. Genau diese Lücke wird geschlossen; ADMET (Chemprop/TDC),
  Strukturvorhersage und MD bleiben offen und dokumentiert.
- Geändert:
  - `src/hcs_discovery/similarity.py` — `TanimotoIndex` / `tanimoto_search` mit
    k-NN und Threshold, residenter Bibliothek, Chunking über der
    Storage-Buffer-Grenze, CPU-Referenz und `verify=True`: die GPU-Popcounts
    werden gegen `gpu.cpu.cpu_counts` geprüft, ein Unterschied wirft `ParityError`
    statt eine Zahl zu liefern. Ähnlichkeit ist `inter/union` in float64, also
    bit-identisch zu `DataStructs.TanimotoSimilarity`. `prefer="gpu"` ohne
    Hardware wirft `GpuUnavailableError` statt still auf CPU zu fallen.
  - `workflow/nodes.py` — `chem.similarity` bekommt `engine: auto|cpu|gpu`,
    loggt Engine/Adapter/Parity als Run-Event und nimmt die Engine in den
    Cache-Runtime-Fingerprint auf. Standard-Radius/-Bits nutzen den Kernel,
    andere Breiten bleiben beim CPU-Pfad (und sagen das im Engine-Detail).
  - `cli/main.py` — `hcs-discovery similarity search --query … --file … [-k]
    [--threshold] [--engine] [--output]`, Schema `hcs.similarity-search.v1`,
    Standardisierung wie `dataset import`.
  - `api/app.py` — CSP: `'wasm-unsafe-eval'` und `'unsafe-eval'`, kein Remote-
    Script-Source. Grund: RDKit MinimalLib ist mit Emscripten embind gebaut und
    generiert Bindings per `new Function`; ohne das lief das Browser-Panel nie.
  - Browser: `GpuBenchmark.tsx` / `gpuTanimoto.ts` melden Durchsatz (M/s),
    prüfen die Storage-Buffer-Grenze und fangen Kernel-Fehler als Fehlerzustand;
    `e2e/browser-compute.spec.ts` testet den RDKit-WASM-Selbsttest gegen den
    echten Server, `e2e/gpu.spec.ts` die WebGPU-Parität.
  - `scripts/science/benchmark_gpu_similarity.py` → erzeugt
    `docs/validation/gpu-tanimoto.md` und `build/gpu-similarity.json`.
- Messung (AMD Radeon 680M, Vulkan, 5 Wiederholungen, Median, veröffentlicht in
  `docs/validation/gpu-tanimoto.md`): 100k Fingerprints resident 1,6 ms
  (60,9 M/s, 12,3× RDKit), 500k resident 5,0 ms (99,2 M/s, 19,1× RDKit), Counts
  exakt, Top-10 identisch, max. Abweichung zu RDKit 0,0.
- Befehle und Ergebnis: `similarity search` über `examples/datasets/demo_library.csv`
  → 17 Strukturen, `engine gpu (Vulkan, AMD Radeon(TM) Graphics)`, Parity
  verifiziert; `HCS_E2E_WEBGPU=1 npx playwright test e2e/gpu.spec.ts` → 1 passed;
  volle E2E-Suite → 5 passed; ruff format/check und mypy grün.
- Nicht getan: BitBound-Prefilter, persistente gepackte Fingerprints pro Dataset,
  API-Route für die Suche, GPU-Fingerprint-Generierung, Vergleich mit nvMolKit
  (CUDA-only, andere Hardware).

## 2026-11-03 (Abend) — Zero-Backend-Lab, MCP, SAT, Hybrid, Container

- Branch `feat/zero-backend-workspace` (von `main` nach dem GPU-Merge).
- Recherche → `docs/engineering/PLAN_2026-11-03_ZERO_BACKEND.md` (Vercel-Limits,
  Container, OPFS/SQLite/IndexedDB, WebGPU-Präzision, SAT, Packaging).
- Gebaut und verifiziert:
  - **Offline-Lab** (`apps/web/src/pages/Lab.tsx`, `lib/offlineLab.ts`): Import
    CSV/SDF/SMI, RDKit-WASM-Deskriptoren, identische Triage/Composite-Ranking-
    Semantik, WebGPU/CPU-Similarität, IndexedDB-Persistenz, CSV-Export, 360-px-Layout.
    Drei Playwright-Tests gegen `vite preview` (kein API-Server), inkl. Reload und
    Löschen.
  - **API** `POST /api/v1/similarity/search` + `/engines` mit demselben Schema wie
    die CLI; Tests für 404, ungültiges SMILES, engine=gpu ohne Adapter.
  - **MCP** `mcp_server.py` (JSON-RPC 2.0, stdio, fünf Read-only-Tools), CLI
    `hcs-discovery mcp serve`; Subprozess-Test prüft, dass stdout nur Protokoll ist.
  - **Hybrid-Boost**: GPU+CPU-Split mit Kalibrierung; `auto` bleibt GPU-only, wenn
    die CPU nicht mithalten kann. Gemessen 1,03–1,09× gegenüber GPU-Upload.
  - **SAT**: DPLL mit Watched Literals, Pure-Literal-Elimination, deterministischer
    Branching; 40 Brute-Force-Differentialfälle, Pigeonhole-UNSAT, Sequenzzähler;
    CLI `sat solve` (Exit 5) und `sat select`.
  - **Docker**: Multi-Stage-Image (SPA im Node-Stage, schlanker Python-Runtime,
    non-root, Healthcheck); Container startet, liefert `/api/v1/health`, SPA 200,
    Similarity-Suche und `sat select` im Container. Stolpersteine: WGSL-Import
    außerhalb des Web-Kontexts (Kernel an denselben relativen Pfad kopiert) und
    RDKit-Draw-Abhängigkeiten (`libxrender1`, `libexpat1`, `libfontconfig1`,
    `libfreetype6`).
  - **SEO/Doku**: Meta/OG/Canonical/JSON-LD, `robots.txt`, `sitemap.xml`,
    Zero-to-Hero-Guides EN/DE/FR; Playwright prüft Metadaten und die echte 404-Seite.
  - **Stündlicher Weckruf**: `scripts/ops/hourly_wakeup.ps1` (Lock, Merge-Check, Log)
    plus `install_hourly_task.ps1`; Task `HCS-OpenCode-Hourly` ist installiert
    (`Status: Bereit`), Dry-Run protokolliert.
- Nicht getan / bewusst offen: Service-Worker-Offline-Cache, veröffentlichte
  npm-/PyPI-Pakete, UI-Übersetzung (nur Guides), BitBound-Prefilter.

## 2026-11-03 (04:00) — Offline nach dem ersten Besuch (Service Worker)

- Branch `main`, Ausgangspunkt `5577cb8`. Nächste offene Phase aus dem Plan: P1.7
  (Offline-Cache). npm-/PyPI-Veröffentlichung bleibt offen (Credentials/Freigabe).
- Gebaut: `apps/web/public/sw.js` — Navigationen network-first (Deploy sofort
  sichtbar, Offline-Reload fällt auf die gecachte Shell zurück), gehashte Assets
  cache-first, `/api/` wird nie gecacht; Cache-Version im Namen, `activate` löscht
  fremde Caches; `skipWaiting` + `clients.claim`.
- Erstbesuch-Problem gelöst: Ein Worker kontrolliert die Seite erst nach der
  Aktivierung, also wurden JS/CSS des ersten Ladevorgangs nie gecacht. `main.tsx`
  schickt dem Worker nach `ready` die eigenen Boot-URLs (`CACHE_URLS`), der Worker
  legt sie ab (Fehler pro URL werden ignoriert).
- `manifest.webmanifest` + Link in `index.html` (installierbar, wo der Browser es
  unterstützt).
- Test: `e2e/offline-cache.spec.ts` startet einen statischen Preview-Server auf
  8793, benutzt das Labor, **killt den Server** (echtes Verbindungs-aus, nicht
  Playwright-Offline-Emulation), lädt neu und prüft Shell, IndexedDB-Kopie und
  Similarity. Erster Lauf rot, Ursache per Diagnose im Worker gefunden:
  `cache.match(request)` verfehlte die Einträge wegen `Vary`-Headern
  (`TypeError: Failed to fetch`). Fix: `{ ignoreVary: true }` für unveränderliche
  Shell-/Asset-Einträge. Danach 1 passed, ganze Suite 12 passed.
- Gates: ruff/mypy/tests wie zuvor; volle Suite unten erneut.
- Nicht getan: UI-Übersetzung, veröffentlichte Pakete, BitBound-Prefilter.

## 2026-11-03 (05:00) — BitBound-Prefilter + langfristiger Plan

- Branch `main` @ `064a7f4`. Recherche (chemfp/BitBound, US-RSE/OSS-Nachhaltigkeit)
  → neuer Plan `docs/engineering/ROADMAP_LONG_TERM.md` (Horizonte, Gates, Nicht-Ziele).
- Umgesetzt (erste Zeile aus „Now"):
  - `gpu/cpu.py`: öffentliche `popcount_rows`.
  - `TanimotoIndex` berechnet die Popcounts der Bibliothek einmal bei `install`
    und bietet `threshold_hits` / `threshold_hits_for` mit der BitBound
    `T ≤ min(a,b)/max(a,b)`. Nur Kandidaten werden bewertet; `counts_for(indices)`
    prüft die Parity weiterhin auf genau dieser Teilmenge. Kein Hybrid-Pfad für
    Teilmengen (CPU-Anteil wäre bedeutungslos).
  - `ThresholdResult` (hits, candidates, timings, `prefiltered`), `SearchResult`
    trägt zusätzlich `prefiltered`/`candidates`.
  - CLI/API/MCP nutzen den Prefilter nur, wenn keine vollständige Score-Liste
    gebraucht wird (`--output` deaktiviert ihn); JSON `prefilter.{enabled,candidates,library}`.
- Tests: Differential (7 Schwellen), Kanten (nichts prunebar, alles gepruned,
  threshold=0), Property „Bound ist obere Schranke" über 15 Zufallsbibliotheken,
  GPU-Differential. 26 Tests in `test_similarity_search.py`, 68 in CLI/API/MCP.
- Messung (`docs/validation/gpu-tanimoto.md`): uniforme Dichte 98–100 % Kandidaten
  (kein Gewinn), dichte-variierte Bibliothek 68 %/35 %/12 % Kandidaten bei 0.4/0.7/0.9
  → 1,5–8× schneller; beide synthetisch, im Report benannt.
- Gates: ruff/mypy grün, volle Suite + Gate-Runner folgen im selben Lauf.
- Offen: Dataset-Fingerprint-Cache (nächste Zeile), Metriken, Lighthouse/axe.

## 2026-11-03 (08:00) — Release-Runde v2.1.0 (R1–R4)

- Branch `main` @ `e096f81`; Plan `docs/engineering/RELEASE_PLAN_v2.1.md`.
- R1: Version 2.1.0 in `pyproject.toml`, `src/hcs_discovery/__init__.py`,
  `apps/web/package.json` (+ Lockfile) und `CITATION.cff`; CHANGELOG-Abschnitt
  `## [2.1.0] - 2026-11-03` (mit dem Hinweis, dass 2.0.0 nie veröffentlicht wurde);
  Release Notes `docs/releases/v2.1.0.md`; README-Badge/Quickstart/Citation/Status
  darauf umgestellt.
- R2: `release.yml` bekommt einen **gated** PyPI-Job (Trusted Publishing, OIDC,
  Environment `pypi`, `PYPI_PUBLISH=true` nötig); Runbook
  `docs/engineering/RELEASING.md` mit Tag/PyPI/DOI-Schritten, Rollback und
  Post-Release-Checks. Der Job läuft ohne Variable nicht und bricht keine Releases.
- R3: WCAG-2.2-Verbesserungen im Offline-Lab: `aria-live="polite"` + programmatischer
  Fokus auf Import- und Similarity-Ergebnis, `scroll-padding-top` gegen den
  Sticky-Header (2.4.11), Touch-Ziele ≥44 px unter 640 px (2.5.8). Playwright prüft
  Announcement, Fokus, Scroll-Padding und Buttonhöhe.
- R4: README/Status/Docs-Links aktualisiert (Long-term-Roadmap, Release-Plan,
  Runbook, Release Notes).
- Zwei echte Fehler dabei gefunden und behoben:
  - Der EXE-Smoke-Test prüfte hart auf `2.0.0` und ließ G15 nach dem Versionsbump
    scheitern; er liest die erwartete Version jetzt aus `pyproject.toml`.
  - Mehrere Dateien waren durch PowerShell-Encoding doppelt kodiert (Mojibake:
    „â€—", „Ã×", „FranÃ§ais"); per UTF-8-Reparatur bereinigt, danach repo-weit 0
    Treffer. Lehre: Dateien nur mit dem Edit-Tool oder explizitem
    `UTF8Encoding($false)` schreiben.
- Verifikation: 567 Tests, 83 % Branch-Coverage, ruff/mypy grün, Gate-Runner
  `--level full` grün, G15 grün, Wheel-Smoke (G8) grün, `verify_version.py v2.1.0`
  grün.
- Offen (owner-gated): Tag, GitHub Release, PyPI-Upload, DOI.
- **Blockiert, nicht erledigt:** Der Produktions-Deploy des neuen Builds scheitert am
  Tageslimit des Vercel-Free-Plans (`api-deployments-free-per-day`, 100/Tag). Die
  Produktion läuft weiter auf dem Stand von `064a7f4`: im ausgelieferten `/lab`
  fehlen `data-testid="lab-import-result"` und `scroll-padding-top`. Nächster
  Versuch nach dem Reset des Limits oder mit einem bezahlten Plan.

## 2026-11-03 (08:40) — Metriken-Endpoint (erste Zeile der „Now"-Liste nach BitBound)

- Branch `main` @ `4bbfe90`.
- `GET /api/v1/metrics` (Prometheus text 0.0.4, `include_in_schema=False`):
  `hcs_build_info`, `hcs_uptime_seconds`, `hcs_projects`, `hcs_datasets`,
  `hcs_compounds`, `hcs_runs{status=…}`, `hcs_queue_depth{status=…}`,
  `hcs_node_cache_entries`, `hcs_node_cache_bytes`, `hcs_gpu_available`.
  Bewusst klein: keine Per-Request-Labels (Kardinalität), keine Pfade, keine Tokens,
  keine Nutzerdaten; gleiche Bearer-Token-Regel wie der Rest von `/api/v1`.
  Der GPU-Probe-Fehler kann einen Scrape nicht brechen (`except` → 0).
- Tests: Format/Serien, Zähler wachsen nach Projekt+Import (16 Compounds),
  keine Pfade/Secrets, jede Zeile ist eine gültige Prometheus-Zeile.
- Grenze bleibt ehrlich: keine Traces, keine Dashboards, kein Alerting — so im
  Ledger vermerkt.
- Gates: ruff/mypy grün, API-Suite 20 passed, voller Lauf unten.

## 2026-11-03 (11:00) — Dataset-Fingerprint-Cache (Migration b7d21c4f9a03)

- Branch `main` @ `8da569d`. Nächste „Now"-Zeile: Fingerprints nicht bei jeder Suche
  neu berechnen.
- Neu: Modell `DatasetFingerprints` + Migration `b7d21c4f9a03` (Tabelle
  `dataset_fingerprints`, unique Index auf `dataset_id`, FK CASCADE) und Service
  `services/fingerprints_cache.py`:
  - Compounds werden in stabiler Reihenfolge (`ORDER BY id`) gelesen; die IDs kommen
    mit der Matrix zurück, damit Treffer-Indizes sicher auf Zeilen zeigen.
  - `compounds_checksum` (id + SMILES) erkennt geänderte Daten, `checksum` über die
    gepackten Bytes erkennt abgeschnittene/manipulierte Blobs → Neuaufbau statt
    falscher Scores.
  - Nur radius 2/2048 Bit (Kernel); andere Formen sind ein Validierungsfehler.
- API `POST /api/v1/similarity/search` nutzt den Cache über
  `TanimotoIndex.from_packed`; Payload meldet `fingerprints.{cached,checksum,count,
  radius,bits}`. Der Index wird pro Request neu gebaut (kein globaler Zustand).
- Metriken: `hcs_fingerprint_cache_entries`, `hcs_fingerprint_cache_compounds`.
- Tests: `tests/integration/test_fingerprint_cache.py` (Reuse → cached=true,
  Compounds ändern → cached=false, Blob korrupt → Neuaufbau, unbekanntes Dataset →
  NotFound), API-Test (zweiter Aufruf cached=true, identische Hits), Alembic
  `check` (Modelle == Migrationen) und Migrations-Smoke grün.
- Gates: ruff/mypy grün, volle Suite im selben Lauf.
- Offen: Messung „Zeit pro Suche mit/ohne Cache" auf einer großen Bibliothek steht
  noch aus; der Cache-Effekt ist derzeit funktional, nicht in ms belegt.

## 2026-11-03 (12:40) — Cache gemessen + selbstheilende Stundenschleife

- **Cache-Messung nachgeholt** (`scripts/science/benchmark_fingerprint_cache.py`,
  synthetische 5.000-Zeilen-Bibliothek, Median aus 3 Läufen): `pack_smiles` 656,9 ms,
  erster Cache-Aufbau 724,1 ms, Cache-Treffer 15,3 ms → **43×**; Checksummen stabil.
  Report: `docs/validation/fingerprint-cache.md` (inkl. Grenzen: synthetisch, ein
  Host, Verhältnis „Neu-Fingerprint vs. Cache-Lesen", keine Ende-zu-Ende-Latenz).
- **Stundenschleife selbstheilend gemacht** (`scripts/ops/`):
  - `hourly_wakeup.ps1`: JSON-Lock mit PID, **OS-Prüfung auf einen laufenden
    opencode-Prozess derselben Session** (überlebt einen getöteten Wrapper), ein
    Retry, Heartbeat `logs/heartbeat.json`, `opencode`-Pfadauflösung.
  - `watchdog.ps1`: läuft alle 15 min, startet nur bei fehlendem/veraltetem
    Heartbeat (>75 min) oder `failed`; Dry-Run getestet, erkennt einen 120-min-alten
    Heartbeat korrekt.
  - `install_hourly_task.ps1`: registriert beide Tasks per `schtasks` (ohne Admin);
    `Register-ScheduledTask` scheiterte hier an fehlenden Rechten.
  - Doku: `docs/ops/HOURLY_LOOP.md` (Ablauf, Prüf- und Reparaturbefehle).
- Verifikation: Dry-Runs beider Skripte, laufender Turn wird als „already running
  (pid …)" erkannt; Tasks `HCS-OpenCode-Hourly` und `HCS-OpenCode-Watchdog` sichtbar.

## 2026-11-03 (19:00) — axe-Gate + Bundle-Budget (WCAG 2.2)

- Branch `main` @ `a3d7be9`. Nächste „Now"-Zeile: Accessibility-Audit und Budgets.
- Neu: Dev-Dependency `@axe-core/playwright@4.11.0` (MPL-2.0, dev-only; der npm-
  Lizenzcheck prüft nur Produktionspakete) und `apps/web/e2e/a11y.spec.ts`: axe-core
  mit `wcag2a/2aa/21a/21aa/22aa` über 7 Routen gegen den echten Server; `serious`
  und `critical` schlagen fehl, `moderate/minor` werden geloggt.
- Dabei drei echte Defekte gefunden und behoben:
  1. `link-in-text-block` (About): Inline-Links nur per Farbe unterscheidbar →
     `.text-link` und Links in Prosa sind jetzt dauerhaft unterstrichen (WCAG 1.4.1).
  2. `scrollable-region-focusable` (Settings, Umgebungstabelle): `tabIndex=0`,
     `role="region"`, `aria-label`.
  3. dito (About, Zitatblock `<pre>`): gleiche Behandlung mit `aria-label`
     „Citation in BibTeX format".
- `scripts/ci/check_bundle_budget.mjs`: gzip-Budget JS 210 kB / CSS 16 kB / total
  235 kB; aktuell 167/10/177 kB. Läuft im Gate-Runner (G5) und im CI-Frontend-Job.
  Bewusst ohne Lighthouse: LCP/CLS auf einem statischen Host ohne Backend wären
  nicht vergleichbar; die Zahlen sind als offen markiert.
- Verifikation: 19 E2E-Tests grün (7 davon axe), `npm run build` grün,
  Bundle-Budget grün. Zwischenfälle: `npm ci` scheiterte an einem gesperrten
  `node_modules` (laufende Vite/Playwright-Prozesse beendet), und ein CSS-Edit hatte
  verwaiste Deklarationen hinterlassen (lightningcss-Fehler) — beides behoben.
- Offen: Lighthouse-LCP/CLS-Budget; Tag/PyPI/DOI (owner-gated).

## 2026-11-03 (22:45) — `select.sat` als Workflow-Node

- Ausgangslage: `main` @ `3377c8e` (2.2.1); die parallele Hosted-Parity-Arbeit ist
  gemerged, mein Review ist beantwortet (Treiber ist `pg8000`, nicht `psycopg`), der
  Baum ist clean.
- Neu: `select.sat` in `workflow/nodes.py` — wählt höchstens `k_max` Zeilen, sodass
  jede Gruppe ≥ `min_per_group` vertreten ist, über den vorhandenen DPLL-Solver
  (`select_subset`, Sinz-Zähler).
  - `on_infeasible: fail` (Default) bricht mit dem Solver-Grund ab, statt eine
    plausible Teilmenge zu schreiben; `mark` schreibt alle Zeilen als nicht gewählt
    mit Grund und lässt den Lauf weiterlaufen.
  - Ausgabe `sat_selected` (boolean) + `sat_reason`; Zeilen werden nie entfernt.
  - Zeilen ohne Gruppenzwang (`NULL`/leer) werden nie gewählt, Grund „no group value".
  - Deterministisch (Solver sortiert IDs), Gruppen- und ID-Spalte sind Pflicht.
- Tests: `tests/unit/test_sat_node.py` (8) — Abdeckung, Budgetkonflikt (fail/mark),
  Zeilen ohne Gruppe, leere Gruppenspalte, `min_per_group`, fehlende Spalten,
  Determinismus.
- Doku: `docs/user-guide/WORKFLOWS.md` (Feldtabelle + YAML), README-Zeile,
  CHANGELOG, Roadmap (Next-Zeile erledigt).
- Verifikation: ruff/format auf den geänderten Dateien, Node-Tests grün, Node im
  Registry-Katalog sichtbar (`select.sat`), Workflow-Validator akzeptiert ihn
  (Gruppenspalte muss von einer Vorgänger-Node stammen). Voller Lauf unten.

## 2026-11-04 (08:40) — Run-Timeline (Observability in der UI)

- Branch `main` @ `6bf9ffb`, Baum clean, kein paralleler Agent aktiv.
- Neu: `apps/web/src/components/RunTimeline.tsx`, eingebunden im Run-Monitor unter dem
  Ausführungsgraphen. Ausschließlich aus persistierten Zeitstempeln:
  - Queue-Segment (`created_at` → `started_at`), nur wenn es eine Wartezeit gab;
  - je Knoten ein Balken (`started_at` → `finished_at`, laufende Knoten bis jetzt);
  - Cache-Markierung aus `node.cached`, Statusfarbe aus `node.status`;
  - Kopfzeile mit „X queued · Y in nodes · Z total".
  Knoten ohne aufgezeichneten Start werden **ausgelassen**, nicht geschätzt.
- Barrierefreiheit: `<section aria-label>`, `<ol>` als Zeilenliste, die Grafik ist
  `aria-hidden`, die Information steht als Text (Label + Dauer) daneben; axe-Gate
  deckt die Seite ab.
- Test: `e2e/studio.spec.ts` prüft nach dem Run mindestens 4 Timeline-Segmente und
  die Kopfzeile. Lokal: `studio.spec.ts` 3 passed (inkl. Timeline), Build grün.
- Gates/Doku: CHANGELOG, Roadmap (Next-Zeile erledigt), voller Gate-Lauf unten.

## 2026-11-04 (08:50) — v3-Plan gegengeprüft: zwei behauptete Defekte existieren nicht

- `main` @ `85b3d10` (Run-Timeline committet); im Baum arbeitet ein zweiter Agent an
  `similarity.py` (bound-pruned k-NN) — nicht angefasst.
- `docs/engineering/PLAN_2026-11-04_SOTA_V3.md` behauptete in §0.1/§0.2 zwei Defekte.
  Beide geprüft, beide **nicht reproduzierbar**:
  1. „kaputter CSS-Einzeiler" in `global.css`: `.node-progress` ist ein normaler
     Block (`padding`, `border`, `border-left`, `border-radius` je eigene Zeile),
     `npm run build` und lightningcss laufen grün.
  2. Mojibake in `plugins/science/adapter.py`: die Datei heißt
     `plugins/science/properties/adapter.py`; ein Scan über alle `src/**/*.py` nach
     U+FFFD/„â€"/„Ã" liefert 0 Treffer.
  Der Plan ist an beiden Stellen korrigiert (durchgestrichen + Prüfdatum), nicht
  stillschweigend gelöscht.
- Lehre für den Plan: Behauptungen über einen Arbeitsbaum veralten, sobald ein
  zweiter Agent committet; jeder „Defekt" braucht den Befehl, der ihn zeigt.
- Zusätzlich die im v3-Plan (§0.2, Punkt 13) benannte **Versionsdrift** behoben:
  `apps/web/package.json`/Lockfile, `CITATION.cff` (beide Blöcke) und README
  (Badge, Citation-Block) standen auf `2.1.0`; `IMPLEMENTATION_STATUS.md` nannte
  `2.2.0` als aktuell. Jetzt überall `2.2.1`, passend zu Tag, GitHub-Release
  (published 2026-11-03) und `pyproject.toml`. `verify_version.py v2.2.1` grün,
  `test_release_version.py` 12 passed.

## 2026-11-04 (09:00–…) — v3.0.0: SOTA-Lücken schließen, Major Release

- Ausgangslage: `main` @ `6bf9ffb` + uncommitted Run-Timeline; Branch
  `release/v3.0.0`. Plan: `docs/engineering/PLAN_2026-11-04_SOTA_V3.md`
  (Recherche zu Similarity-SOTA, ADMET, Docking, RO-Crate, MCP `2026-07-28`,
  Packaging und UI/UX mit Quellen).
- **W0:** CSS-Defekt (inline `border` im Timeline-Block) behoben; Timeline-Werk
  committet; Baseline `uv run pytest` → 591 passed, 1 deselected, 110 s.
- **W1 — Bound-pruned k-NN:** `TanimotoIndex.knn_hits(_for)`; exakt (Differential-
  und Property-Tests inkl. Ties). Die erste Ring-pro-Dispatch-Variante war
  **14× langsamer** als ein Full Scan und wurde verworfen; die gestagte Variante
  (Popcount-Ring als Seed, dann Bound-Filter in einem Dispatch) ist 6,0× (100k)
  bzw. 3,9× (500k) auf einer geclusterten synthetischen Bibliothek, 0,85× auf
  einer ungeclusterten — beides im generierten Report.
- **W2 — Batch-Kernel:** `gpu/kernels/tanimoto_batch.wgsl`, `GpuEngine.counts_many`,
  `TanimotoIndex.search_many`, CLI `similarity screen`; 10,9× (100k) / 9,7× (500k)
  gegenüber Einzelabfragen, Parität pro Query. Erster Kernel-Versuch scheiterte an
  `target` als WGSL-Schlüsselwort; das warf den gesamten GPU-Pfad still auf CPU
  zurück, bis der Name geändert war.
- **W3 — ESOL:** vollständige Delaney-Gleichung auf dem 1.128-Molekül-Set
  gemessen: RMSE 1,099 [1,047; 1,154], MAE 0,844, R² 0,725; Held-out-Scaffold-Split
  RMSE 1,201 / R² 0,640. Der 45-Molekül-Stresstest (R² 0,07) bleibt publiziert.
  `validate_esol_delaney.py --check` ist das Gate.
- **W4 — RO-Crate:** `reports/rocrate.py`, CLI/API/UI; RO-Crate-1.1-Kontext,
  `CreateAction`/`prov:Activity`, `prov:Plan`, Umgebung, Artefakt-Hashes,
  deterministisches ZIP; fehlende Artefakte brechen ab. Drei Integrationstests.
- **W5 — MCP:** dual-era `2026-07-28` (`server/discover`, `-32022`,
  `resultType`, `ttlMs`/`cacheScope`, `structuredContent`) plus Legacy-
  `initialize`; 16 Tests.
- **W6 — Metriken:** `hcs_run_duration_seconds`, `hcs_node_duration_seconds`,
  `hcs_node_cache_hits_total` aus persistierten Zeitstempeln; API-Tests.
  Lighthouse bleibt offen (nicht installiert; kein erfundenes Budget).
- **W7 — Docking:** Multi-Target bewusst **nicht** gebaut (keine
  Rezeptorvorbereitung/keine Meeko-Abhängigkeit); 1IEP-Gate bleibt
  Regressionscheck, die Lücke steht in README/Status.
- **W8 — Release:** `3.0.0` in pyproject/`__init__`/package.json/Lock/constants/
  CITATION; Release-Matrix Windows x64, Linux x64, macOS arm64/x64 plus
  GHCR-Container mit Smoke-Test; Release Notes `docs/releases/v3.0.0.md`.
  PowerShell-`Set-Content -Encoding utf8` schrieb BOMs in sechs Dateien
  (TOMLDecodeError); mit Python-Byteschnitt entfernt. Lehre: Dateien nur mit
  Edit-Tool oder Python schreiben.
- **W9 — UI/UX:** Zwei echte Defekte gefunden:
  1. `formatDuration` erwartet Sekunden, die Timeline übergab Millisekunden →
     ein 0,25-s-Lauf zeigte „1m 40s in nodes“/„4m 23s total“. Behoben, E2E prüft
     jetzt `< 60 000 ms` und dass die Summe keine Minuten enthält.
  2. Der Footer-Credit war doppelt kodiert (`â¤ï¸`), weil `constants.ts` als
     Latin-1-Mojibake gespeichert war. Behoben; neues Gate
     `scripts/ci/check_text_encoding.py` (UTF-8 strikt, U+FFFD, Mojibake-Muster)
     plus vier Tests und CI-/Gate-Runner-Einbindung.
  Timeline-Hinweis (Queue/Idle/Cache) ergänzt; RO-Crate-Button mit Tooltip;
  Screenshots neu erzeugt. Visueller QA-Lauf: **180 Captures, 0 automatische
  Findings**; E2E 19 passed; Bundle-Budget grün.
- **Doku:** README (3.0.0, neue Fähigkeiten, ehrliche Grenzen, korrigierte
  DAG-Beschreibung), IMPLEMENTATION_STATUS neu geschrieben, Roadmap/Release-
  Notes/CLI-Guide aktualisiert.
- **Parallelarbeit:** Die stündliche Schleife hat während dieses Turns zwei reine
  Doku-Commits erzeugt (`c4612a5`, `c8909e2`) und dabei zwei Punkte des Plans
  gegengeprüft, die zum Prüfzeitpunkt schon repariert waren. Beide Tasks
  (`HCS-OpenCode-Hourly`, `HCS-OpenCode-Watchdog`) wurden für den Rest des Turns
  deaktiviert, damit kein zweiter Agent in denselben Arbeitsbaum schreibt; nach dem
  Merge wieder aktivieren.
- **Offen:** Lighthouse-LCP/CLS, Tag/PyPI/DOI (owner-gated), Multi-Target-Docking,
  PostgreSQL gegen echten Server, Objekt-Storage.

## 2026-11-04 (10:30) — PostgreSQL gegen echten Server + Lighthouse-Budgets

- Ausgangspunkt `main` @ `da8e079` (CI und CodeQL grün). Zwei der im Ledger offenen
  Punkte waren auf dieser Maschine doch prüfbar: Docker 29.6.1 und Lighthouse 13.6.0.
- **PostgreSQL:** `scripts/ci/run_postgres_tests.py` startet
  `postgres:16-alpine` (Digest gepinnt) auf einem freien Loopback-Port und führt
  `tests/integration/test_postgres.py` aus:
  - Migrationen auf leerer DB, voller Triage-Lauf (16 Ergebnisse, ≥ 4 Artefakte),
  - vier Threads racen einen Claim → genau einer gewinnt,
  - `/api/v1/ready` und `/health` über den echten Server,
  - Stale-Lease-Recovery (requeue).
  4 passed lokal; Gate `G16`, CI-Job `postgres`, im Summary als Pflichtjob.
- **Dabei ein echter Bug:** `HCS_DATABASE_URL` wurde ignoriert. Das Feld hieß
  `database_url_override`, also las pydantic-settings nur
  `HCS_DATABASE_URL_OVERRIDE`; jedes Dokument nannte die kurze Variable. Die
  Vercel-Anleitung hätte also weiter SQLite benutzt. Fix: `validation_alias` mit
  beiden Schreibweisen + `populate_by_name`, zwei Regressionstests. `db current`
  zeigt jetzt „PostgreSQL database (configured by HCS_DATABASE_URL)“ statt eines
  SQLite-Pfads.
- **Lighthouse:** `apps/web/scripts/check_lighthouse.mjs` (programmatische API,
  `lighthouse` 13.6.0 als Dev-Dependency) misst Workspace und Offline-Lab gegen den
  statischen Build; `scripts/ci/run_lighthouse.py` baut/serviert und räumt auf.
  Messung: **Workspace 96 Performance, 100 Accessibility, FCP 1,8 s, LCP 2,4 s,
  CLS 0,007, TBT 104 ms; Lab 98 / 100, LCP 1,8 s, TBT 36 ms.** Budgets (0,85 /
  LCP 3000 ms / CLS 0,1 / TBT 600 ms) sind Regressionsbänder, dokumentiert in
  `docs/validation/lighthouse.md`. Gate `G17`, CI-Job `lighthouse`.
- **Gates:** voller Lauf lokal `635 passed, 4 skipped` (die 4 PostgreSQL-Tests
  skippen ohne `HCS_TEST_POSTGRES_URL`), ruff/mypy folgen; der neue CI-Lauf muss
  beide Jobs grün zeigen.
- **Weiter offen:** Multi-Target-Docking (Rezeptorvorbereitung), Managed-PostgreSQL-
  Deployment, Objekt-Storage/Worker auf Vercel, UI-i18n, Tag/PyPI/DOI (owner-gated).

## Blockers

- None technical at the time of writing. The `v0.1.0` preview is published and
  its assets are verified.

## Open follow-ups

- Add a generated `THIRD_PARTY_LICENSES` file to the wheel.
- Add PostgreSQL and distributed-worker support only if the product needs it.
- Implement a real docking or property adapter with a validation report before
  claiming scientific breadth.
- Consider replacing RDKit's bundled stubs with a maintained stub package, or
  pin a release whose stubs mypy can parse.

## 2026-11-03 - Hosted parity and release 2.2.0

Plan: `docs/engineering/PLAN_2026-11-03_HOSTED_PARITY.md`.

**Branch hygiene.** `release/v2.0.0` (`9434518`), `fix/v2-stable-gates`
(`55874cf`) and `fix/v2-gemini-mandate` (`e8071d1`) were each ahead of `main`, but
every divergent commit subject is present in `main` through the squashed merges
`556c76d` (PR #6) and `12febcf` (PR #7). They are superseded, not unmerged work.

**Baseline gate run.** `scripts/gates.py --level full` failed at `G5` with
`npm ci ... EPERM: unlink apps/web/node_modules/@rolldown/binding-win32-x64-msvc`.
Two orphaned processes from an interrupted earlier run (a `vite preview` on 8792
and a hung `playwright test e2e/a11y.spec.ts`) held the file. Killing them fixed
`npm ci`; this is a host-state failure, not a repository defect.

**Hosted parity.** One Vercel project now serves the SPA and `/api/v1`.
Verified on the deployment: `/api/v1/health` ok, `/api/v1/ready`
`database: ok`, `/api/v1/projects` with a demo project of 16 compounds and one
computed triage run, `/` and `/lab` returning the SPA shell, and
`POST /api/v1/runs` finishing `succeeded` in 2.1 s with `HCS_RUN_MODE=inline`.
Three defects surfaced and were fixed on the way:

1. `ModuleNotFoundError: No module named 'hcs_discovery'` - Vercel installs the
   declared dependencies but not the project in a `src/` layout. The entrypoint
   now puts `src/` on `sys.path`.
2. `ImportError: libXrender.so.1` from `rdkit.Chem.Draw` - the eager import in
   `chemistry/depiction.py` broke **every** route. The import is lazy and the
   depiction endpoint answers `424 missing_dependency`.
3. The CLI uploaded local runtime data and a deploy died on
   `.e2e-data/run-*/hcs.sqlite3`. Added `.vercelignore`.

**Postgres driver choice.** `psycopg` is LGPL and `scripts/ci/check_licenses.py`
rejects it; `pg8000` (BSD-3-Clause, pure Python) is used instead.

**Not durable on the host.** The SQLite file and run artifacts live on `/tmp`.
`HCS_DATABASE_URL` makes rows durable when pointed at PostgreSQL; artifacts are
still regenerable files and object storage remains a follow-up.

**Open follow-ups**

- Object storage for uploads and run artifacts; a Vercel Queues/Daemons worker to
  replace inline execution for long runs.
- `vercel promote` rebuilt from the git HEAD instead of moving the alias, so the
  production alias pointed at the pre-change commit until a CLI production deploy
  of the verified tree replaced it.

## 2026-11-03 - Release outcome (2.2.0 -> 2.2.1)

- PR #14 (20 checks green) squash-merged as `d9bad1a`; review response as
  `56fda4f`; the release pipeline fix as `b44c3d8`.
- `v2.2.0` was tagged on `56fda4f` with CI and CodeQL green. Verify, wheel and
  the one-file executable all passed; the publish job failed before creating
  anything with `Unable to resolve action actions/download-artifact@3d3c42e5`.
  That commit does not exist in the action repository - the v7 line only has
  `v7.0.0`. Nothing was published for 2.2.0 and the tag was **not** moved.
- `release.yml` now pins `actions/download-artifact` to
  `37930b1c` (v7.0.0), matching the `upload-artifact` v7 line already in use.
  Version bumped to 2.2.1, tagged as `v2.2.1` on `b44c3d8` (CI + CodeQL green)
  and the release published: `hcs_discovery_studio-2.2.1-py3-none-any.whl`
  (2.7 MB), `hcs-discovery.exe` (75.4 MB), `sbom.cdx.json`,
  `SHA256SUMS.txt`, with the SLSA build-provenance attestation.
- Production `https://hcs-discovery-studio.vercel.app` reports version 2.2.1,
  `/api/v1/ready` is ready with `database: ok`, one demo project is present
  and `/` serves the SPA shell. The deployment stayed behind Vercel
  Authentication throughout.
- Open follow-ups: object storage for uploads/artifacts, a real worker
  (Vercel Queues/Daemons) instead of inline execution for long runs, a PostgreSQL
  deployment exercised against a real server, and the stale-tag note for 2.2.0.
