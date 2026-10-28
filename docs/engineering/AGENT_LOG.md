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

## Security notes

- A GitHub token was supplied in chat earlier in the project. It was never
  written to a file, committed, printed in a report or included in a screenshot.
  Authentication used the `GH_TOKEN` environment variable as `timfromhcs`.
  Rotation is recommended regardless, because the token appeared in chat.
- No provider API key is configured or required for the demo.
- Local data lives under `data/` and is ignored by Git.

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
