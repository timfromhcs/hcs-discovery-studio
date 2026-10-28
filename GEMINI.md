# GEMINI.md — Autonomous Stable v1.0.0 Engineering Mandate

**Project:** HCS Discovery Studio  
**Repository:** https://github.com/timfromhcs/hcs-discovery-studio  
**Owner/brand:** hcsmedia  
**Brand line:** `Open science. Reproducible discovery. Made with ❤️ by hcsmedia.`  
**Target:** a genuinely stable, scientifically honest, tested, packaged, user-friendly `v1.0.0` release for Windows and Linux, with a dependable CPU-only distribution and a separate optional Vulkan-capable distribution.  
**Operating mode:** autonomous execution; do not ask the user routine questions. Inspect, decide from evidence, implement, test, repair, document, package, publish, and only then report completion.  
**Critical principle:** release quality is demonstrated by reproducible evidence, not by optimistic documentation or a green badge alone.

---

## 0. Mission and non-negotiable rules

Take the repository from its current `0.1.0` preview to `v1.0.0 Stable`. Deliver working code, working user journeys, credible scientific validation, robust local operation, accessible and polished UI/UX, secure local-agent workflows, a tested CPU-only path, a separately tested optional Vulkan-enabled path, ready-to-install releases for Windows and Linux, accurate documentation, GitHub branding, and a release with checksums/SBOM/build provenance.

Treat this file as the engineering contract. Complete the work in order: **local audit and implementation → local full test gates → local visual QA → local packaged-artifact tests → cloud CI/release-candidate verification → README/SEO/branding final pass → final cloud verification → stable release → verify the published assets**. Do not move to the cloud-validation phase while local checks for the same code revision are failing. If a cloud-only defect is found, reproduce or isolate it, fix it locally, rerun the relevant local gates, push the fix, and repeat the cloud gates.

### 0.1 Non-negotiable truthfulness

1. Never claim an engine is implemented because a registry card, configuration field, mock, or documentation paragraph exists. A feature is implemented only when a real supported path executes successfully and has tests.
2. Never label the project, a model, an adapter, a result, or a benchmark “SOTA” without a named task, named dataset/version, official or justified split, baseline, metrics, uncertainty, and reproducible evidence. Prefer “supports” or “benchmarked on X” over broad claims.
3. Never claim a result proves biological binding, safety, efficacy, clinical suitability, or that a compound is a drug. Docking scores, descriptors, predicted properties and model scores are prioritisation signals, not experimental proof.
4. Never claim Vulkan acceleration just because `vulkaninfo` finds a Vulkan device. Report the backend each specific engine actually used. CPU is always a valid supported baseline.
5. Never make a failed, cancelled, partial or incomplete run look successful. Missing values and engine errors must be explicit, not silently converted to plausible numbers.
6. Never remove, skip, weaken, xfail, or rewrite a legitimate test only to get a green build. A flaky test is a defect to investigate.
7. Never create fake data or success screenshots for features that do not work. Fixtures are labelled fixtures, not presented as real external or experimental data.
8. Never make README badges, release notes, model cards, SEO metadata, benchmark charts or marketing claims exceed the state of the implementation.
9. Never commit credentials, access tokens, private data, proprietary datasets, non-redistributable weights, or generated secrets. Keep secrets in environment variables or GitHub Actions secrets; redact them from logs/reports.
10. Never force-push, bypass branch protection, disable security controls, delete user data, or publish a release that failed a release gate. If credentials or permissions are missing, perform all remaining work that can be done safely and write a precise blocker report without pretending it succeeded.

### 0.2 Autonomous-work rules

- Do not ask the user for choices that can be made from the repository, available documentation, compatibility data or a reversible engineering decision. Choose the smallest dependable implementation that meets the acceptance criteria.
- Do not stop after producing a plan. Inspect the source, change the code, create tests, run tests, repair failures and produce the real release artifacts.
- Work in small, understandable batches. Keep a progress journal such as `docs/engineering/AGENT_LOG.md`; update it at meaningful milestones with commands, actual outcomes, commit SHAs and links.
- Preserve all pre-existing user changes. Before editing, inspect `git status`, current branch, commit and untracked files. Do not discard unexplained changes. Do not run destructive cleanup commands against directories outside disposable test/build locations.
- Prefer repository-native commands and architecture. Do not rewrite the application from scratch merely to introduce a new framework.
- Choose stable, well-maintained libraries and inspect current official docs/release notes before relying on APIs, engine capabilities, licenses, packaging flags or security recommendations.
- Keep CPU-only operation independent of a GPU, Vulkan SDK, CUDA, Docker, cloud account, runtime model download, network key or developer toolchain. An optional accelerated build must not break the CPU baseline.
- Use bounded self-healing loops. Retry with a changed hypothesis, not the exact same command forever. After five materially different attempts to repair the same blocking root cause, write a technical blocker with logs and next steps; do not fake a pass or release.

---

## 1. Ground truth about the current repository

At the time this mandate was written, the repository README/status ledger identifies the following starting point. Recheck all of it at runtime; the repository may have moved since this file was authored.

### 1.1 Existing technology and implementation

- Python package: `hcs-discovery-studio`, Python `>=3.12,<3.14`, dependency-managed with `uv` and `uv.lock`.
- Backend: FastAPI/Uvicorn, Pydantic, SQLAlchemy, Alembic, SQLite, Typer CLI, RDKit, YAML workflows, report rendering.
- Frontend: React, TypeScript, Vite, React Router, TanStack Query and Playwright.
- Source frontend: `apps/web/`; Python package: `src/hcs_discovery/`; tests: `tests/`; documentation: `docs/`; CI: `.github/workflows/`.
- Entrypoint: `hcs-discovery`. Source development requires Python 3.12/3.13, `uv`, and Node.js compatible with the locked Vite version; current README says Node 22.12+.
- Current API is versioned under `/api/v1`; UI is embedded in the installed wheel.
- The current architecture aims for local-first behavior, loopback binding by default, explicit network policy, auditability, immutable workflow snapshots, SHA-256 hashes, run manifests, content-addressed node caching and a persistent SQLite queue.
- Existing scientific nodes include RDKit descriptors, Morgan/Tanimoto similarity, rule filters, Pareto/composite ranking and summaries.
- Existing import paths include CSV, SDF and SMILES, with per-row error retention and configured standardisation.
- A local OpenAI-compatible provider exists as a probe/configuration path, but the prior implementation ledger says there is no complete chat/tool-calling agent.
- Previously planned engines include AutoDock Vina, OpenMM, Chemprop, Boltz-2 and Chai-1; do not assume any is runnable until you inspect the current adapter and execute it.
- Workflows are documented as linear, single-input chains. Multi-input merges, branching, loops, subworkflows and parameter sweeps were not implemented in the starting ledger.
- The project contains 82 backend tests and 3 Playwright E2E tests in the starting documentation, with a reported 75% local coverage and a CI floor of 70%. Treat these as historical claims until reproduced on the actual current checkout.
- Project/dataset deletion has been documented as leaving some run files on disk by design; cache size has not been bounded in the prior ledger. Verify and fix these limitations safely.
- The previous TypeScript/Vite toolchain has been upgraded by Dependabot, so update all audit/docs that pin older versions after verifying `package-lock.json` and installed packages.

### 1.2 Baseline commit and CI

The latest inspected commit at the time of writing was `bd44f206b7c6a5897e503ef63dc7847461b65f63` (`chore: adopt Vite 8 toolchain and untrack tsbuildinfo`), with a completed green CI run `40680764054` on 2026-10-28. This is historical context, not a promise that the present `main` is still at this commit. Inspect the actual HEAD and Actions state before planning.

### 1.3 Known high-priority code-review leads

Prove or disprove each item with tests against the actual code. Do not blindly apply a proposed fix if newer code has already solved it.

1. **Pareto front correctness:** `src/hcs_discovery/workflow/nodes.py` historically builds each Pareto front by comparing a candidate to members already accumulated in that front. This can be order-dependent if a valid dominator occurs later in the candidate order, particularly when zero-weight score objectives make the composite ordering tie. Correct the nondominated-sorting algorithm and test dominance invariance under input permutation, ties, missing values and zero weights.
2. **Filter validation:** the old `RuleConfig` checked `between` for `value2`, but did not fully enforce operator/value type consistency. Invalid text supplied to a numeric operator may pass validation and later fail during `float(...)`. Validate type, finiteness, bounds and operator semantics before queueing.
3. **Descriptor exception handling:** the old descriptor loop broadly caught `Exception` and recorded `None`. Separate expected per-record chemistry failures from unexpected implementation errors, log structured diagnostics without leaking data, and mark incomplete outputs clearly.
4. **Ranking meaning:** Min-max normalized composite scores are relative to the current dataset and can change when outliers are introduced. Display that limitation, support explicit objectives such as maximize/minimize/target range/constraint/informational, and avoid treating generic descriptors as universally “better” in one direction.
5. **Playwright retries:** the old configuration allowed one CI retry. Make flaky tests visible and fail the CI build on flakiness where the installed Playwright version supports it; also forbid accidental `test.only` in CI. Investigate any retry-pass instead of hiding it.
6. **Dependency/license audit drift:** re-audit `docs/research/COMPONENT_AND_LICENSE_AUDIT.md` from the actual lockfiles and generated SBOM after the latest Vite/TypeScript upgrades.
7. **Reports:** the previous ledger says Markdown and HTML reports truncate large tables (historically 200/500 rows). Verify current behavior and state truncation prominently; full JSON/CSV/SDF exports must be complete and tested.
8. **Data deletion:** trace relational deletions and on-disk run artifacts. Provide explainable retention and deletion behavior, a preview/dry-run and tests; never promise removal while residual files remain.
9. **Cache lifecycle:** bound the cache by configurable size/age, add explainable eviction and a safe dry-run/status view, and test concurrent access.
10. **Mypy and RDKit stubs:** an earlier pinned RDKit distribution shipped an incompatible stub package and CI removed that package before mypy. Reassess the current version, document the rationale, avoid silently excluding application code from type checking, and revisit this workaround when upstream is fixed.

---

## 2. Phase 0 — Repository, environment and baseline audit (local first)

Do this before implementation.

1. `git status --short --branch`; record current branch and HEAD. Read existing `GEMINI.md`, `AGENTS.md`, `CONTRIBUTING.md`, `SECURITY.md`, release workflow, `pyproject.toml`, `uv.lock`, frontend package manifests, current README, implementation ledger, validation protocol, threat model and test guide.
2. Fetch the current origin state without overwriting local changes. If the checkout is behind, record divergence and integrate safely. Do not reset the working tree.
3. Inspect `git log --oneline -20`, open issues/PRs, all workflow files, tags/releases, latest Actions run and the generated release assets. Distinguish current source from claims about an earlier release.
4. Capture versions: OS, Python, `uv`, Node/npm, RDKit, browser/Playwright, frontend bundler, `hcs-discovery version`, CPU/RAM, detected graphics devices, Vulkan runtime/driver and whether each potential acceleration adapter actually works.
5. Reproduce all existing tests before changing code. Save raw logs under an ignored local `build/qa-baseline/` or equivalent, not in the distributable unless a concise audit report is intentionally committed.
6. Reproduce a complete CPU smoke journey: create project → import demo/library → inspect row outcomes → validate workflow → run → monitor events → inspect results → export reports → restart server → re-open results.
7. Capture baseline screenshots at desktop and narrow widths. Run accessibility and overflow checks on every route.
8. Build and smoke-test the current wheel from a clean environment. Confirm the SPA is present and works without Node at runtime.
9. Produce `docs/engineering/STABLE_V1_GAP_ANALYSIS.md`: current facts, defects backed by tests, unimplemented capabilities, risk/priority, planned implementation order and acceptance criteria. Do not edit the final polished README yet.

### Baseline commands

Use the installed/current versions and the repository’s own docs if they differ from these commands. Run from repository root unless noted.

```powershell
# Windows PowerShell examples
uv sync --dev
uv run hcs-discovery doctor
uv run hcs-discovery version
uv run ruff format --check .
uv run ruff check .
uv run python scripts/ci/prepare_typecheck.py
uv run mypy
uv run pytest -q --strict-markers --cov=hcs_discovery --cov-branch --cov-report=term-missing
cd apps/web
npm ci
npm run typecheck
npm run build
npm run test:e2e
npm run screenshots
cd ../..
uv build --wheel
```

If a documented command no longer applies, update the engineering instructions and use the equivalent current command. Never run a test against a stale `dist/` build when a frontend source change has been made.

### Baseline output requirements

The audit must record the actual outcome of every command, including exit code, OS and tool versions. A command that was not run is `NOT RUN`, not “pass”. A command that could not be run due to a missing system dependency is a blocker or an explicitly scoped optional check, not a pass.

---

## 3. Phase 1 — Engineering foundations and critical correctness

Fix proven correctness defects before adding major capabilities.

### 3.1 Data and chemistry invariants

- Preserve immutable raw input and raw source-row metadata. Derived structures must be stored with an explicit transformation history and versioned standardisation settings.
- Test canonicalization determinism, stereochemistry preservation, duplicate identity, invalid structures, salts/mixtures, neutralization, tautomer handling, formal charge, formula and InChI availability.
- Define the molecule identity policy explicitly: canonical non-isomeric SMILES must not be treated as equivalent to a stereochemistry-preserving identity. Ensure identity and deduplication use the intended representation and are documented.
- Input validation should cover empty files, max file size/row count, mixed encodings, unusual line endings, delimiter/header problems, duplicate column names, missing SMILES, malformed SDF records, large structures, too-long strings, invalid atom counts and malformed rows.
- Unexpected errors must be distinct from invalid user data. Retain row-level status and a stable error code without dumping secrets or massive raw structures into logs.
- Add import preview: show mappings, sample rows, warnings, estimated accepted/rejected/duplicate counts and standardisation options before persisting. Validate without creating permanent records or leaving temporary files behind.
- Test transaction rollback: a failed import must not leave orphaned database rows, partially-written uploads or inconsistent counts.

### 3.2 Workflow engine correctness

- Define typed data contracts for node inputs, output schemas, units, data direction, uncertainty, null policy and artifact outputs.
- Validate the entire workflow before it is queued: schema version, nodes, edge direction, cycles, disconnected nodes, unknown nodes, unknown properties, invalid configs, missing columns, type mismatches and incompatible units when units are defined.
- Preserve a frozen workflow snapshot and exact effective parameters per run. Existing results must not change when a workflow definition or engine installation changes later.
- Fix Pareto nondominated sorting using a correct algorithm; test the mathematical invariant, not implementation details. Permuting input rows must not alter which compounds belong to a front. Stable ties may use a deterministic tie-break for display order, but tie-breaks must not redefine scientific dominance.
- Reject non-finite objective values (`NaN`, `+inf`, `-inf`) or treat them under a documented missing-data policy. Never turn an absent objective into zero.
- Validate weight constraints: all weights nonnegative; at least one positive. Explicitly decide whether a zero-weight objective participates in Pareto dominance. Prefer a separate, explicit set of Pareto objectives so a zero-weight composite dimension is not ambiguous.
- Add objective types: `maximize`, `minimize`, `target_range`, `constraint` and `informational`. Give them distinct, tested semantics. A “target range” score should have a documented formula and property tests.
- Explain min-max normalization and sensitivity to outliers. Provide a sensitivity view/analysis showing whether ranking changes under reasonable parameter perturbations. Do not claim a universal drug score.
- Validate filter operators and values before a run. Reject invalid number/string/bool combinations, non-finite thresholds, invalid ranges, missing columns and silent coercions. Decide whether reversed `between` bounds normalize or fail and test that behavior.
- Make missing-value handling explicit in all numeric filters. A missing numeric value must not silently pass a constraint or produce a misleading string comparison.
- Every long-running node must report progress at appropriate intervals, check cancellation safely and preserve a structured failure state. Use per-node timeouts and bounded output sizes.
- Ensure cache keys include node implementation/config schema version, input content, effective config, dependency/engine version, workflow schema, seeds, model-weight hash, relevant backend, precision settings and any stochastic configuration that can alter results.
- Never cache errors or partial results as successful results. Cache files and database rows must be checksum-verified when read back.
- Make cache size/age limits configurable, expose `status`, `prune --dry-run` and `prune` behavior, and add tests for races, corrupt entries and interrupted writes.

### 3.3 Queue, persistence and lifecycle

- Test queue claim exclusivity, expired lease recovery, worker crash/restart, cancellation before/during execution, retry semantics, duplicate execution, event sequence ordering and partial artifacts.
- Document at-least-once execution and make node effects idempotent. Avoid describing the queue as exactly-once.
- The run state machine must reject invalid transitions, be enforced in service logic and be tested against concurrent updates.
- Ensure each job has heartbeat/lease policy, hard resource/time limits, cancellation polling and structured diagnostic context.
- On shutdown, stop accepting new work, close streams/connections gracefully and persist a recoverable status. Test interrupted termination.
- Add migration tests from an empty database and representative previous-schema databases. No destructive migration should silently discard data.
- Audit foreign keys and cascade rules for project/dataset/workflow/run deletion. The UI/CLI must show a preview of affected database entities and files and confirm destructive actions. Prefer soft-delete/trash or backup where appropriate; if actual deletion is promised, prove that all related artifacts and records are removed according to policy.
- Add database backup/restore, integrity checks and a documented recovery procedure. Test restoring a backup into a clean data directory and opening its existing projects/runs.

### 3.4 API/CLI contract

- UI, CLI and API must call the same domain/service layer. Do not fork scientific behavior between clients.
- Every endpoint must have typed input/output schemas, stable error codes, correct HTTP statuses, limits and documentation. Check pagination boundaries, sorting allowlists, injection-safe query construction, missing resources, repeated requests and interrupted streams.
- Add tests demonstrating that the same workflow/dataset/config yields equivalent core outputs through CLI, API and UI-triggered execution.
- Version APIs and workflow schemas explicitly. Document deprecation policy before calling v1 stable.
- `--json` output must remain parseable and consistent. Errors go to stderr or structured error envelopes, not mixed into successful JSON stdout.
- Verify SSE reconnect/replay behavior using sequence IDs, duplicate frames and dropped connections. Keep polling fallback and test that event state does not lose or double-count terminal transitions.

---

## 4. Phase 2 — Real scientific engine integrations

The stable product must have real, working, well-tested scientific breadth beyond a registry of planned engines. Build the adapter contract first, then integrate in order. Use current official documentation for every engine and record verified versions/licences. Do not bundle external weights/data unless their redistribution terms have been verified.

### 4.1 Shared adapter contract (mandatory for every engine)

Every adapter needs:

- stable adapter ID and version;
- an explicit status (`available`, `available_with_limits`, `not_configured`, `unavailable`, `blocked_by_policy`, `planned`);
- capabilities and known limitations;
- code, model weights and dataset licences recorded separately;
- supported file formats, units and required/optional inputs;
- exact model/engine version and hash where appropriate;
- capability and dependency probes that do not claim more than they actually verify;
- CPU baseline and optional backend information;
- resource profile and validated memory/time ceilings;
- deterministic seed control when available and an explanation of nondeterminism;
- logs, structured error codes, progress, cancellation, timeout and retry policy;
- reproducibility manifest, citations, artifact checksums and scientific limitations;
- offline mock tests, integration tests, an optional real-engine smoke test and a named benchmark when scientific accuracy is claimed.

Do not let arbitrary plugin code run in the main server process without documented trust boundaries. The initial trusted built-in adapters can share the process where appropriate, but third-party or user-provided tools should run as controlled child processes with an allowlisted executable, sanitized environment, explicit working directory, file/CPU/RAM/time limits and safe artifact exchange. Do not introduce mandatory Docker.

### 4.2 RDKit foundation (required)

- Retain working import, standardisation, descriptors, Morgan fingerprints, similarity and depiction.
- Add reference tables with exact expected values for a fixed, legally redistributable molecule set and the pinned RDKit release. Include stereochemical cases, charged molecules, salts, isotopes and edge cases.
- Record method, units, version and null/error semantics with every descriptor.
- Add structure export and depiction regression fixtures. Ensure generated SVG is sanitized before it is embedded in HTML or loaded in the UI.

### 4.3 AutoDock Vina docking (required real adapter)

Implement a fully executable CPU-capable docking workflow using the supported official Vina distribution/API. Verify packaging, input preparation and native dependencies from current documentation before choosing the integration technique.

Minimum working flow:

1. Import/choose target structure and ligands with clear identifiers and provenance.
2. Validate structures and report missing atoms, unsuitable formats, protonation/preparation problems, alternate locations, metals/cofactors and other caveats. Do not invent an automatic correction that silently changes the scientific object.
3. Define binding box by coordinates and dimensions, plus a discoverable interactive pocket/box view where feasible. All values and units are shown.
4. Expose documented engine parameters with validated bounds; capture seed, exhaustiveness and output pose count.
5. Run with progress/cancellation/timeouts and CPU-only fallback. Store logs, raw output, prepared inputs, pose files and parsed result tables.
6. Preserve original input and every preparation step. Record target/ligand hashes, engine and preparation versions, environment and exact effective command/configuration.
7. Visualize protein/ligand/pose in the UI where feasible and always provide downloadable standard structure artifacts; parse failures are visible.
8. Explain that docking scores are approximations and not experimental affinity or efficacy.

Tests must use redistributable tiny fixtures or deterministic synthetic fixtures for parser/contract tests. Add at least one documented real-engine smoke run on a known fixture and a scoped benchmark protocol; no assertion should claim universal binding correctness from one target.

### 4.4 Learned property prediction (required real adapter)

Integrate a real model family through a declared adapter (for example Chemprop or a validated, legally distributable equivalent) with a strict separation between code, weights and training/evaluation data.

- Support user-selected/downloaded models where licence allows; do not automatically download weights during ordinary CPU smoke tests.
- Model metadata includes task/endpoint, unit, training-data citation/version, weight checksum, architecture, version, supported chemistry and intended applicability domain.
- Preflight validates feature schema, task output and dependency/backend capability.
- Results include prediction, uncertainty/calibration where the method supports it, applicability-domain warnings, missing-input status and exact model identity.
- Evaluate using a development split and a held-out test split that is not used for tuning. Prefer scaffold split for molecular property work and time split for prospective settings when appropriate. Detect duplicate/near-duplicate leakage.
- Compare against an explicitly chosen trivial baseline and a simple descriptor baseline using metrics selected before final evaluation. Report sample count, missingness, confidence intervals, all folds/seeds, runtime and limits.
- No model can be promoted to “validated” merely because it runs or because its training score is high.

### 4.5 OpenMM molecular dynamics (real optional integration; include if dependencies and licence permit)

- Support a narrow, documented first use case rather than an unsafe “simulate any protein” button. Require explicit validated input assumptions, force-field choice, solvent/ions policy, integration parameters and runtime controls.
- Package as an optional adapter/dependency profile. The CPU-only app must run without OpenMM installed if the optional engine is not selected; its absence is reflected as `not_configured`, never as a fake success.
- Use small, legally redistributable fixtures for contract tests and scientifically meaningful stability/energy sanity checks for the supported workflow. Record precision, platform and nondeterminism.
- Expose system preparation artifacts and simulation outputs; explain limits and prohibit unsupported biological claims.

### 4.6 GNINA and OpenFE integration

Treat GNINA and OpenFE as real optional integrations, not as mandatory core dependencies if their upstream runtime requirements would compromise the dependable CPU install.

- GNINA: document supported platform/runtime and model weight licence; execute real inference/docking only when the matching adapter has passed an end-to-end probe. Report CUDA/Vulkan/CPU capabilities honestly; do not imply that GNINA itself has Vulkan support without verified upstream/runtime evidence.
- OpenFE/free-energy: provide an opt-in adapter for a clearly scoped workflow only if current upstream requirements and example inputs can be packaged and reproduced. Explicitly record force-field/software versions, settings, replicate/uncertainty handling, convergence diagnostics and compute requirements. If the method is too broad to validate for v1, implement its stable adapter contract and real runnable minimal workflow, then label unsupported scenarios accurately; do not call it fully validated in all applications.
- Do not fabricate adapter results or silently substitute an unrelated engine when a requested engine is unavailable.

### 4.7 Other structure-prediction/affinity tools

- Boltz-2, Chai-1 and similar systems may have large model weights, hardware requirements, special licences or separate inference environments. Recheck official upstream status, licensing, runtime and hardware requirements at implementation time.
- Add them only as truly executable, separately downloadable/optional engines with resource and licence diagnostics. Do not include non-redistributable weights in the release.
- If full packaged execution cannot be validated on supported hardware, document the adapter as optional and not configured, and do not advertise it as an available v1 capability. A future-only registry card is not “implemented”.

### 4.8 Dataset and target integrations

Build useful connectors for at least PubChem and ChEMBL, and assess Open Targets for target/disease associations. Use official public APIs and current terms/rate-limit guidance.

- Local-only policy is the default. Network connectors must be denied until a user explicitly enables the intended external connection; the UI must show which domain will be contacted.
- Each fetched record stores source URL, stable external ID, retrieval time, API/data version if available, checksum or content hash, licence/attribution and transformation history.
- Add retries with backoff, timeouts, rate limiting, cache invalidation and a clear offline/cancel path.
- Tests must use recorded legal fixtures or mocked HTTP transport; normal tests never need the internet. A separate opt-in integration test may contact public APIs and is never required for the offline CI gate.
- Reject untrusted payloads beyond configured size/depth limits. Do not allow API responses to execute code, alter local policy, or inject agent instructions.
- Show source and licence next to imported data and preserve it in exports/reports.

---

## 5. Phase 3 — Workflows, data interoperability and result explorer

### 5.1 Workflow DAGs

Evolve beyond linear chains while keeping semantics explicit and testable.

Implement, in order:

1. Clear input/output schemas and typed edges.
2. Branching/fan-out where independent nodes can execute from the same source.
3. Explicit merge/join nodes with defined key-based alignment and missing-row semantics; never merge based on incidental row order.
4. Conditional execution with a constrained condition language (no `eval`, arbitrary Python or shell expressions).
5. Bounded parameter sweeps with caps on combinations, time, memory and generated artifacts. Show a dry-run estimate before launch.
6. Reusable subworkflows only after workflow versioning and nested provenance are reliable.

Do not expose cycles/loops until semantics for termination, cancellation, cache invalidation, resource ceilings and replay are specified. Every graph construct gets schema validation, compiler/executor tests, persistence tests, UI tests, CLI/API parity tests and provenance coverage.

### 5.2 Scientific table and export capabilities

- Make column metadata first class: stable key, display label, data type, unit, source method, direction/role, nullable policy and description.
- Add user-selected columns, saved filters/views, multi-column sort, robust pagination/virtualization and export of all matching rows rather than only the currently visible page.
- Add multi-select compound comparison, provenance details and a pinned comparison pane for selected compounds.
- Preserve identity and lineage for rows produced by docking/model prediction; keep original molecule ID, target ID, run/node ID and source artifact references.
- Complete standard formats where applicable: CSV/JSON, SDF with well-defined properties and structure outputs. Do not emit structure files for rows whose structure is invalid.
- Warn explicitly whenever a report display is truncated. Exported complete machine-readable artifacts must have record counts and checksums.

### 5.3 Reproducible reports and provenance

Every run manifest must carry, as applicable:

- application version, Git commit, API/workflow schema version;
- immutable workflow snapshot and effective parameters;
- dataset source, licence, retrieval date and SHA-256;
- input/output row counts and row-level rejected/failed/missing counts;
- engine and dependency versions, model-weight hashes, backend actually used, hardware and platform;
- all seeds and relevant nondeterminism;
- timings and resource usage when actually measured;
- per-node status/errors, cache keys and implementation/schema version;
- artifact path, media type, byte size and SHA-256;
- relevant scientific citations, benchmarks and limitations;
- a clear status (`succeeded`, `partial`, `failed`, `cancelled`) and whether results are scientifically validated for a named task.

A manifest proves provenance of software outputs; it does not prove biological truth.

---

## 6. Phase 4 — Beautiful, usable and accessible scientific UI/UX

Preserve the working React architecture and current design tokens where useful. Improve the product itself rather than doing a superficial theme-only redesign.

### 6.1 Design direction

Create a polished, calm scientific workbench with an original HCS visual identity: strong hierarchy, elegant typography, consistent spacing, high-quality data tables, meaningful empty/loading/error states, carefully used colour, clean iconography and enough density for real research. Maintain light and dark themes. Avoid excessive glassmorphism, giant decorative cards, neon gradients or animation that reduces legibility. A scientific app should look beautiful without compromising accuracy or focus.

Create/maintain documented design tokens for colour, spacing, typography, radii, elevation, focus ring, motion and z-index. Components should consume tokens rather than inventing one-off values. Keep important UI strings accessible and avoid colour-only status cues.

### 6.2 Workspace/product flows

- New-project first run: “Import a library”, “Load a demo project” and “Build a workflow”, with clear expected inputs and privacy/network behaviour.
- Project overview: datasets, active/failed/recent runs, engine availability, storage/cache health and next actions.
- Import wizard: format detection, column mapping, sample preview, standardisation controls, licence/source fields, warnings and dry-run validation before commit.
- Compound detail: clear 2D depiction, canonical/isomeric identifiers, formula/charge, raw input and transformation history, computed properties with units/methods, warnings, source and run provenance.
- Model/engine registry: distinguish `installed and tested`, `available but not configured`, `blocked by policy`, `requires external install`, `planned` and `unavailable`. Only executable adapters can launch runs.
- Workflow editor: searchable node library, canvas, visible typed edges, contextual settings panel, undo/redo, auto-layout, keyboard alternatives to drag/drop, graph validation and output schema preview.
- Run monitor: streaming events, node state graph, progress, time/resource metrics when actually measured, cancellation/retry controls, logs and artifacts. A lost SSE connection must not make a running job look finished.
- Results explorer: configurable columns, table performance, persistent URL-backed filters/sort, multi-select, comparison, meaningful charts, clear uncertainty/limitations, reasons for filters/ranking and complete export.
- Local AI assistant: explicit Ask/Plan/Run modes, readable tool-call history, preview of planned actions, approval boundaries and traceable run IDs.
- Settings: network policy, model paths, CPU/GPU status, storage/cache controls, diagnostics, data backup/restore, privacy and security posture.

### 6.3 Interaction requirements

- No inert buttons or placeholder controls. Every visible action either works, is disabled with an explicit reason, or is visibly marked as planned/non-runnable. Prefer removing a fake control over showing an inactive one.
- Every form has validation before submission, useful field-level errors, preserved user input on recoverable failure and a summary of what can be done next.
- Destructive actions require a readable preview and confirmation. Cancellation explains whether the job stops immediately or at a safe point.
- Use semantic HTML, labels, button types, focus states, keyboard navigation, Escape handling, and proper dialogs. Never make clickable `<div>`s the only way to perform a core action.
- Support browser zoom to 200%, prefers-reduced-motion and narrow viewports. Keep text and tables readable at 320/360/390 px, but optimise scientific desktop tasks for wider layouts too.
- Provide `Ctrl/Cmd + K` command/search palette for projects, datasets, workflows, compounds, engines and runs where it can be implemented reliably.
- Add keyboard shortcuts only where discoverable, conflict-free and documented. Provide non-drag alternatives for all core canvas tasks.
- Use skeletons for loading without layout jumps; no false data placeholders. Provide accessible status announcements for job completion/failure.
- Persist user preferences intentionally. Do not put sensitive credentials or experimental data into browser localStorage.

### 6.4 Visual QA matrix (must be automated)

Test all important pages and states at minimum:

- Viewports: 1440×900, 1280×800, 1024×768, 768×1024, 390×844 and 320×700.
- Themes: light and dark.
- State variants: first-run/empty, populated, long IDs/long labels, error, loading, disabled engine, active run, completed run, failed run, cancellation, validation failure, zero results, thousands of results, missing image/structure, truncated logs/report and modal open.
- Zoom/accessibility: 200% zoom-equivalent checks, keyboard-only main flow, reduced motion, high contrast where available, focus order and axe/a11y automated scan.
- Geometry: `scrollWidth <= clientWidth` for page shell and major panels unless horizontal scrolling is intentional and visibly contained. Fail on accidental page-wide horizontal overflow.
- Screenshot assertions: deterministic fixtures, fixed test time where possible, stable fonts, no remote images, fixed viewport/device scale, reproducible seeds. Use Playwright visual snapshots with a reviewed baseline. Never blindly overwrite the baseline to silence a mismatch.
- On failure: upload actual/expected/diff images, trace, browser console errors, failed network requests and relevant server logs.
- Keep a human visual review checklist in `docs/developer-guide/VISUAL_QA.md`; automated pixel equality is not a substitute for checking meaning, hierarchy and usability.

### 6.5 Performance and usability targets

Set measurable budgets and record baseline/result, for example: startup-to-health-ready, first-render time on a clean local launch, table interaction responsiveness at 10k rows, memory use for a defined fixture, workflow validation time and cancellation latency. Do not assert a universal speed number from one machine. Avoid loading all results to render a page; virtualize/partition large datasets and ensure charts clearly label any sampled/truncated subset.

---

## 7. Phase 5 — Safe agentic research assistant

Build a real local assistant, not a chat-shaped mock. The assistant must be useful for composing and running workflows while respecting the scientific execution and network policies.

### 7.1 Model/provider layer

- Support OpenAI-compatible local endpoints (for example a local llama.cpp server or local inference application) using explicit URL/model/timeout configuration and policy checks.
- Default network policy is local/offline. Remote models/connectors require deliberate opt-in, visible domains and explicit permission. No secret may enter prompts, logs, model messages or reports.
- Probe compatibility, model ID, supported tool-calling/structured-output behaviour, timeout and failure modes. A successful `/models` request is not proof that reliable tool calling works.
- Do not bundle a large model or weights by default. Let users select local model files/download optional model packs only when licence and checksum are known; downloads need clear consent, disk-space estimates and interruption recovery.
- Provide CPU inference where the selected model/runtime supports it. The Vulkan build can additionally accelerate compatible inference only after a real probe and output-parity smoke test. If unsupported, fall back to CPU with a visible explanation.

### 7.2 Agent modes and permissions

Implement three explicit modes:

1. **Ask:** read-only questions over current project data, docs, engine status and existing manifests.
2. **Plan:** produce an editable structured plan, tools to be called, required inputs, estimated resources if measurable, external access needs, expected artifacts and scientific limitations. No mutation or long job is started.
3. **Run:** execute only approved typed tools. Show a preview before external downloads, destructive operations, large resource usage or other high-impact actions.

Tool calls must go through narrow server-side functions, not arbitrary shell strings. Provide allowlisted tools for project/dataset inspection, schema validation, workflow creation/edit, run launch/cancel/status/results, report export and engine probes. Validate each tool argument with strict schemas; check permissions and current state again at execution time. Prevent prompt-injection from dataset text, external webpages, SDF/CSV fields, model cards and logs. Treat all data content as untrusted data, never as instructions to change system policy.

### 7.3 Agent verification and UX

- Record plan, approvals, model/provider, tool calls, inputs/outputs, run IDs and final report for reproducibility.
- Agent conclusions must cite the app's saved run/manifest and distinguish observed values from interpretations.
- When a tool fails, surface the real error and offer a corrected next action. Do not hallucinate an output or claim the tool succeeded.
- Every final summary lists which engines really ran, which did not, important caveats, source data and artifacts.
- Add tests for tool-call validation, denied network access, prompt injection in filenames/data/remote content, malformed JSON, repeated tool calls, timeouts, cancellation, permission changes mid-plan, and a model that produces unsafe/invalid requested actions.
- Never let an agent modify its own tests, branch protections, security policy or release gate to claim completion.

---

## 8. CPU and Vulkan: same core features, optional acceleration

The CPU release is the compatibility baseline and cannot require Vulkan/CUDA or a GPU. The Vulkan release is a separate, optional build that contains every stable core feature and adds acceleration only for adapters that genuinely support and pass tests on that build.

### 8.1 CPU-only release

Must work on supported x86-64 Windows and Linux machines with no GPU, Vulkan runtime, CUDA, Docker, Node.js, compiler, Python installation or source build. Bundle the backend runtime, required native libraries, built SPA and launcher. A system browser may be used to display the local UI; document that clearly. Ensure the server binds to loopback only and launches with a random/free local port or robust port-conflict handling. The app must not open a public network listener by default.

Required CPU gates:

- no installed Python/Node toolchain on the test machine;
- no Vulkan device/runtime required;
- startup and health readiness check;
- automatic browser opening (with documented `--no-browser` or equivalent option);
- normal close/shutdown without leaving orphan processes;
- data directory is user-writable and outside the install directory;
- upgrade does not delete existing user data;
- network disabled by default;
- full RDKit/workflow/export flow completes;
- app restart recovers stored projects/runs;
- installer/uninstaller and portable package tested on a clean VM/user profile.

### 8.2 Vulkan-enabled release

Investigate current upstream documentation before choosing the runtime. `llama.cpp` has a documented Vulkan backend (`GGML_VULKAN`); it may be a sensible optional backend for local LLM inference if the selected binary, driver and model actually work. Do not assume RDKit, AutoDock Vina, OpenMM, Chemprop, GNINA, Boltz-2, Chai-1 or an arbitrary user model accelerates with Vulkan.

- Build Vulkan support as an optional capability bundle/variant, not as a requirement of the core application.
- Keep the scientific feature set and API semantics identical to the CPU build. Backend-specific acceleration is additive; if unsupported, the corresponding task still runs on CPU where an actual CPU implementation exists.
- Probe driver/runtime/device, supported backend and model compatibility separately. Record `detected`, `available`, `validated`, `active`, `fallback` as separate states where necessary.
- For an inference adapter, run an explicit warm-up/inference smoke test on the actual Vulkan runtime and compare output type/shape plus numerical quality against CPU within justified tolerances. Record device, backend build, runtime version and error details.
- Offer Auto/CPU/Vulkan selection where supported. Default to Auto only when capability validation succeeds; provide an explicit CPU-only override for debugging.
- A Vulkan crash, out-of-memory error or unsupported operation may fall back to CPU only if restart/retry and state handling are safe. State visibly which backend was used; do not silently claim acceleration.
- Include Vulkan runtime dependencies required for redistribution, respecting each licence. Do not bundle drivers that belong to the user’s OS/GPU vendor. Document compatible driver/runtime requirements.
- Test the Vulkan variant both on a device with working Vulkan and on a machine without a Vulkan device. The latter must still open the app and use CPU-only features.

### 8.3 Performance claims

Benchmark CPU and Vulkan builds on at least one declared hardware/software setup using the same models, inputs, precision, prompt/parameters, warmup, number of measured runs and reporting method. Report median and spread, throughput/latency, peak RAM/VRAM where measurable and actual fallback status. Do not promise a fixed multiplier or imply every scientific engine is faster. In README and release notes, state exactly what has been benchmarked.

---

## 9. Installable releases: Windows EXE and Linux packages

A user must not have to install Python, Node or compile the repository to use the official release. Developers must still be able to build from source using documented commands.

### 9.1 Choose and prove the packaging architecture

Review packaging options and current official documentation. The simplest dependable route is preferable to introducing a large new desktop shell without need. Candidate approach:

- build the React SPA;
- bundle Python backend and RDKit/native dependencies with a proven packager such as PyInstaller plus required hooks/spec configuration;
- ship a launcher executable that starts the local API, waits for `/api/v1/health`, opens the default browser and manages shutdown;
- package on the native runner for each target OS (do not cross-compile native artifacts from the other OS);
- keep mutable user data outside the installed application bundle;
- use an OS-native installer/portable bundle wrapper where practical.

A one-folder bundle plus a Windows installer may be more reliable than a monolithic `--onefile` executable with complex native dependencies. Test the real user path before selecting it. Packaging a wheel alone does not fulfil the no-self-build requirement.

### 9.2 Minimum Windows outputs

For x86-64 Windows, produce and smoke-test at minimum:

- CPU-only installer `.exe`;
- CPU-only portable `.zip` if practical;
- Vulkan-enabled installer `.exe`;
- Vulkan-enabled portable `.zip` if practical.

Each installer must include the application, bundled UI, runtime dependencies, icon/branding, version information, licence notices and launcher. Prefer a reputable Windows installer generator such as Inno Setup if it fits the chosen layout. Use a code-signing certificate only if available; never fake a signature or state that an unsigned installer is signed. Clearly disclose Windows SmartScreen warnings if signing is unavailable.

Test install, launch, health readiness, main user journey, closing, uninstall and upgrade preserving existing user data. Verify spaces and Unicode in install/data paths, non-admin install where possible, port collision, antivirus-like locked files and missing optional Vulkan runtime. Use clean Windows runners and, before stable release, a clean Windows VM or equivalent independent environment.

### 9.3 Minimum Linux outputs

For x86-64 Linux, produce and smoke-test at minimum:

- CPU-only AppImage when the packaging/runtime compatibility is genuinely verified;
- CPU-only portable `.tar.gz` as a fallback where useful;
- Vulkan-enabled AppImage and/or portable bundle with clear system-driver requirements.

A `.deb` package is a welcome optional output if it can be built and tested properly. AppImage should not be called universal until exercised on a reasonable compatibility matrix. Build on Linux runners and test on a clean Linux environment without development Python/Node. Check executable permissions, desktop entry, icon, writable XDG data/config directories, browser launching, shutdown and no Vulkan fallback crashes. Document required system libraries/graphics drivers precisely.

### 9.4 Shared packaging requirements

- Never store writable databases, uploads, caches, models or user reports inside a protected installation directory.
- Separate code/resources from user data with documented path resolution and environment overrides.
- Generate a build manifest with commit SHA, app version, target OS/architecture, dependency lock hashes, frontend build hash, packaging-tool version and CPU/Vulkan variant.
- Create fresh-environment smoke tests that import RDKit, initialise the DB/migrations, serve the SPA, call health endpoint, import fixture, run a workflow, export a report and restart the app.
- Test the packaged bundle itself, not only the source checkout.
- Generate `SHA256SUMS.txt`, SBOM (CycloneDX or compatible), licence notices, release notes and GitHub artifact attestations for distributable artifacts where the current GitHub environment supports it.
- Verify every downloaded/published artifact against the generated checksum and verify provenance using current official GitHub procedures. Do not claim provenance or signatures unless verification actually passes.
- Build artifacts reproducibly as far as practical. Record sources of nondeterminism in the build process.
- Do not include model weights or external databases by default unless licences and redistribution rules are explicitly cleared.

### 9.5 Release naming

Use clear, consistent names, for example (adjust to project conventions, but preserve the distinction):

- `HCS-Discovery-Studio-1.0.0-Windows-x64-CPU-Setup.exe`
- `HCS-Discovery-Studio-1.0.0-Windows-x64-CPU-Portable.zip`
- `HCS-Discovery-Studio-1.0.0-Windows-x64-Vulkan-Setup.exe`
- `HCS-Discovery-Studio-1.0.0-Linux-x86_64-CPU.AppImage`
- `HCS-Discovery-Studio-1.0.0-Linux-x86_64-Vulkan.AppImage`
- `SHA256SUMS.txt`, `sbom.cdx.json`, `THIRD_PARTY_NOTICES.txt`, `BUILD_PROVENANCE.md`

Only include an artifact in the release if it was successfully built and tested. If a specific Vulkan variant cannot be correctly packaged for one OS, do not fabricate an output: block the intended full release scope or label the actual availability honestly and explain the limitation. The CPU-only path must always be deliverable first.

---

## 10. Security, privacy, licenses and operational trust

- Default to local/offline. Make every network route explicit and policy-checked. Tests must prove that blocked external destinations cannot be contacted through connectors, model calls, redirect chains or malformed URLs.
- Loopback is the default server bind. Non-loopback binds require explicit configuration and authentication. Do not treat a static bearer token as equivalent to user accounts/roles, and do not present local single-user mode as multi-user secure hosting.
- Avoid SSRF: validate schemes/hosts/ports, block private/local metadata destinations when external fetch is allowed, revalidate redirects and resolve DNS safely. Enforce timeouts and response size limits.
- Sanitize HTML, SVG and user-controlled labels in reports/UI. Test XSS payloads in names, SMILES fields, imported descriptions and model/connector responses. Never execute SVG scripts or imported workflow code.
- Protect artifact/path resolution against traversal, symlinks and path confusion. Artifacts must remain inside the configured data root.
- Redact secrets and sensitive raw data from structured logs, errors, HTML reports, event streams and screenshots.
- Use request IDs and stable error envelopes; add secure headers and CSRF/origin protections appropriate to the actual local server/browser flow. Check CORS rather than allowing broad origins.
- Add dependency audit, secret scanning, CodeQL/static analysis, lockfile review, licence policy and dependency review in CI. Pin GitHub Actions to reviewed immutable commit SHAs where the repo's policy already does so.
- Review dependency licences, model code licences, weight licences, dataset licences and asset licences separately. Store upstream URL, version and date of the audit. Do not infer the licence for weights from the licence of model code.
- Keep a threat model current. Add a vulnerability reporting procedure in `SECURITY.md`.
- Provide safe logs/support bundle export that strips secrets, credentials, private prompts and dataset contents by default.
- Test user data deletion honestly; explain any retention policy before deleting. Provide backup/restore to protect valuable local research.

---

## 11. Testing architecture: no false green builds

### 11.1 Required testing layers

1. Unit tests for pure functions, schemas and invariants.
2. Property-based tests (Hypothesis or an equivalent already installed) for parsers, canonicalization, table operations, ranking, filters, schema validation, serialization and cache key sensitivity.
3. Contract tests for every adapter and API schema.
4. Integration tests for DB transactions, migrations, workers, queue recovery, artifacts, SSE and local process boundaries.
5. API/CLI/UI parity tests for the same actions and error states.
6. Playwright E2E for every core end-to-end user journey, including failures and cancellations.
7. Screenshot/visual regression and accessibility audits.
8. Scientific validation/benchmark suite separated from quick correctness tests.
9. Performance, memory, large-input, cancellation and crash/recovery tests.
10. Security, licence, secret, dependency and packaging tests.
11. Clean-install tests for source, wheel, Windows installer/portable bundle and Linux package.
12. Vulkan capability/backend tests on a genuinely Vulkan-capable runner/host, plus CPU-only fallback tests on a host without Vulkan.

### 11.2 Required scientific unit and property tests

- **Standardisation:** equivalent structures, retained stereochemistry, transformations, invalid inputs, empty inputs, atom/length limits, salts and mixtures.
- **Descriptors:** expected reference values and metadata, correct null handling, known engine version, deterministic output where expected.
- **Fingerprints/similarity:** range [0,1], self-similarity, symmetry when applicable, deterministic settings and known examples.
- **Filters:** every operator at/beyond bounds, mixed types, booleans, nulls, NaN/infinity, reversed bounds, multiple rules and flag/drop modes.
- **Ranking:** dominance invariant, permutation invariance of fronts, exact handling of ties, missing values, zero weights, objective direction, target-range semantics, constraints, sensitivity to outliers and stable deterministic ordering.
- **Cache:** same inputs/config/engine → same key; every relevant input/version/seed/backend/weights change → key changes; corrupted output is detected.
- **Artifacts:** checksum, byte size, path containment, export round-trip, truncated/large data and stable media type.
- **Manifests:** exact run config/versions/seed/provenance/limitations and terminal status; incomplete runs never get a success manifest.

### 11.3 Mutation testing and test effectiveness

- Add a mutation-test stage for especially important code paths: filter comparisons, objective direction, Pareto dominance, cache key composition, policy defaults and error handling. Choose a maintained mutation testing tool compatible with this project's Python version and CI; if it is unsuitable, write targeted mutation-style regression checks.
- Report mutation score with context; do not chase 100% at the expense of meaningful tests. Set a minimum target for critical modules, and record surviving mutations and why they are equivalent/unimportant.
- Keep coverage floor at least the current 70% baseline; raise it toward 85%+ overall and near-complete branch coverage for critical scientific/security functions as the test suite matures. Do not enforce a new global threshold until reproducibly achieved locally and in CI. Never treat coverage alone as correctness.
- Ensure every test failure results in a non-zero exit. Do not use blanket `continue-on-error`, swallowing exceptions or hidden skips on required jobs.
- Make flaky Playwright tests fail the required gate, while retaining traces/screenshots for diagnosis.
- Avoid assertions about wall-clock durations unless a test uses generous, justified bounds for a timeout contract. Performance benchmarks are separately versioned and compared with tolerances.

### 11.4 Test inventory and coverage reporting

Create `docs/developer-guide/TEST_MATRIX.md` mapping every stable user capability to test IDs/commands and evidence. For each capability list unit, integration, API/CLI, E2E, visual, security and scientific checks as applicable. A capability with no test has an explicit owner/priority, not an implicit “done”. Publish coverage/test reports as CI artifacts and optionally a badge only if the report is actually generated by the current CI.

### 11.5 Minimum CI gate commands

Adapt for exact repo setup and use the same script locally and in Actions:

```bash
uv lock --check
uv sync --frozen
uv run ruff format --check .
uv run ruff check .
uv run python scripts/ci/prepare_typecheck.py
uv run mypy
uv run pytest -q --strict-markers --cov=hcs_discovery --cov-branch --cov-report=term-missing --cov-report=xml --cov-fail-under=70
cd apps/web
npm ci
npm run typecheck
npm run build
npm run test:e2e
# Add the real visual, accessibility and package smoke commands created in this mission.
```

Run the required Python gates on Linux and Windows. Run frontend build/type checks and Playwright on a supported Linux CI runner. Add clean migration, wheel/source install, standalone bundle and package smoke jobs. Add Vulkan build/test jobs only on runners where the necessary toolchain/runtime/device capability is verified; always test CPU fallback in other jobs. Mark external API tests optional/opt-in rather than making baseline CI network-dependent.

---

## 12. Local-first self-healing loop: implement everything before cloud validation

This is the required day-to-day loop. Repeat until all local release gates pass.

### Loop A — implement one coherent unit

1. Select the highest-priority unresolved item from the gap analysis.
2. Read the actual code, tests, dependency docs and any relevant upstream changelog.
3. Write a concise design note for any nontrivial behavior/contract change.
4. Write a regression test that fails on the current bug or establishes the desired feature contract.
5. Implement the smallest coherent solution. Avoid broad refactors unless necessary and separately tested.
6. Run the new test and targeted tests. Confirm the test would fail if the bug were restored, where practical.
7. Run formatting, lint, type checks and the full relevant test layer.
8. Review the diff manually for scope creep, secrets, generated files, incorrect claims and missing tests.
9. Update the implementation status ledger, agent journal and affected technical docs, but keep the final marketing README polish for the final documentation phase.
10. Commit a coherent local checkpoint once that work unit passes. Do not push prematurely while the entire local validation phase is still failing.

### Loop B — fix every failure by root cause

When any command fails:

1. Capture the full command, exit code and first/root traceback; separate the initial cause from cascading failures.
2. Reproduce with the narrowest test/command.
3. Form a concrete hypothesis and verify it against code/docs or an experiment.
4. Add/adjust a regression test for the underlying defect; do not merely loosen the failing assertion.
5. Change code/config only after the hypothesis is supported.
6. Re-run the narrow test, then adjacent tests, then the complete local gate.
7. If the same failure remains, revise the hypothesis. After five distinct, evidence-backed attempts, document a blocker and do not claim the gate passed.
8. If the cause is environment-specific, create a reproducible diagnostic and check the actual clean environment; do not mark the test “not relevant” without evidence.

### Loop C — no premature feature completion

A feature cannot be called complete merely because it compiles or appears in the UI. Require all applicable items: working implementation, validation, real error handling, regression tests, integration test, UI state, accessibility, documentation, licence review, security review, actual output artifact and a reproducible demo command.

### Required local exit criteria

Do not begin the cloud validation phase until:

- all required code/static checks pass locally;
- all backend tests pass;
- all frontend type/build checks pass;
- E2E and visual QA pass on the actual final SPA build;
- scientific core invariants and required validation runs pass;
- the wheel and standalone local packages build;
- fresh-environment package smoke tests pass;
- CPU-only functionality passes with Vulkan absent;
- Vulkan variant passes its local capability checks where hardware/toolchain is available, or the precise missing external requirement is documented without a false pass;
- security/licence checks are clean or an explicitly approved, documented exception is non-blocking;
- the documentation ledger is internally consistent;
- the working tree contains no accidental binaries, caches, secrets, `.tsbuildinfo` files or user-generated data.

If the local environment lacks a Vulkan GPU/runtime, build the Vulkan artifact in the appropriate environment or CI runner and test it on a real capable runner. Do not infer success from compilation alone.

---

## 13. Cloud phase — reproduce the complete gate in GitHub Actions

Only after all local required gates pass for the same revision:

1. Verify Git identity, remote, branch protection, CI permissions and available release credentials without printing secrets.
2. Push a dedicated stable-release branch or the intended branch according to the repository's actual policy. Do not force-push.
3. Watch Actions to completion. Inspect all jobs and steps, not just the aggregate green badge. Download artifacts/logs when a job fails.
4. Compare cloud output to local output. Check lockfile drift, platform-specific path handling, case sensitivity, native RDKit imports, fonts/browser availability, SQLite migration behavior and packaged-file inclusion.
5. If any cloud job fails, reproduce/fix locally, run the relevant/full local gate again, commit, push and repeat the relevant cloud workflow. Never patch only a CI script to ignore the underlying failure.
6. Repeat until all required jobs are truly green on the final HEAD SHA. Verify `git rev-parse HEAD`, GitHub Actions `head_sha`, built artifact SHA and intended tag target agree.
7. Ensure required jobs did not pass only because a step was skipped, `continue-on-error` was enabled, a job was conditionally bypassed or a test retried successfully while flaky.
8. Preserve CI artifacts for tests, coverage, Playwright reports, screenshot diffs, package smoke logs and scientific benchmark results.
9. Run dependency review and security jobs on the relevant PR/event and verify that “skipped” reasons are expected; required checks must not rely on a job that never ran.
10. Confirm the cloud build artifacts are from a clean checkout and do not include untracked files from a developer machine.

### Cloud acceptance criteria

- Required backend CI green on Linux and Windows.
- Frontend typecheck/build green.
- E2E/visual/accessibility jobs green, with no flaky test tolerated as green.
- Clean database migration and restore smoke test green.
- Wheel/standalone installer/package jobs green.
- License policy, dependency audit, secret scan, CodeQL and dependency review green or explicitly documented according to the repository's actual policies; no critical/unresolved release blocker.
- CPU-only package test green on a machine without Vulkan.
- Vulkan variant successfully probed and exercised on compatible hardware, plus graceful CPU fallback tested without a device.
- All outputs tied to the same commit and the release notes do not outclaim the evidence.

---

## 14. Final README, repository SEO and HCS branding — do this near the end

The README rewrite is the final documentation/content-polish phase, after features and package names/links are real. It must describe the released software, not future intentions. If README changes affect markdown links, screenshots, workflow badges, build instructions or package names, rerun docs validation, link checks, screenshot asset checks and the full final cloud CI before tagging. Updating the README last does not waive tests.

### 14.1 README structure

Create a readable, accurate, polished README in this order:

1. HCS logo/wordmark and concise title.
2. A one-sentence factual value proposition and `Made with ❤️ by hcsmedia` attribution.
3. Accurate badges: current CI status, latest stable version/release, supported OS/runtime, license, and any coverage/CodeQL badge only when backed by a real active workflow.
4. Short project description and a prominent honest “What works in v1.0.0” list.
5. Download/install section with direct GitHub Release links for Windows CPU, Windows Vulkan, Linux CPU and Linux Vulkan artifacts that truly exist; clearly distinguish installer/portable/AppImage and CPU/Vulkan requirements.
6. Very quick start for users who install a release without building source.
7. Screenshot gallery using committed, current screenshots that were captured from the actual stable build. Include workspace, workflow editor, active/failed run and result explorer, light/dark and desktop/narrow states when useful.
8. Key features, explicitly separating supported engines from optional/unavailable ones.
9. Example workflow/demo with real commands and expected artifact names. Use only outputs that a fresh install reproduces.
10. CPU/Vulkan matrix and what acceleration really applies to.
11. Architecture diagram and concise architecture explanation.
12. Scientific validity/limitations and the distinction between computational results and experimental evidence.
13. Reproducibility, datasets/licences/provenance, reports and citation instructions.
14. Security/privacy/network policy and model/data licensing.
15. Development/build/test commands.
16. Troubleshooting, contribution guide, changelog, citation and licence.
17. Links to detailed user/architecture/testing/validation/security docs.

Keep marketing copy clear and compact enough for first-time visitors; move exhaustive explanations into the right docs. Do not hide limitations at the bottom if users could reasonably misinterpret a result.

### 14.2 SEO and discoverability without keyword spam

- Set a precise GitHub repository description using the GitHub UI/API if permissions permit. Example: “Local-first open-source computational drug-discovery workbench with reproducible workflows, RDKit, docking and validated model adapters.” Adjust it to the *actual* stable capabilities; remove any engine that did not make the release.
- Add relevant GitHub repository topics (lowercase, hyphen-separated, no irrelevant spam). Candidate topics after verifying the actual feature set: `drug-discovery`, `cheminformatics`, `rdkit`, `computational-chemistry`, `molecular-docking`, `open-science`, `scientific-workflows`, `reproducible-research`, `bioinformatics`, `molecular-dynamics`, `machine-learning`, `local-first`, `python`, `react`, `fastapi`. Keep within GitHub's current topic limits and use only accurate concepts.
- Use descriptive headings and natural terms people search for: computational drug discovery, cheminformatics, molecular docking, RDKit, reproducible scientific workflows, CPU-only, Vulkan inference where truly supported.
- Make the README title, opening sentences, repository description, release name and screenshot alt text consistent. No keyword stuffing or fake claims.
- Add a concise project description and canonical documentation links. If there is a public project website, set a real homepage URL; never invent one or point to a broken page.
- Check that the repository is public if its public discoverability is intended, that the About description/topics are saved, and that main docs are linked from README.
- Avoid giant badge rows or irrelevant badges. A badge is a verifiable signal, not decoration.
- Validate README links, relative image paths, alt text, rendered Markdown, release links and anchors. Every screenshot must load on GitHub.
- If a website is shipped in this release, include appropriate title/description/canonical/Open Graph metadata and structured data only when the deployed website actually serves them. Do not assume a localhost SPA is indexed like a public web site.

### 14.3 HCS logos and GitHub visuals

Create a clean, original HCS Discovery Studio brand system; do not copy the GitHub Octocat or third-party product logos as if they were HCS branding.

Required source-controlled assets (paths may follow existing conventions, but make one canonical source):

- `apps/web/public/favicon.svg` — small simplified geometric HCS mark;
- `apps/web/public/brand/hcs-discovery-mark.svg` — vector icon/mark;
- `apps/web/public/brand/hcs-discovery-wordmark.svg` — mark + readable wordmark;
- `docs/assets/branding/social-preview.png` — 1280×640 recommended GitHub/social preview image, under 1 MB and readable at thumbnail size;
- optional matching PNGs for README/release pages and an icon file suitable for Windows installer/EXE.

Visual direction: original geometric chemistry/network/hexagon motif that reads at 16–32 px, clear `HCS` silhouette, restrained dark navy/charcoal plus a tasteful cyan/teal or warm accent, sufficient contrast, generous negative space, and “HCS Discovery Studio” plus “Open science. Reproducible discovery.” on the social preview. Include `Made with ❤️ by hcsmedia` as a secondary credit without overpowering the title. No false claims like “SOTA AI”, “experimentally verified” or “all engines included”.

Generate the image from original SVG/vector source or scripted rendering so it is reproducible; keep source editable. Check that PNG exports contain no accidental transparency issue, clipping, unreadable microtext or excess file size. Add meaningful alt text and use relative asset links in Markdown. Validate the EXE/icon asset on the actual packaged launcher.

GitHub repository appearance has two separate parts:

1. **README logo:** commit the logo files and display a relative image such as `docs/assets/branding/hcs-discovery-wordmark.svg` at the top of `README.md`.
2. **Social preview (Open Graph card for repository links):** GitHub normally needs the image uploaded in repository **Settings → Social preview → Edit → Upload an image**. The recommended image dimensions are at least 640×320, with 1280×640 preferred, and the file must be under 1 MB. Use the prepared `docs/assets/branding/social-preview.png`. Attempt the authenticated API/UI path only if available and permitted; otherwise clearly record the exact manual action, without claiming it has been configured.

Also create consistent favicon/browser metadata, installer icon and docs logo. Do not confuse the repository social preview with the owner's GitHub profile avatar or with a website favicon; they are separate assets/settings.

Official GitHub documentation:
- Repository customisation and social preview: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository
- Social preview details: https://docs.github.com/en/enterprise-cloud@latest/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview
- Repository topics: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics

### 14.4 Honest status tables

README status tables must use precise statuses such as:

- `Available and tested`: runs end-to-end in a supported clean install and has the required tests.
- `Available with limits`: works, but limitations and required setup are directly shown.
- `Optional / not configured`: real integration exists but needs an external model/runtime/setup.
- `Planned`: no runnable implementation; not offered as a runnable feature.
- `Unsupported`: not supported by current code or release package.

Do not write “every UI action has a CLI equivalent” unless tested for all advertised actions. Do not write “offline” if a core flow silently downloads something. Distinguish installation-time downloads from runtime network traffic. State exactly what the Vulkan variant accelerates and what remains CPU-only.

---

## 15. Stable release gates and final release procedure

The stable release is not made merely because the code compiles or a prerelease can be uploaded. All relevant gates below must be true.

### 15.1 Scientific release gates

- Each claimed scientific capability has a named, tested workflow and a scoped validation protocol.
- Descriptor/reference tests and import/identity invariants pass.
- Pareto/filter/scoring properties are covered by regression/property/mutation-style tests.
- Each predictive model has a clearly defined endpoint, versioned/legal data, appropriate split/leakage checks, simple baselines and metrics chosen in advance. Report uncertainty and limitations where supported.
- Docking adapter executes real runs, saves poses/logs/parameters and has a reproducible smoke example. Its reported performance is not called experimental binding evidence.
- Every optional engine state is accurate; no planned entry can execute accidentally.
- Reports and manifests record the full provenance of the actual computation.

### 15.2 Product/UX release gates

- New-user workflow from first launch to report can be completed without reading developer docs.
- Core actions work on mouse, keyboard and narrow layouts; no inert primary controls remain.
- Empty/loading/error/cancel/partial states are clear.
- Tables and plots disclose truncation/sampling and can export complete data.
- Accessibility checks and manual keyboard/contrast review are complete and defects fixed or documented with explicit justification.
- No accidental horizontal overflow; light/dark themes both have legible charts, forms and dialogs.
- Agent Ask/Plan/Run modes work, enforce policy and report actual tool execution.

### 15.3 Engineering/security release gates

- All local and cloud tests from this mandate pass on the final commit.
- No known critical/high security vulnerabilities in shipped dependencies unless assessed, mitigated and transparently approved. No leaked secrets.
- License/third-party notices and SBOM agree with shipped artifacts.
- Database migrations and backup/restore work on clean and upgrade paths.
- Cache, user-data paths, deletion, queue recovery and cancellation are tested.
- API/CLI contracts and workflow schemas are versioned/documented.
- The wheel and both platform package families are smoke-tested from clean environments.
- CPU release runs without Vulkan/Node/Python build tools; Vulkan release runs on real compatible hardware and degrades gracefully to CPU where supported.
- Install/update/uninstall do not unexpectedly destroy user data.

### 15.4 Release-candidate procedure

1. Freeze features; fix only release-blocking defects.
2. Update version metadata consistently (`pyproject.toml`, frontend/package metadata if applicable, about/version output, changelog and release config). Do not change release version in unrelated places.
3. Rebuild frontend, all Python/package outputs and app installers from a clean checkout at the candidate commit.
4. Run all local tests and visual checks; build all intended artifacts; smoke-test each real artifact in a fresh environment.
5. Commit the final code/docs, push the branch, wait for all required cloud gates, and verify the workflow `head_sha` matches the intended tag target.
6. Create a versioned release candidate tag (for example `v1.0.0-rc.1`) only after its tests pass. Publish as prerelease, download every asset, verify checksums and provenance, and test the downloaded packages—not the build-directory copies.
7. Gather any newly exposed problems, fix them locally, repeat all affected checks and regenerate every artifact from the fixed commit. Never edit an artifact manually after signing/checksumming it.
8. If the RC passes the complete release checklist with no blockers, merge according to repository policy and create `v1.0.0` pointing to the exact validated commit. Do not tag a dirty working tree.
9. Upload all assets, checksums, SBOM, third-party notices and build provenance; include installation/upgrade instructions, known limitations, CPU/Vulkan differences and verification commands.
10. Download the published stable assets again, verify hashes/attestations, install CPU Windows/Linux packages, launch, execute the demo workflow and export a result. Verify the Vulkan package on a compatible device and its fallback on a non-Vulkan machine.
11. Confirm GitHub release page, README links, tags, CI badges, social preview asset, screenshots, About description and topics. If a GitHub setting cannot be changed due to permissions, do not hide this; list its exact pending manual operation.
12. Update `docs/engineering/IMPLEMENTATION_STATUS.md`, `CHANGELOG.md`, `docs/engineering/AGENT_LOG.md`, validation reports and release records with verified facts. Do not update the final README with completion claims until the final release assets exist; then do one last README polish and re-run every affected check/cloud workflow before stable tagging. If this requires redoing the RC, do so.

### 15.5 Release block conditions

Do **not** release `v1.0.0` if any of these apply:

- required tests are failing, flaky or skipped unexpectedly;
- an advertised primary workflow does not complete from a clean install;
- a result silently suppresses unexpected errors or hides missing rows/outputs;
- the CPU-only package requires a GPU/Vulkan/Node/Python build environment;
- the Vulkan build is marketed as accelerated without a real tested compatible execution;
- distributables are missing, checksum mismatch, corrupt, untested, or require users to self-build;
- critical licensing/security issues or secrets remain unresolved;
- scientific marketing claims exceed the evidence;
- the tag, commit, SBOM, build provenance and binaries do not match;
- the final README has broken links, stale version numbers, badges or unsupported claims.

If a blocker fundamentally depends on credentials, signed certificates, physical hardware or permissions that are not available, still finish all safe work possible. Explain precisely what is blocked, how the blocker was verified, what artifact/check remains, and why it cannot honestly be called `v1.0.0 Stable`. Never release a fake stable build just to satisfy the goal.

---

## 16. Suggested repository outputs to add or maintain

Use the existing directory structure unless there is a clear reason to adjust it. At minimum, ensure the following files or equivalents exist and are accurate:

- `GEMINI.md` — this operating mandate, merged carefully with existing repo instructions.
- `docs/engineering/STABLE_V1_GAP_ANALYSIS.md` — evidence-backed baseline and action list.
- `docs/engineering/IMPLEMENTATION_STATUS.md` — honest status ledger.
- `docs/engineering/AGENT_LOG.md` — chronological actual work/log references.
- `docs/scientific-validation/VALIDATION_PROTOCOL.md` — current protocol plus per-engine result reports.
- `docs/scientific-validation/reports/` — reproducible, per-adapter validation evidence.
- `docs/developer-guide/TEST_MATRIX.md` — capability-to-test map.
- `docs/developer-guide/VISUAL_QA.md` — automated/manual visual and accessibility procedure.
- `docs/developer-guide/PACKAGING.md` — source, wheel, Windows and Linux build/test procedure.
- `docs/developer-guide/RELEASE_CHECKLIST.md` — gate-by-gate release checklist.
- `docs/security/THREAT_MODEL.md` and `SECURITY.md` — threat/security policy.
- `docs/assets/branding/` — original editable logos and social-preview source/output.
- `.github/workflows/` — deterministic required CI, per-OS packaging and release workflows.
- Updated `NOTICE`, `CITATION.cff`, `CHANGELOG.md`, `THIRD_PARTY_NOTICES.txt`, SBOM and release checksums where applicable.

Don't create empty docs just to satisfy this list. Every new file must contain useful content and link to the actual implementation or commands.

---

## 17. Web references to consult during implementation

Recheck these official or upstream sources because technical details and versions can change. Do not blindly trust a search snippet; read the relevant current documentation and record the version/date used.

### GitHub / release / discovery
- Repository customisation: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository
- Social preview image requirements/settings: https://docs.github.com/en/enterprise-cloud@latest/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview
- Repository topics: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics
- Artifact attestations and build provenance: https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations

### Scientific engines / data
- RDKit docs: https://www.rdkit.org/docs/
- AutoDock Vina docs: https://autodock-vina.readthedocs.io/en/latest/
- GNINA upstream: https://github.com/gnina/gnina
- OpenMM upstream: https://github.com/openmm/openmm
- OpenFE docs: https://docs.openfree.energy/en/latest/
- Chemprop upstream/docs: https://github.com/chemprop/chemprop
- PubChem PUG REST: https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest
- ChEMBL web services: https://chembl.gitbook.io/chembl-interface-documentation/web-services
- Open Targets platform/API: https://platform.opentargets.org/ and https://platform-docs.opentargets.org/
- llama.cpp: https://github.com/ggml-org/llama.cpp
- llama.cpp build guide and Vulkan option: https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md
- OECD QSAR assessment guidance: https://www.oecd.org/content/dam/oecd/en/publications/reports/2023/11/q-sar-assessment-framework-guidance-for-the-regulatory-assessment-of-quantitative-structure-activity-relationship-models-and-predictions_9b064821/d96118f6-en.pdf
- FAIR principles: https://www.go-fair.org/fair-principles/

### Packaging / quality / accessibility
- PyInstaller docs: https://pyinstaller.org/en/stable/
- PyInstaller contributed hooks: https://github.com/pyinstaller/pyinstaller-hooks-contrib
- AppImage: https://github.com/AppImage/AppImageKit
- Playwright config: https://playwright.dev/docs/api/class-testconfig
- Playwright visual comparisons: https://playwright.dev/docs/test-snapshots
- Playwright accessibility guidance: https://playwright.dev/docs/accessibility-testing
- WCAG 2.2: https://www.w3.org/TR/WCAG22/

Check current versions, available APIs and licence terms during execution; this link list is a starting point, not a substitute for investigation.

---

## 18. Final completion report — only after the work is actually done

Do not stop to send a final “done” message before the full sequence is complete. When all required work is finished, provide a concise but evidence-backed final report containing:

1. Stable release tag, release URL, exact commit SHA and cloud CI run URL.
2. Direct links to Windows CPU installer, Windows Vulkan installer, Linux CPU package and Linux Vulkan package (only assets that actually exist and passed smoke tests).
3. SHA-256 verification result, SBOM and build-attestation verification result.
4. Exact local and cloud gate summary: backend test count, coverage, frontend build/typecheck, E2E, visual/a11y QA, scientific validation reports, clean-install package tests, security/licence scans and OS matrix. State counts and failures truthfully.
5. Working scientific engines/data connectors, their actual tested versions, validation scope, and clear list of optional/not-configured/unsupported adapters.
6. CPU-vs-Vulkan behavior: what is genuinely accelerated, on what hardware, benchmark results and fallback behavior. Do not generalise beyond the tested hardware.
7. Important known limitations and anything requiring a manual action or unavailable credential/certificate/physical device.
8. README/SEO/branding status: committed logos, social preview asset, repository description/topics, working download links and screenshots. Explicitly state if the GitHub Settings social-preview upload still requires an owner action.
9. The most useful user-facing install command/instructions and how to report a bug.

The final report must be the last step. Only say “Stable v1.0.0 released” if the stable tag is published, the public release contains the verified intended artifacts, and the post-publication smoke tests pass. Otherwise report the exact status and blocker without dressing a candidate build up as stable.

**The north star:** HCS Discovery Studio should be a beautiful, local-first, scientifically transparent research workbench whose CPU mode is dependable on ordinary machines, whose Vulkan mode accelerates only what is genuinely supported, whose agent cannot fabricate work, whose results are reproducible and honestly limited, and whose stable release can be installed and used without a developer toolchain.
