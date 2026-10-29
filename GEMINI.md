# GEMINI.md — Autonomous Engineering Mandate for HCS Discovery Studio v2.0.0 Stable

**Project:** `timfromhcs/hcs-discovery-studio`  
**Target:** a genuinely stable, secure, reproducible, scientifically honest, accessible and correctly packaged `v2.0.0` release.  
**Operating mode:** autonomous, evidence-driven engineering. Inspect the actual checkout; establish a baseline; implement and verify locally first; run build, test, integration, visual QA, packaging and scientific validation loops; only then push to a dedicated GitHub branch; inspect cloud CI on the exact pushed commit; reproduce and repair every failure; repeat until all required gates pass. Reconcile documentation after the implementation is stable, rerun all relevant gates, and publish only when release criteria are satisfied.  
**Communication:** do not ask routine questions. Make safe, conventional engineering decisions from source code, tests and official references. Ask for human approval only where repository policy, permission, irreversible publication, or a genuine product decision requires it.

---

## 0. Mission and non-negotiable rules

You are the coding agent responsible for taking the repository from its **real current state** to the next verified Stable release. This document is a plan and an audit checklist, not proof that every described defect still exists. The repository changes quickly: confirm every claim against the current commit before changing code. A recent fix may already have landed; do not reapply stale changes.

### 0.1 Truthfulness and scientific integrity

1. Never claim that a test, build, runtime check, cloud job, benchmark, release or upload succeeded unless you observed its actual result and recorded the relevant command, commit and exit status.
2. Distinguish these states everywhere: **implemented**, **locally runnable**, **tested**, **reference-tested**, **benchmarked**, **scientifically validated**, **host-dependent**, **experimental**, **planned** and **unsupported**. Do not collapse them into one generic `available` state.
3. A clean test suite proves only the behaviors covered by those tests. A successful build does not prove runtime behavior; a runtime smoke test does not prove scientific validity; a green CodeQL run does not prove the entire system is secure.
4. Never use “state of the art”, “validated”, “accurate”, “production-ready”, “industry-grade”, “GPU-accelerated” or similar claims without specific evidence. Report task, method/model version, dataset source/license, split, baseline, metrics, sample count, uncertainty, hardware and limitations where applicable.
5. RDKit descriptors, similarity, Pareto/composite scores, ESOL, CNS MPO and docking outputs are computational signals. They do not prove binding, potency, selectivity, safety, toxicity, efficacy or clinical utility.
6. Do not silently convert invalid input, missing dependencies, exceptions, partial calculations or absent outputs into plausible-looking values or success statuses. Preserve row-level errors when the workflow contract permits; surface unexpected defects as failures.
7. A heuristic uncertainty value is not a calibrated confidence interval unless independent calibration evidence exists. CNS MPO is a desirability score, not a direct probability of BBB penetration. A reduced ESOL formula is not the full published model.
8. Never use a held-out benchmark set to tune thresholds or model parameters. If a set has already influenced development, label its results development-only and obtain a new independent test set for any generalization claim.
9. Do not use test fixtures as evidence of real-world performance. Clearly identify synthetic, illustrative and experimental datasets.
10. Device discovery alone is not proof of Vulkan/CUDA/GPU model support. Only report a backend as supported after an actual calculation on that backend and a comparison against a suitable reference.

### 0.2 Security and repository integrity

- Start with `git status` and preserve all existing user changes. Never overwrite or discard unrelated work.
- Never run destructive cleanup against the developer's real `data/`, user directories or any path that has not been proved disposable.
- Use separate temporary `HCS_DATA_DIR` directories for tests, migrations, integration tests, visual QA and packaging smoke tests.
- Never print secrets into logs, screenshots, issue reports, test fixtures or documentation. Never commit credentials, private structures, local machine paths or sensitive run data.
- Never force-push, rewrite public history, delete or move existing tags, bypass branch protection, disable a legitimate security test, or publish over an existing stable release to work around a failure.
- Do not weaken, delete, skip, `xfail`, quarantine or loosen a valid test merely to obtain a green result. Fix the underlying problem. If a test is truly invalid, document why and replace it with a stronger test in the same change.
- Do not add large scientific datasets, model weights or executable binaries without checking licensing, provenance, repository size, security and distribution consequences.
- Use a dedicated branch and PR where repository permissions and rules allow. A required review or human approval is not an obstacle to bypass.
- Use official, up-to-date documentation for scientific tools, GitHub Actions, dependency/runtime compatibility and package behavior. Do not rely on guessed command flags or unverified references.

### 0.3 Autonomous repair loops

Use the loop **Build → Test → Diagnose → Fix → Retest → Inspect diff → Record evidence** for each coherent work package.

- Every repeat must change the diagnosis, test setup or implementation. Re-running an unchanged failing command is not a repair strategy.
- For a single root cause, make up to five materially different fix attempts. After that, isolate the blocker, write a precise technical diagnosis, and continue independent work. Never claim that the release is complete while a mandatory blocker remains.
- Repair the earliest failing layer first: syntax/import → type/lint → unit test → integration → full backend/frontend suite → UI runtime/visual QA → package install → cloud CI → release verification.
- Keep an auditable log in `docs/engineering/AGENT_LOG.md` or the repository's existing equivalent. Record date, commit SHA, issue, hypothesis, command, environment, exit code, fix and test evidence. Keep logs concise and free of secrets.
- Work in small batches. Do not combine a scientific algorithm change, large UI rewrite and release-workflow rewrite in a single hard-to-review commit.
- If a check is blocked only because a tool or permission is unavailable, finish every independent task, record the exact missing capability and do not pretend the blocked check passed.

---

## 1. Establish ground truth before touching code

### 1.1 Repository and environment inspection

Run these commands first, from the repository root, and save the results in your working notes:

```bash
git status --short --branch
git rev-parse HEAD
git log -8 --oneline --decorate
git remote -v
git branch --show-current
git tag --list 'v*' --sort=-version:refname | head -20
```

On Windows PowerShell, replace `head` with `Select-Object -First 20` if needed. Confirm `origin` points to the intended public repository. Record uncommitted and untracked files before running formatters or generators. If the working tree is dirty, determine which changes belong to the user and preserve them. Do not reset the tree to make it clean.

Inspect the current versions of:

- `pyproject.toml`, `uv.lock`, `hatch_build.py`, Python package version and CLI/API version surfaces;
- `apps/web/package.json`, `apps/web/package-lock.json`, TypeScript/Vite/Playwright configuration;
- `README.md`, `CHANGELOG.md`, `GEMINI.md`, `SECURITY.md`, `NOTICE`, license and `CITATION.cff`;
- `docs/engineering/IMPLEMENTATION_STATUS.md`, historical gap analyses, scientific limitations, validation reports, architecture docs, install guides and release notes;
- `.github/workflows/ci.yml`, `codeql.yml`, `release.yml`, release/version scripts and repository settings if accessible;
- `src/hcs_discovery/`, `apps/web/src/`, `tests/`, `examples/`, `migrations/` and `scripts/`;
- current branches, PRs, tags, releases, Actions runs and release assets if GitHub access is available.

Record the current HEAD SHA, branch, package versions, actual published release state and initial CI state. Do not assume the previous Stable version, feature count or test count is still current.

### 1.2 Determine feature truth from implementation

For every important capability, trace the entire execution path:

1. Is a real implementation present?
2. Is it registered in the runtime registry?
3. Can the user configure it in the UI, CLI or API?
4. Does schema validation reject unsupported fields and malformed input?
5. Can the host detect all runtime dependencies reliably?
6. Does a successful real run create correct results and artifacts?
7. Are errors, cancellation, missing values and partial output reported honestly?
8. Is output provenance recorded, including relevant runtime versions?
9. Is there a regression test? Does it run in the required CI suite or skip conditionally?
10. Is there independent scientific reference evidence where the claim requires it?

Classify each feature separately as `implemented`, `runnable_here`, `smoke_tested`, `reference_tested`, `benchmarked`, `host_dependent`, `experimental`, `planned` or `unsupported`. Keep status names consistent across registry, API, CLI, UI, README and docs. A Vina adapter being registered does not mean Vina is installed on the host; Vina being installed does not mean a docking result has been scientifically validated.

### 1.3 Produce a baseline report

Before modifying code, record:

- current commit SHA and package versions;
- working-tree state and branch strategy;
- available Python, `uv`, Node and npm versions;
- whether Vina is installed and the actual `--version` output;
- the outputs of `hcs-discovery doctor` and the relevant diagnostics, with secrets removed;
- the result of the initial local quality gates;
- the current release/tag and associated workflow state;
- verified bugs, suspected bugs, stale documentation, environment limitations and priorities.

Do not stop at this report. Use it to drive implementation.

---

## 2. Branching, version strategy and release discipline

### 2.1 Preserve the Stable baseline

- Do not make direct, unreviewed edits to `main` if a branch/PR process is supported.
- After preserving local changes and confirming the correct upstream, use a dedicated branch such as `release/v2.0.0` or `fix/v2-stable`. Do not overwrite a branch owned by another workflow without inspecting it.
- Use small conventional commits such as `fix:`, `feat:`, `test:`, `docs:`, `build:` and `security:`.
- Do not tag a release candidate or Stable release until its exact source commit has passed the required local checks and is ready for cloud verification.
- Never change or delete the existing `v1.0.0` tag/release. Never reuse a tag for different source contents.

### 2.2 Version source of truth

Inspect the version verifier and real repository conventions before changing versions. Keep the following in sync as appropriate:

- Python project version;
- frontend package version if it is intended to mirror the application version;
- CLI/API version output;
- changelog heading;
- release-note filename and heading;
- Git tag and GitHub release title;
- wheel filename and installed version;
- README status badge and implementation status.

Do not guess the mapping between a tag such as `v2.0.0-rc.1` and a PEP 440 version. Confirm the behavior in the actual verification script and test it. Use a release-candidate cycle before Stable if the release workflow supports it. The Stable tag must point to the exact commit whose full CI gates passed.

### 2.3 Permission and approval policy

Use the available GitHub CLI or connector to push a dedicated branch and create/update a PR if authorized. Follow the repository's branch protection and required review policy. If push, merge, tagging or publication is blocked by permissions, complete all local work and prepare the branch/PR; report the precise required owner action. Do not bypass policy or claim a remote change succeeded unless the host confirms it.

---

## 3. Local-first development environment

**Hard order:** baseline → implement locally → local targeted tests → local full gates → local visual/runtime QA → local package smoke test → inspect diff → commit → push → cloud CI loop. Never push knowingly broken code merely to use cloud CI as a debugging environment.

### 3.1 Isolate every test environment

- Default automated tests must be deterministic and offline.
- Network tests must be separately marked and run only when explicitly intended.
- Set `HCS_DATA_DIR` to a unique disposable directory for migration tests, API integration tests, E2E tests and wheel smoke tests.
- Do not run migration or deletion tests against the normal user data directory.
- Every test-started process must be stopped at the end, even after failure.
- Verify the temporary directory path before removing it. Do not use broad wildcard cleanup.

### 3.2 Baseline Python and frontend commands

Use the actual installed versions and adapt only when repository scripts have intentionally changed. Update this file and CI together when command names change.

```bash
uv --version
uv lock --check
uv sync --frozen
uv run hcs-discovery version
uv run hcs-discovery doctor
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest -q --strict-markers
uv run pytest -q --strict-markers --cov=hcs_discovery --cov-branch --cov-report=term-missing --cov-report=xml --cov-fail-under=70
```

Do not run two competing pytest invocations against the same data directory. If the coverage floor changes, justify it and keep the CI floor aligned. Do not reduce the floor to hide missing coverage.

Frontend, from `apps/web/`:

```bash
node --version
npm --version
npm ci
npm run typecheck
npm run build
npm run test:e2e
```

Build `dist` before packaging. Do not use `npm install` to mutate the lockfile incidentally; if a lockfile update is required, make it an explicit, reviewed change and validate `npm ci` from a clean checkout.

### 3.3 Whole-journey and packaging baseline

Using isolated test data and the actual current CLI syntax, prove the following lifecycle:

1. Start with an empty disposable data directory.
2. Run the database upgrade and verify `db current` identifies the correct revision.
3. Run diagnostics and verify the server reports readiness.
4. Create a project.
5. Import a small documented fixture CSV/SDF/SMILES file and inspect row-level successes and errors.
6. Create or load a supported workflow, validate it, save it and execute it.
7. Inspect progress, events, logs, cancellation/failure behavior and terminal status.
8. Inspect result rows and columns, then export CSV/JSON/Markdown/HTML as supported.
9. Verify the manifest, input checksums, workflow snapshot, engine versions and artifact checksums.
10. Repeat the run and verify cache semantics are correct.
11. Delete a disposable project/dataset and verify database and filesystem retention/deletion policy.
12. Stop all processes and confirm no unintended files changed outside the isolated data directory.

Use current CLI command help rather than relying on stale command examples. Package tests:

```bash
uv build --wheel
```

Install the wheel into a **new clean virtual environment** that is not the source development environment. With a fresh disposable `HCS_DATA_DIR`, verify version, diagnostics, database upgrade, `/api/v1/health`, `/api/v1/ready`, and that `/` serves the built SPA rather than a development placeholder. Record wheel SHA-256 and installed package version. Repeat on Windows if Windows is an officially supported release platform.

---

## 4. Mandatory Build → Test → Diagnose → Fix loops

Every change must use this process. Do not batch up unverified edits and hope the final build passes.

### Loop A — Reproduce

1. State the failing behavior in one sentence.
2. Find the smallest deterministic reproducer.
3. Create a regression test that fails against the current code for the expected reason, where feasible.
4. Inspect adjacent callers/contracts and the latest source history to prevent duplicate fixes.
5. Separate code defects from test configuration, OS differences, dependency changes and environmental issues.

### Loop B — Fix

1. Implement the smallest correct fix consistent with architecture and public API contracts.
2. Validate inputs at the boundary, not after unsafe side effects have already begun.
3. Preserve meaningful error messages and stable error codes.
4. Add regression coverage for both the reported defect and relevant edge cases.
5. Do not replace explicit validation with broad exception suppression.

### Loop C — Focused verification

Run the directly affected unit tests, then adjacent integration tests, type/lint checks and the narrowest relevant runtime test. Inspect the full diff. Confirm the test would fail if the new fix were reverted, or otherwise explain how the test protects the invariant.

### Loop D — Regression suite

After each coherent work package, rerun all relevant tests. At each phase boundary, run the complete local gates from Section 12. When shared contracts change, retest all entry points: UI, CLI, HTTP API, imported workflow and agent tool payloads.

### Loop E — Self-healing repair protocol

For any failed command:

1. Save the command, return code, relevant log and exact commit.
2. Identify the earliest failing layer and root-cause hypothesis.
3. Change code or test setup only after a concrete diagnosis.
4. Re-run the focused test.
5. Re-run adjacent integration tests.
6. Re-run the full relevant gate.
7. Inspect changed/untracked files and ensure no generated secrets, real data or unintended lockfile changes were added.
8. Record the successful result or the precise remaining blocker.

Never disable a required test to get green. A skipped optional Vina live test is not evidence of a successful live Vina calculation. A missing visual QA pass is not replaced by a successful TypeScript build.

---

## 5. Priority P0 — Scientific correctness and cache provenance

Resolve these before spending time on new feature work. Treat each finding as an audit lead that must be confirmed against the checkout.

### 5.1 AutoDock Vina ligand preparation and output validity

Audit `src/hcs_discovery/plugins/science/docking/prep.py`, `src/hcs_discovery/plugins/science/docking/vina.py`, its registration and `tests/scientific/test_vina_adapter.py`.

The custom `prepare_ligand_pdbqt()` path must not be assumed correct simply because it emits a file containing `ROOT`, atom records and `TORSDOF`. Confirm the PDBQT torsion-tree representation required by the exact supported Vina version. Compare the output against official documentation and a suitable established preparation tool such as Meeko. Check license and packaging requirements before adding or bundling another tool.

Required audit and tests:

- Correct handling of stereochemistry, aromatic atoms, formal charges, protonation states, tautomerism, salts/multiple fragments and unusual elements.
- Correct, reference-checked atom typing and partial charges.
- A valid representation of flexible bonds/torsion branches, not just a torsion count.
- Correct receptor preparation assumptions: polar hydrogens, atom types, coordinates, receptor integrity and box configuration.
- Consistent and traceable handling of fragment selection. Never silently drop important components; record the transformation and warnings.
- Real Vina process return-code checks, recognized version output, executable discovery on Windows/Linux, timeout, cancellation and malformed/missing output handling.
- Per-ligand status is preserved: preparation failure, engine failure, no pose and successful docking must never be conflated.
- PDBQT and SDF pose artifacts are parseable, traceable to the compound and linked in the manifest.
- A known-good reference complex is redocked with a legally usable, reproducibly sourced fixture. Document PDB/source/version, preparation method, coordinates and box, seed, Vina version, settings, RMSD definition, acceptance threshold and observed results. Do not invent a threshold or claim pose recovery without executing the test.
- Default CI stays offline and deterministic. If the real Vina executable or a licensed/reference fixture is unavailable in a normal runner, use a separately required scientific release gate or a manually/scheduled workflow with recorded evidence; do not mark a skipped test as passed.

A Vina binary passing `--version` proves that the executable is discoverable and runs. It does not validate ligand preparation or docking science. Report these states separately.

### 5.2 Scientific runtime versions must invalidate cached results

Audit `src/hcs_discovery/workflow/cache.py`, `src/hcs_discovery/workflow/registry.py`, `src/hcs_discovery/workflow/executor.py`, all scientific adapters and model metadata.

Current design uses a node implementation hash, node version, config, input table hash, engine-version dictionary and schema version. Verify that the effective hash changes for **every relevant factor** that can affect output. A handler-only source hash may miss helper functions called transitively. Static adapter version strings may not equal the actual external engine installed on a host.

Requirements:

- Include relevant runtime engine versions in the execution context and cache key: at minimum the actual detected Vina version for docking, RDKit version for chemistry, effective property-model version/coefficients and other dependencies that influence results.
- Include model weights/coefficients and meaningful preprocessing/method versions in model fingerprints.
- Include stochastic seeds and every output-relevant parameter.
- Ensure edits to helper code cannot reuse a previous scientific output. Use a deliberate application/build/source revision fingerprint or a dependency-aware implementation fingerprint; document the trade-off and test it.
- Do not include irrelevant host-specific values that reduce cache reuse unless they can change scientific results. Record hardware separately where it is provenance-relevant.
- Verify artifact hashes when reading cache entries and fail closed on missing, altered or incomplete entries.
- Cache restoration must be atomic or recoverable; a failed restore should produce a real cache miss without partial files being accepted as successful output.
- Add regression tests that modify each relevant version/fingerprint/input/config dimension and assert the key changes. Test stable inputs produce a cache hit only when all relevant identities match.

### 5.3 Ranking, workflow schemas and scientific semantics

Audit `src/hcs_discovery/workflow/nodes.py`, `schema.py`, `table.py` and tests.

- Validate numeric fields for finite values and clear missing-value semantics. NaN/Infinity must not silently pass through scoring, JSON output or reports.
- Keep objectives and hard constraints semantically separate. Constraints gate eligibility; they must not distort Pareto fronts or composite scores through accidental weighting.
- Test `higher`/`lower` versus `maximize`/`minimize` aliases, `target_range`, `constraint`, informational-only objectives, zero weights, equal values, absent values and target boundaries.
- Use standard non-dominated sorting with permutation-invariance and tie tests. Every front must satisfy the documented dominance invariants.
- Composite scores based on min-max normalization are dataset-relative. Label and report that limitation; do not compare scores across different datasets without a documented normalization strategy.
- Test joins by explicit identity keys, not physical row order. Specify and test duplicate keys, missing keys, join cardinality and conflict resolution. Do not silently duplicate or discard compounds.
- Validate the whole workflow graph before queueing: unknown node types, cycles, invalid references, incompatible output columns, unknown config keys, invalid edges, unsupported graph shapes and resource limits.
- Keep UI, CLI, API and agent validation on the same service/schema logic.

### 5.4 Chemistry parsing and standardisation

Audit imports, standardization, descriptors, depictions and exports.

- Preserve raw input, standardized structure, transformation options, failure reason and source provenance.
- Test invalid SMILES/SDF, explicit/implicit hydrogens, stereochemistry, salts, multi-component structures, tautomers, charged species, unusual valences and uncommon elements.
- Expected molecule-level chemistry errors may become explicit row-level failures. Unexpected implementation errors must be surfaced and tested rather than hidden behind `except Exception`.
- Verify SVG depiction safety and the correctness of filenames/media types for exports.
- Make duplicate policy explicit: raw duplicate rows, canonical structures, stereoisomers and source identifiers are not interchangeable concepts.
- Avoid promising unique-compound identity unless the exact identity method and normalization are documented.

---

## 6. Priority P1 — Property models and connectors

### 6.1 ESOL validation

Audit `src/hcs_discovery/plugins/science/properties/models.py`, `validation.py`, `scripts/science/validate_esol.py`, the challenge fixture and validation report.

- Keep the model description precise: if the code implements a reduced four-descriptor equation, do not label it as the full published ESOL model.
- Make the challenge fixture, provenance, DOI/license, checksum, inclusion/exclusion criteria and metrics reproducible from a clean checkout.
- Keep the held-out challenge set frozen. If development has used it to choose coefficients or thresholds, label the reported result development-only and obtain a distinct independent set for any final generalization claim.
- Compare RMSE, MAE, R², bias and baseline results. Report sample size and all exclusions; do not select only favorable metrics.
- The current repository's recorded challenge result is weak (small improvement over a constant baseline, low R²). Keep this result visible. Do not remove or obscure it to make the product look better.
- Treat distance-based uncertainty as a heuristic unless calibration and coverage tests demonstrate more.
- Verify unit, label and endpoint semantics: logS/log10(mol/L) is not the same as a generic solubility measure in any unit.
- Add boundary and out-of-domain tests for molecular weight, heavy atoms, element set, invalid structures and charged molecules.

### 6.2 CNS MPO

Audit the CNS MPO formula and metadata against the cited original method and an authoritative implementation.

- Distinguish the published six-parameter desirability score from any approximation.
- Inspect approximations for CLogD and pKa: a fixed offset from cLogP or a simple count of nitrogen atoms must not be presented as the exact measured/calculated property without evidence.
- If the complete supported method cannot be implemented robustly, rename/label the output as an approximation or CNS-MPO-inspired heuristic and document the exact deviations.
- Do not describe a score above a threshold as a probability of BBB penetration, clinical activity or brain exposure.
- Do not call a fixed numeric field calibrated uncertainty without calibration evidence.
- Add test vectors that compare function outputs to published/authoritative reference values and test each desirability boundary.

### 6.3 PubChem and ChEMBL connectors

Audit `src/hcs_discovery/plugins/connectors/` and the network policy.

- Local/offline must be the default; external calls require explicit policy opt-in.
- Test DNS/host allowlists, redirects, hostname normalization, request size, response size, timeout, rate limiting, retries, 404, 429, 5xx, malformed JSON, invalid content types and partial provider responses.
- Re-check target hostname and policy on every redirect. Do not allow a URL redirect to bypass host policy or reach local/private metadata services.
- Validate returned identifier/structure relationships and retain source identity, URL, retrieval timestamp, license/attribution, raw or normalized payload hash and cache status.
- Cached results must be distinguishable from current provider results.
- Use deterministic mocked transports in ordinary CI. Live network smoke tests must be opt-in/scheduled and cannot make the default offline suite flaky.

### 6.4 Optional models, LLM and backend claims

- Do not add a model or engine only to increase the number of feature cards.
- An adapter needs a documented task, supported inputs/outputs, license/weights review, resource profile, host capability probe, error paths and suitable acceptance tests.
- Local LLM support must state whether a provider is local or remote, and must not send private structures/secrets to an LLM unexpectedly.
- Vulkan device detection is not proof that scientific inference runs through Vulkan. Do not claim Vulkan acceleration unless a named runtime actually uses that backend, a real inference has succeeded and output/performance have been measured.
- Keep the dependable CPU path working on explicitly supported Windows/Linux environments without CUDA, Docker, cloud credentials or an implicit weight download.

---

## 7. Priority P1 — API, CLI, agent and operational safety

### 7.1 Shared service contracts

- Keep domain/business logic in shared service functions, not duplicated across React, HTTP routes, CLI and agent execution.
- Check status codes and CLI exit codes for validation errors, missing resources, network policy blocks, cancellation, timeout and internal failures.
- Ensure every documented UI action has the expected API/CLI behavior only if parity is explicitly promised. If an action cannot be exposed headlessly, document that limitation rather than faking parity.
- Validate pagination and bounds. Do not return unbounded huge data unnecessarily.
- Preserve `/api/v1` compatibility unless a documented breaking change is intended.

### 7.2 Research Agent safety

Treat the research assistant as a controlled interface to existing scientific functionality, not an autonomous scientific authority.

- Ask mode must be read-only; Plan mode must not create persistent objects or queue work; Run mode must use a concrete validated plan and the allowlisted server tool registry.
- Validate all LLM output against strict typed schemas; reject extra fields, unsupported tool names, out-of-range arguments and semantically invalid workflow configurations.
- Bind approval to the actual immutable plan digest and current plan contents. Modifying any step after approval must invalidate the approval.
- Do not let imported compound names, SDF/CSV text, external web content, logs or model output grant permissions or override system policy. Add prompt-injection tests.
- Return structured validation issues and unsupported assumptions. Do not convert a planning error into `valid=true` or silently choose an unrelated engine.
- Test no provider, unreachable provider, malformed response, timeouts, blocked remote policy, invalid plan, approval mismatch, tool error, cancellation and partial execution.
- Never pass secrets to the LLM. Keep remote provider usage explicit and policy-gated.
- Bound molecule counts, job duration, retries and resource consumption. Explain limits before expensive work where practical.

### 7.3 Filesystem, paths, uploads and data lifecycle

- Audit all user-supplied filenames, receptor paths, artifact paths, plan IDs, uploads, deletion and export routes.
- Prevent traversal, symlink escape, sibling-prefix confusion, Windows reserved names and writing/reading outside the configured data root unless a documented local operator explicitly configures access.
- For HTTP-accessible workflows, do not allow an untrusted client to read arbitrary host files by setting an absolute receptor path. Use workspace/project confinement or an explicit trusted-local configuration.
- Keep destructive operations confirmed and scoped. If deletion removes files, offer preview/dry-run where useful and report precisely what was deleted.
- Decide and document whether failed/cancelled runs leave artifacts. Ensure database and filesystem state remain consistent after crashes.
- Test project/dataset deletion, cache pruning, orphan cleanup, concurrent writes and worker restart with isolated data.

---

## 8. Priority P1 — CI, dependency and release-workflow integrity

Inspect `.github/workflows/ci.yml`, `codeql.yml`, `release.yml`, version verification and repository rules.

### 8.1 Required CI gates

Keep or strengthen these checks:

- Python lockfile consistency and frozen dependency install;
- Ruff formatting and linting;
- mypy/type checks;
- backend tests with coverage floor;
- frontend typecheck and production build;
- Playwright E2E tests;
- clean DB migration and DB revision verification;
- wheel build, clean-environment install and runtime/UI smoke test;
- license policy and dependency vulnerability audit;
- documentation relative-link check;
- secret scanning and CodeQL;
- dependency review on PRs;
- a single aggregate job that fails if any mandatory job fails or is missing.

Use the current lockfile, pinned major versions and action SHAs as the source of truth. Do not weaken permissions or use `continue-on-error` for mandatory gates.

### 8.2 Tag and cloud-gate race prevention

A key release risk is that the normal CI workflow may run on branches/PRs while the separate release workflow is triggered by a tag. The release workflow must not publish an insufficiently tested tagged commit merely because its own smaller subset passes.

Implement a reliable policy that proves the exact tagged commit passed all mandatory release gates. Depending on current repository capabilities, use a reusable required gate workflow, a versioned release-candidate branch/PR, or explicit verification of completed successful checks for that exact SHA. Do not implement a brittle sleep or a check that merely sees a green run for a different SHA.

Required invariants:

1. Every release artifact is built from the immutable tagged commit.
2. The exact commit has all mandatory checks completed successfully before publication.
3. A failed, cancelled, skipped mandatory gate blocks release publication.
4. A release tag is not moved or reused to publish a different source.
5. Publishing and asset replacement cannot silently overwrite an existing Stable release.
6. Only the release job gets the write permissions required to publish and attest assets; test/PR jobs remain read-only.
7. Concurrency prevents competing publication jobs for the same tag, without cancelling a publication halfway through.

### 8.3 Dependency and license integrity

- Run audit tools on locked production dependencies and production npm dependencies.
- Review advisories and package licenses in context; do not simply suppress high/critical findings.
- Preserve third-party notices and license attribution.
- Avoid unpinned/unreviewed downloads in build/test scripts.
- Verify that the wheel's contents match the intended Python modules, built SPA and Alembic migration scripts.

---

## 9. User experience, accessibility and visual QA

**Visual QA is mandatory.** A frontend build, static typecheck or saved screenshot alone is not visual QA.

### 9.1 Test the actual app

Start the real backend with a disposable data directory and the built or dev SPA on loopback. Use Playwright or the installed equivalent against the running application. Do not use generated mockups, placeholder data or a static screenshot as proof of functionality.

Review the real critical journeys:

1. Workspace loads with empty and populated states.
2. Project create, open, edit and deletion confirmation.
3. Dataset import, column mapping, invalid rows and completion summary.
4. Compound library, details and SVG depiction.
5. Workflow template, node configuration, validation, save and reload.
6. Run queue, monitor, live events, node errors, cancellation and retry behavior.
7. Results table, Pareto plot, column meanings, filters/sorts and complete data export.
8. Model registry with available, unavailable, not configured and planned states.
9. Data connectors in offline mode and explicit policy-block states.
10. Agent Ask/Plan/Run when these are part of the release contract.
11. Settings, diagnostics, not-found routes and API/server failure states.

### 9.2 Required viewport/theme matrix

Test at a minimum of 320, 390, 768, 1280, 1440 pixels (or the closest reproducible browser widths) and in both Light and Dark themes. Include keyboard-only navigation and focus states. Test at 200% zoom where feasible.

Check:

- horizontal overflow and clipped dialogs/tables;
- empty, loading, partial, success, warning and error states;
- readable table columns, units and long compound identifiers;
- graph/chart legibility and responsive behavior;
- visible focus indicator, labels, semantic heading order and button names;
- contrast and theme-specific contrast regressions;
- non-blocking progress states with no fake completion;
- clear indication when a model or external engine is not locally runnable;
- destructive confirmations and actionable recovery instructions.

### 9.3 Visual QA loop

For every important visual defect:

1. Capture a screenshot from the real running app and record route, viewport, theme and fixture.
2. Inspect the image, not just the screenshot path or console output.
3. Identify the component/CSS cause.
4. Fix the underlying layout/state/accessibility problem.
5. Re-capture the same screenshot and compare it visually.
6. Run related E2E tests and scan browser console/page errors.
7. Re-run the relevant responsive/theme matrix after changing shared layout or tokens.

Use synthetic fixture data only. Do not commit screenshots with private structures, real user data, tokens, secrets or machine-specific paths. Commit screenshots only when they are intentional project documentation and verified current.

---

## 10. Performance, resilience and data-size behavior

Before claiming performance improvements, measure a baseline and retain the measurement command, hardware, software versions, dataset size and result. Do not invent speedups or select only favorable outcomes.

Use representative fixtures appropriate to the current product: small import, several hundred compounds, and a larger local workflow dataset within reasonable CI constraints. Heavy scientific benchmarks may be separately scheduled/manual, but Stable release claims must link to their actual results.

Test at least:

- import limits, malformed files and oversized payload rejection;
- worker process crash during a node;
- lease heartbeat failure, expired lease, duplicate claim and restart recovery;
- cancellation before, during and after an expensive step;
- timeout and retry semantics;
- repeated runs with cache hit and forced invalidation;
- partial artifact writes and corrupted cache manifests;
- database contention and concurrent API/worker access;
- SSE client disconnect/reconnect and non-blocking async behavior;
- large report/table export, explicit truncation disclosure and full CSV/JSON export;
- bounded cache pruning, dry-run/status if supported, and safe cleanup during concurrent use;
- project/dataset deletion with active or completed runs.

SQLite is a single-machine database with serialized writes. Do not advertise distributed multi-worker or high-concurrency scaling without a separately tested architecture. Do not add PostgreSQL/Redis/container infrastructure to this Stable scope unless it is required by the current documented contract; make the local CPU path reliable first.

---

## 11. Test construction standards

A test must prove behavior, not just execution. Prefer deterministic assertions on invariant, state transition, returned schema, error code, output provenance and side effects.

### 11.1 Unit tests

Use isolated inputs and test success, failure, boundaries, missing fields, invalid values, unexpected exceptions and exact status mapping. Avoid asserting incidental implementation details unless they protect a public contract.

### 11.2 Property-based tests

Use Hypothesis where it provides value. Good targets include ranking invariants, graph validation, table operations, serialization, cache fingerprints, path confinement and standardization invariants. Retain explicit small counterexamples for previously discovered bugs.

### 11.3 Integration tests

Test real internal components connected together: service + DB, queue + worker, workflow + artifact store, API + service layer, CLI + service layer, migration + existing database, cache + executor. Use temporary directories and a known explicit DB path.

### 11.4 Scientific tests

Separate these test levels:

- formula/unit tests;
- deterministic fixture tests;
- comparison with an authoritative/reference implementation;
- real-engine integration tests;
- independent dataset validation/benchmark;
- experimental validation (only if actual experimental data/protocol exists).

Do not call one level by the name of a stronger level. For scientific datasets, record provenance, license, checksum, transformations, exclusions and the exact reproduction command.

### 11.5 API/CLI contract tests

For each key action, verify UI/API/CLI call the same business service or produce equivalent outcomes. Test invalid config, missing ID, policy block, timeout, cancellation and machine-readable `--json` output.

### 11.6 E2E tests

At minimum, cover happy path and major failure paths. Do not let E2E runs reuse a hidden stale database. Ensure their setup happens before the server begins with the E2E `HCS_DATA_DIR`, following the actual Playwright config. Confirm teardown never deletes user data.

---

## 12. Mandatory complete local gates before any push

Do not push code that has known local failures. Run the correct subset after every work package and the full gate before the first push and before creating a candidate/release tag.

### 12.1 Clean and inspect

```bash
git diff --check
git status --short
```

Inspect the complete staged and unstaged diff. Check that there are no secrets, unintended generated artifacts, real data, unrelated changes, debug statements, stale screenshots or accidental lockfile churn. Run format check, lint, type check and lockfile check.

### 12.2 Backend and migrations

Run the full backend test suite with coverage using the isolated test environment. Run migration tests against both an empty DB and a copy of the prior supported schema. Verify the correct Alembic revision is recorded; do not accept `create_all` success as proof that migrations are working.

### 12.3 Frontend and actual runtime

Run frontend install from lockfile, typecheck, production build and E2E tests. Start the actual built app with isolated data and test health, readiness, root SPA, core journey and error states. Inspect console errors and visual output.

### 12.4 Scientific gates

Run deterministic science tests. Run the Vina reference/redocking gate and any independent property-model benchmark required by the Stable criteria. If these tests are separated from default CI due cost or dependency/license requirements, run them explicitly before publication and attach their actual evidence to the release notes or CI summary. A skipped optional test does not pass a required gate.

### 12.5 Package and fresh install

Build the wheel only after a fresh frontend build. Install it into a new virtual environment. Verify CLI version/doctor, clean database migration, HTTP readiness and the served SPA. Inspect wheel contents for web assets and Alembic scripts. Repeat on each claimed supported OS.

### 12.6 Local release verdict

The first push is allowed only when all locally runnable mandatory gates pass. If a required check cannot run locally due to platform/hardware, record the reason and ensure it has an explicit, required cloud/release gate. A green lint/build combination is never a substitute for missing science, E2E or install verification.

---

## 13. GitHub push and Cloud CI repair loop

**Do not push until Section 12's local gate passes.** After pushing, continue this loop until every required cloud job for the exact final source commit is green.

### 13.1 Pre-push checklist

1. Confirm current branch is the intended release/fix branch, not `main` unless repository policy explicitly requires direct work.
2. Confirm working tree and diff are understood; stage only intended files.
3. Run relevant tests after the final code change.
4. Commit with a concise, truthful message.
5. Record the commit SHA.
6. Push the branch and verify the remote points to the same SHA.
7. Create/update the PR if supported and verify required checks are attached to the expected branch/commit.

Example commands; adapt to actual repo state and permissions:

```bash
git status --short --branch
git diff --check
git diff --stat
git diff --cached
git push -u origin "$(git branch --show-current)"
git rev-parse HEAD
git ls-remote origin "refs/heads/$(git branch --show-current)"
```

Never assume push succeeded because the command appeared to start. Check its exit status and remote SHA.

### 13.2 Cloud polling and diagnosis

Use `gh run list`, `gh run view`, `gh run watch` or the available GitHub integration. Inspect real run IDs and the commit SHA; do not infer current status from a badge, a previous branch run or an earlier commit.

Useful CLI examples:

```bash
gh run list --branch "$(git branch --show-current)" --limit 20
gh run view <RUN_ID> --json name,status,conclusion,headSha,event,workflowName,url
gh run view <RUN_ID> --log-failed
```

Confirm the exact schema supported by the installed GitHub CLI version before use. If `gh` is unavailable, use the authorized GitHub UI/API connector. Never invent results for unavailable tools.

For each failed job:

1. Open the job summary and failed logs.
2. Identify the first meaningful failure, not only the final aggregate failure.
3. Decide whether it is code, platform, dependency resolution, lockfile, path/case sensitivity, newline, environment, test isolation, browser install, packaging, license, network or workflow orchestration.
4. Reproduce it locally or in a matching container/OS when practical.
5. Implement a real fix and add a regression test or workflow invariant.
6. Run focused tests, then the affected full local gate.
7. Review the diff and commit the fix.
8. Push again and inspect the new cloud runs on the new SHA.
9. Repeat until all mandatory jobs on the final commit are green.

Do not fix a Windows-specific failure only by skipping the Windows job. Do not fix a license issue by disabling the license gate. Do not fix a flaky E2E test by removing assertions on the behavior under test. Correct race conditions and hidden shared state.

### 13.3 Cloud loop stop conditions

The cloud loop is complete only if:

- all mandatory CI jobs on the exact candidate SHA concluded `success`;
- no required job was skipped, cancelled or silently allowed to fail;
- CodeQL and secret/dependency/security checks are green;
- E2E, migration, packaging, docs and scientific release gates have the required evidence;
- PR status and approvals satisfy the repo's rules;
- the remote branch/tag SHA is exactly the intended commit.

If a human approval, owner-only permission or an unavailable external service blocks an action, do not bypass it. Finish all safe independent work and report the blocker by exact workflow, job, PR or permission. Do not call the release complete.

---

## 14. Documentation and repository hygiene — after implementation stabilizes

Do a final, systematic documentation reconciliation once the code/behavior has stabilized. Fix factual documentation defects earlier if they would mislead development decisions, but avoid rewriting all prose after every code commit.

### 14.1 One consistent feature ledger

Use one authoritative status table and ensure these pages tell the same truth:

- `README.md`;
- `docs/engineering/IMPLEMENTATION_STATUS.md`;
- `docs/user-guide/SCIENTIFIC_LIMITATIONS.md`;
- model/adapter registry text and API status;
- architecture/workflow docs;
- install guides and troubleshooting;
- changelog and release notes;
- repository version/status badges.

Specific audit leads to resolve:

- Some historical documentation has described AutoDock Vina, property prediction and data connectors as both available and unimplemented. Reconcile every statement against actual implementation, host probing and evidence.
- The documentation for linear workflows may be stale now that the engine registers joins/DAG behavior. Verify actual supported branching/fan-in semantics before updating claims.
- `IMPLEMENTATION_STATUS.md` and earlier gap-analysis documents may conflict on whether v1/v2 are Stable, candidate or pending. Add dates and historical labels; do not present old plans as current release facts.
- Model metadata may contain measured, heuristic and literature-derived results. Label these distinctly and show current evidence for each.
- Package metadata, development-status classifier, Python support badge, current release state and feature claims must agree.
- Do not inflate test counts based on prior commits. Regenerate counts and claims from actual current command outputs.

### 14.2 README quality

The README should let a new user answer quickly and accurately:

1. What the software does and does not do.
2. Which features are genuinely runnable and the requirements for each.
3. How to install from source and from the released wheel.
4. How to run one end-to-end example, including expected output and failure handling.
5. Which operating systems/Python versions are actually supported and tested.
6. How to verify artefact checksums/provenance.
7. What the security model and network policy are.
8. What the scientific caveats and unsupported research claims are.
9. How to report security issues, bugs and scientific errors.
10. How to cite and license the project.

Use genuine, current screenshots from the working application. Never use mockups as evidence of functionality. Make sure images, logo paths, internal links, release links and badges actually resolve.

### 14.3 Versioned scientific reports

For each scientific report, include method/model version, input fixture hash, dataset source and license, exclusions, exact command, code commit, relevant runtime versions, metrics, baseline, sample size and caveats. Do not overwrite historical results without recording why they changed. Do not imply tests were run after the displayed report's commit if they were not.

### 14.4 GitHub metadata, SEO and open-source hygiene

- Verify repository description, topics, license, citations and social preview image reflect the actual product.
- Use accurate, useful headings and searchable terms without keyword spam.
- Check README image alt text and link accessibility.
- Verify contribution, code of conduct, security reporting and issue templates.
- Keep branding credit accurate; do not invent user counts, adoption claims, performance claims or external endorsements.
- Verify links and assets with the current documentation-link checker and, where appropriate, a manual browser check.

---

## 15. Version-candidate and Stable release procedure

### 15.1 Release-candidate stage

1. Finish implementation and the documentation reconciliation.
2. Update package/app versions only according to the real version-verification script.
3. Run the full local gates from Section 12 on a clean working tree.
4. Commit and push the candidate branch.
5. Observe cloud CI and scientific release gates on the exact candidate SHA until green.
6. If a failure appears, return to the local fix loop. Never tag Stable to make the workflow try again.
7. Verify the candidate wheel in a fresh environment and inspect its contents.
8. Run the version verifier and validate release notes before publishing a candidate, if candidate releases are part of the chosen workflow.

### 15.2 Stable tag stage

Only after the candidate is fully verified:

1. Choose the final exact source commit and confirm it contains all approved fixes/docs.
2. Re-run all mandatory local gates if any file changed after the last pass.
3. Re-run cloud required gates for that exact commit.
4. Ensure there is no uncommitted or unreviewed state that changes the artifact.
5. Create/push the Stable tag only after the full exact-SHA gate is green and required approvals exist.
6. Verify that the release workflow checks the tag, package version, changelog and release notes before packaging.
7. Do not reuse an existing tag or overwrite an existing Stable release.

### 15.3 Artifact publication and verification

The release workflow should build the wheel from the tagged source, generate the SBOM from the real package environment, produce SHA-256 checksums and build-provenance attestation, and then publish the assets.

After publishing:

- open the real GitHub Release and verify the tag/SHA;
- list and download the wheel, SBOM and checksum file;
- compute SHA-256 of downloaded assets and compare with the published checksums;
- verify the GitHub build-provenance attestation using the official supported command;
- install the downloaded wheel into a clean environment and run version, diagnostics, migration, API health/readiness and SPA smoke checks;
- verify the installed version equals the release version;
- inspect release notes for unsupported or misleading claims.

Report a release as published only when the host confirms it exists and the published assets have been verified. If permissions prevent tag or release publication, report the exact required human action and do not claim success.

---

## 16. Full final acceptance checklist

Do not mark `v2.0.0 Stable` as done until all applicable boxes are supported by evidence in the final report.

### Repository and implementation

- [ ] Initial Git state preserved; no unrelated user edits lost.
- [ ] All intended work is committed on the appropriate branch.
- [ ] No secrets, private data, temporary logs, unrelated binaries or unintended generated files are committed.
- [ ] CLI, API and UI agree on supported status and error contracts.
- [ ] All advertised runnable capabilities have a real implementation and required runtime checks.
- [ ] `table.join`/DAG semantics are fully validated if advertised.

### Scientific correctness and provenance

- [ ] Vina input preparation conforms to the selected format/tool and has an executed reference validation.
- [ ] A scientific release gate demonstrates actual Vina execution and a documented redocking/reference result.
- [ ] External engine/model versions, coefficients/weights and relevant helper implementation changes invalidate cache correctly.
- [ ] Pareto/ranking constraints, missing values, ties and permutation invariance are tested.
- [ ] ESOL/CNS MPO descriptions, output units, model status and uncertainty claims are accurate.
- [ ] Scientific fixtures have sources, licenses, checksums, exclusion rules and reproduction commands.
- [ ] External connectors obey local-first network policy, redirects/allowlists/rate limiting and provenance requirements.
- [ ] No GPU/Vulkan or model-performance claim exceeds demonstrated evidence.

### Build, test and UX

- [ ] Lockfile and dependency installation gates pass.
- [ ] Ruff format/check and mypy pass.
- [ ] Backend tests pass with coverage floor.
- [ ] Frontend typecheck and production build pass.
- [ ] Playwright E2E gates pass on clean isolated data.
- [ ] Visual QA has been performed on the actual application in both themes and required responsive widths.
- [ ] Accessibility and keyboard focus issues in critical flows are addressed.
- [ ] Fresh DB migration and migration-upgrade tests pass.
- [ ] Fresh wheel install passes on claimed release platforms.
- [ ] Real core lifecycle from import through workflow, run, results and export passes.
- [ ] Crash recovery, cancellation, cache integrity and deletion/path safety tests pass.

### Documentation, security and release

- [ ] README, implementation ledger, scientific limitations, package metadata, changelog, status badges and release notes are consistent.
- [ ] Relative links and screenshots have been verified.
- [ ] Dependency/license audits, Secret Scanning, CodeQL and dependency review pass.
- [ ] Release workflow is blocked unless every mandatory gate passed for the exact tagged SHA.
- [ ] Candidate and Stable versions are synchronized and the version verifier passes.
- [ ] Required branch protection and approvals are respected.
- [ ] Final cloud CI is green on the exact release commit.
- [ ] Wheel, SBOM, SHA-256 checksums and build attestation are published and verified.
- [ ] The downloaded release wheel was installed and smoke-tested.
- [ ] Final report contains actual evidence and accurately identifies any blocker.

---

## 17. Required final engineering report

At completion, produce a concise but evidence-rich report with:

1. **Release status:** not started / implementation complete / candidate verified / Stable published. Use only the status actually achieved.
2. **Source identity:** branch, final commit SHA, tag, package version and GitHub release URL if published.
3. **Changes made:** grouped into scientific correctness, provenance/cache, backend/DB, UI/UX, security, CI/release and documentation.
4. **Local gates:** exact commands, OS/runtime versions and pass/fail result. Do not report only “tests passed”.
5. **Cloud gates:** real Actions run IDs/links, conclusion and exact SHA.
6. **Scientific gates:** method, reference fixture, version, input checksum, test/benchmark command and measured result. Mark unavailable or skipped checks explicitly.
7. **Visual QA:** tested routes, viewports, themes, screenshots reviewed and issues fixed.
8. **Packaging:** wheel filename/version/hash, installation environment and smoke-test results.
9. **Release artefacts:** links and verified hashes for wheel, SBOM and checksum file; attestation verification result.
10. **Known limitations:** only real residual limitations, with their user impact and reason they do not block the claimed release, or the explicit blocker that prevents completion.
11. **Remaining human action:** only if a required permission/approval cannot be completed by the agent. Name the precise action; do not hide it among generic warnings.

Never report “all done” while a required gate is failing, unrun, skipped without approved exception or attached to a different commit. If a true blocker remains after five distinct repair attempts for its root cause, document it and continue all unrelated work. Do not publish Stable while the blocker affects a mandatory acceptance criterion.

---

## 18. Official references to consult during execution

Check current official documentation rather than trusting these links without verification:

- Repository and current releases: <https://github.com/timfromhcs/hcs-discovery-studio>
- AutoDock Vina documentation: <https://autodock-vina.readthedocs.io/>
- Meeko documentation: <https://meeko.readthedocs.io/>
- RDKit documentation: <https://www.rdkit.org/docs/>
- Alembic migration documentation: <https://alembic.sqlalchemy.org/>
- FastAPI documentation: <https://fastapi.tiangolo.com/>
- Pydantic documentation: <https://docs.pydantic.dev/>
- GitHub Actions security hardening: <https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions>
- GitHub artifact attestations: <https://docs.github.com/en/actions/security-for-github-actions/using-artifact-attestations>
- CycloneDX: <https://cyclonedx.org/>

Verify licenses and official method references for any additional tool, dataset, benchmark or model before using it.

---

## Final instruction

Proceed autonomously from the actual checkout. First inspect and record ground truth. Then implement the highest-priority correctness and release-gate fixes in small, testable batches. **Complete the local build/test/visual-QA/package loops before the first push.** Push only verified work to the correct branch, inspect Cloud CI on the exact pushed SHA, fix every genuine failure locally, rerun the necessary gates, commit and push again. Continue until all mandatory gates and independent scientific release checks are demonstrably green. Reconcile documentation after implementation stabilizes, rerun the final local and cloud gates after the documentation/release changes, and publish `v2.0.0 Stable` only when all acceptance criteria pass and the exact release artefacts are verified. Preserve honesty, security, user data and repository history at every step.
