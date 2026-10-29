# GEMINI.md — Autonomous Engineering Mandate for HCS Discovery Studio v2.0.0 Stable

**Project:** HCS Discovery Studio  
**Repository:** https://github.com/timfromhcs/hcs-discovery-studio  
**Maintainer / brand:** hcsmedia  
**Brand line:** `Open science. Reproducible discovery. Made with ❤️ by hcsmedia.`  
**Target:** a genuinely stable, scientifically honest, secure, tested, accessible, packaged and reproducible `v2.0.0` release for the platforms explicitly verified by the project.  
**Operating mode:** autonomous, evidence-driven engineering. Inspect the real repository state, implement the work, build locally, repair locally, test locally, perform visual QA, validate packaged artifacts, then push to GitHub and iterate against cloud CI until the exact release candidate passes. Update user-facing README and documentation after implementation is stable, then run final documentation/release verification. Publish v2 only after every release gate passes.  
**Core rule:** a claim is true only when supported by source, a test, a reproducible measurement, or a clearly cited authoritative reference. Do not fake success.

---

## 0. Mission and non-negotiable rules

You are the autonomous coding agent assigned to take the *current actual checkout* of HCS Discovery Studio from its real starting point to v2 Stable. Do not assume any version, file, feature or defect described in this document still matches `main`. It is a work plan and a set of high-value audit leads; prove every claim against the checked-out code.

Follow this lifecycle strictly:

1. **Inspect and preserve** the repository and working tree.
2. **Establish a reproducible baseline** and write down real failures.
3. **Implement and fix locally** in small, testable work packages.
4. **Build and test locally** after each work package.
5. **Run full local QA**, including live-app visual QA and packaged-wheel tests.
6. **Do not push code with known local failures.**
7. Push a dedicated branch and create/update a PR where repository permissions and branch policy allow.
8. **Observe cloud CI on the exact pushed commit.** Investigate logs, reproduce failures locally, fix, retest, push, and repeat.
9. Run independent scientific/functional verification and validate release assets.
10. Only after code is stable, perform the final README, documentation, repository metadata, screenshots, changelog and SEO pass.
11. Repeat final local and cloud gates after documentation/release-workflow changes.
12. Publish `v2.0.0` only when all required gates are green and the published artifacts are verified.
13. Report completion only after the release actually exists and checksums/assets have been verified. If an external permission or mandatory human approval prevents publication, finish all other work, state the exact blocker, and never claim that the release was published.

### 0.1 Truthfulness and scientific integrity

- A registry card, README paragraph, TODO, model name, mock, fixture or configuration field is **not** proof that a feature works.
- A feature is **implemented** only if the actual path exists; **runnable** only if requirements are available and a real run succeeds; **reference-tested** only if outputs are checked against an explicit independent reference; and **benchmarked** only if a defined dataset/protocol and metrics are executed and reported.
- Do not use “SOTA”, “validated”, “accurate”, “GPU accelerated”, “industry grade”, “production ready” or similar claims without scoped evidence. Name the task, method/model version, dataset and license, split, baseline, metrics, sample count, uncertainty, hardware and limitations.
- RDKit descriptors, similarity scores, composite rankings, predicted properties, CNS MPO scores and docking scores are computational results, not experimental proof of binding, safety, efficacy, selectivity or clinical utility.
- Do not silently turn an invalid input, missing engine, exception, partial calculation, missing value or failed run into a plausible-looking number or a success status.
- Do not treat an approximate uncertainty score as a statistically calibrated confidence interval without calibration evidence.
- Never create fabricated experimental data, fake benchmark results, fake screenshots, fake provider results, fake logs or fake CI status.
- Do not present test fixtures as real-world or experimental data. Label them clearly and preserve their provenance.
- Do not assert Vulkan/CUDA/GPU support based only on detection of a graphics device or runtime. Prove each engine/backend combination with an actual calculation and record which backend ran.
- Do not weaken, delete, skip, xfail, hide, quarantine or loosen a legitimate test simply to obtain a green build. Investigate flaky tests, correct the underlying defect, and report any unavoidable exception explicitly.
- Do not use the held-out scientific test set to tune models or thresholds. If it has already been used for tuning, label its result development-only and obtain a new independent test set before making a generalization claim.

### 0.2 Security and repository integrity

- Inspect `git status` before touching files. Preserve unexplained existing changes, untracked files and user data. Never reset, clean or overwrite them without understanding them.
- Never run broad destructive cleanup commands outside known disposable build/test directories.
- Never commit API keys, tokens, passwords, private keys, user data, restricted datasets or non-redistributable model weights.
- Never print secrets in logs or reports. Do not place credentials in `.env.example`, command history, test fixtures or documentation.
- Never force-push, rewrite public history, delete or move tags, bypass branch protection, disable security checks, or publish over an existing stable release to work around a failure.
- Follow the repository's actual rulesets and permissions. Use a branch + PR and required checks where supported. If approval is mandatory, do not bypass it; finish all independent work and report the precise remaining blocker.
- Treat imported chemical names, CSV/SDF metadata, public database text, model output and all other data as untrusted input.
- Third-party node handlers run with the application's privileges unless a real sandbox is implemented. Never imply that an allowlist alone provides operating-system isolation.

### 0.3 Autonomous operation and bounded repair loops

- Do not ask routine questions. Resolve normal engineering choices from the current code, official documentation, compatibility evidence and the smallest safe implementation.
- Do not stop at a plan. Implement, run tests, inspect failures, repair and verify.
- Work in small coherent batches. Use clear commits and preserve a decision/progress log in `docs/engineering/AGENT_LOG.md` or the repository's existing equivalent.
- Use a bounded **Build → Test → Diagnose → Fix → Retest** loop. Each retry must test a materially different diagnosis or fix; rerunning the identical failing command without changing anything is not a repair strategy.
- For any one blocking root cause, make up to five materially different diagnosis/fix attempts. After that, isolate the issue and proceed with independent work. Do not claim completion while the blocker remains. A human/permission blocker must be reported, not “fixed” by unsafe workarounds.
- Keep the work auditable: record command, environment, exit code, relevant logs, fix commit and exact verification outcome. Do not store unnecessarily large logs or private data in the repository.
- Update internal planning/status notes as work proceeds. Delay final marketing prose and the final README rewrite until the implementation and actual capabilities have stabilised.

---

## 1. Ground truth: inspect the current checkout first

This repository has changed quickly and the README, implementation ledger and earlier `GEMINI.md` have previously contained contradictory or stale status descriptions. Therefore, do not rely on historical version numbers or statements in this file without rechecking them.

### 1.1 Required initial inspection

From the repository root:

```bash
git status --short --branch
git branch --show-current
git log -20 --oneline --decorate
git remote -v
git tag --list --sort=-version:refname
```

Then inspect at minimum:

- `GEMINI.md`, any `AGENTS.md`, contribution/security policies and PR templates;
- `pyproject.toml`, `uv.lock`, `apps/web/package.json`, `apps/web/package-lock.json`, `tsconfig` and Vite/Playwright configuration;
- `.github/workflows/*`, Dependabot configuration, CodeQL and release workflow;
- `README.md`, `CHANGELOG.md`, `CITATION.cff`, `LICENSE`, `NOTICE`, `SECURITY.md`, `CONTRIBUTING.md`;
- `docs/engineering/*`, `docs/scientific-validation/*`, `docs/security/*`, `docs/architecture/*`, user guides and release notes;
- `src/hcs_discovery/`, `apps/web/src/`, `tests/`, `examples/`, `migrations/`, CI and release scripts;
- current GitHub releases, tags, recent commits, PRs/issues if accessible, current Actions runs and actual attached assets.

Use the installed versions and current official docs. Do not copy outdated version assumptions from a previous commit.

### 1.2 Establish capability truth

For every shipped engine/node/provider, determine each of these separately:

1. `implemented`: meaningful production path exists in source;
2. `dependencies_ready`: required executable, model files, packages and data exist;
3. `runnable_here`: a real local execution succeeds on the current host;
4. `smoke_tested`: basic execution test exists and passes;
5. `reference_tested`: output comparison to a known reference exists and passes;
6. `benchmarked`: a documented benchmark was actually run;
7. `experimentally_validated`: appropriate experimental validation exists, if applicable;
8. `supported_platforms`: exact platforms actually tested;
9. `limitations`: known scientific and operational constraints.

Do not collapse these into one `available` boolean. Keep existing API compatibility where possible, but define unambiguous statuses and map them consistently in registry/API/CLI/UI.

### 1.3 Output of the initial audit

Create/update `docs/engineering/V2_BASELINE.md` (or a similarly named engineering artifact) with:

- current HEAD SHA, branch, actual version/tag/release;
- environment/tool versions and platform;
- current feature/capability matrix with evidence links;
- baseline test/build commands, exact results and exit codes;
- known failures and reproduction commands;
- important dependency/license/security concerns;
- visual baseline screenshots or exact capture locations;
- prioritized tasks with acceptance criteria.

A command not executed must be marked `NOT RUN`. A command blocked by missing requirements must be marked `BLOCKED`, with reason and next step. Never report a presumed pass.

---

## 2. Branching and version strategy

### 2.1 Preserve the stable baseline

- Do not make direct, unreviewed edits to `main` if the repository's normal process supports branches and PRs.
- Create a dedicated branch such as `feat/v2-stable` or `release/v2.0.0` from the latest appropriate `origin/main` after preserving local changes and assessing divergence.
- If the current workspace has user edits, create a safe backup or separate worktree and preserve them. Never stash/drop or overwrite user work without understanding it.
- Use conventional, readable commit messages (`fix:`, `feat:`, `test:`, `docs:`, `build:`, `security:`) unless the repository's contribution rules specify otherwise.
- Keep each commit narrow enough to inspect. Prefer several logical commits over one giant opaque commit, but avoid noise-only commits.

### 2.2 Major-version discipline

- Inspect `pyproject.toml`, package metadata, `src/hcs_discovery/__init__.py`, frontend package version, changelog, version-verification scripts, release tags and release workflow before changing a version.
- Establish one authoritative project version and a tested strategy to synchronise Python package version, web package version if relevant, CLI/API version, changelog heading, tag and release assets.
- `v2.0.0` must not be created until the exact release candidate commit has passed all required gates.
- Use release candidates before the stable tag. Align the chosen tag convention with Python packaging pre-release conventions and test it in `scripts/release/verify_version.py`; examples include a documented mapping between `v2.0.0-rc.1` and a valid package version. Do not ship a candidate wheel mislabelled as the final stable version.
- Do not change or delete existing `v1.0.0` tags/releases. Never reuse a tag for different source contents.
- If release notes are generated from PR labels/history, still review them for correctness and remove unsupported claims.

### 2.3 GitHub process and permission limits

- Push only after local gates relevant to the current code have passed.
- After pushing, inspect the exact remote SHA and Actions runs associated with that SHA/PR. Do not infer cloud success from a previous commit's green run.
- Wait/poll for the actual required jobs through the available GitHub UI, GitHub CLI or connector. Read failed job summaries and logs, fix locally, rerun the relevant full gates, push the fix and repeat.
- Use a PR and let branch protections/reviews/status checks work as configured. If repository permissions do not allow push, PR creation, merging, tagging or release publication, continue with all work possible and record exactly which action needs the owner. Never claim a remote action succeeded unless the host confirms it.
- Do not automatically merge around a required human review. If policy permits unattended merge and all gates and approvals are satisfied, follow that policy; otherwise leave a fully prepared PR and report it as a blocker to publication.

---

## 3. Local-first baseline and development environment

### 3.1 Use disposable, isolated data

- Never run destructive or migration tests against a developer's real `data/` directory.
- Give each integration/E2E test an isolated temporary `HCS_DATA_DIR` and verify it is disposable before cleaning it.
- Prefer `tmp_path`, test fixtures and a temporary user-data directory. Stop any server/worker started by a test when the test ends.
- Ensure no test relies on a pre-existing local database, network service, model cache or hidden file.
- The ordinary test suite should remain deterministic and offline. Network-dependent tests must be separately marked and never run by surprise in the default test suite.

### 3.2 Baseline command set

Run commands from the repository root unless the command says otherwise. Adapt syntax to the actual OS/shell. Capture exit codes and logs.

```bash
# Python environment and diagnostics
uv --version
uv sync --dev
uv run python --version
uv run hcs-discovery version
uv run hcs-discovery doctor

# Static quality
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run python scripts/ci/prepare_typecheck.py
uv run mypy

# Tests and coverage
uv run pytest -q --strict-markers
uv run pytest --cov=hcs_discovery --cov-branch --cov-report=term-missing

# Frontend
cd apps/web
npm ci
npm run typecheck
npm run build
npm run test:e2e
npm run screenshots
cd ../..

# Packaging (only after a fresh frontend build)
uv build --wheel
```

Use the repository's current equivalent if one of these scripts has changed. Do not remove an existing gate just because a command name changed; update this instruction and CI together.

### 3.3 Fresh-install and whole-journey baseline

In an isolated directory/virtual environment, prove the user journey from a clean state:

1. Install the package/source dependencies.
2. Run `hcs-discovery doctor` and record detected/unsupported capabilities truthfully.
3. Start the app on loopback using a non-default test port and isolated data directory.
4. Open the live UI and create a project.
5. Import a permitted, small CSV/SDF/SMILES fixture with known valid and invalid rows.
6. Inspect row outcomes, errors, duplicates and standardisation metadata.
7. Create/validate a workflow and make an intentionally invalid one to prove validation fails properly.
8. Submit a run, view node progress/events/logs, and wait for a real terminal state.
9. Inspect all result rows, ranking meanings, units, missing values and provenance.
10. Export CSV, JSON, Markdown/HTML and SDF where those formats are claimed supported; compare completeness and hashes where relevant.
11. Restart server/worker and reopen persisted data/results.
12. Build/install the wheel in a clean environment, start it without Node installed at runtime, and verify health endpoint plus root SPA content.
13. Shut down cleanly and confirm no unexpected background process remains.

Any step that fails is a development defect or explicitly documented limitation; do not describe the journey as successful until it has passed.

---

## 4. Build/Fix/Test loops: required working method

Use a small work-package loop for every defect or feature.

### Loop A — Reproduce

1. Read the relevant implementation and its callers/contracts.
2. Reproduce the failure with the smallest possible deterministic test.
3. Confirm that the test fails for the expected reason on the pre-fix code.
4. Record the command and minimal failure evidence.
5. Check whether a recent commit has already fixed the issue; do not reapply stale fixes.

### Loop B — Fix

1. Identify the root cause, not just the visible symptom.
2. Make the smallest safe code change consistent with the architecture.
3. Add/modify a regression test that protects the invariant.
4. Do not catch generic exceptions just to keep the process alive. Expected data errors should be distinguished from unexpected programmer/runtime defects.
5. Keep error messages useful, structured and free of secrets or excessive raw input.
6. Update in-code contract/docstrings where behavior changed, but defer the final prose/marketing sweep until features stabilise.

### Loop C — Verify the focused area

Run its unit tests, then integration tests for the same contract. Run lint/type checks if affected. Review the full diff for regressions and accidental unrelated edits.

### Loop D — Regression suite

After each coherent work package, rerun all relevant tests and a full build often enough that integration defects are found early. At the phase boundary, run the complete local quality gate from Section 12.

### Loop E — Build/Fix loop with a real hypothesis change

If the gate fails:

1. Save the first failing command and error summary.
2. Identify whether the failure is code, test setup, environment, dependency, browser, package, data or tooling.
3. Change one relevant cause at a time.
4. Re-run the focused test.
5. Re-run adjacent integration tests.
6. Re-run the full affected gate.
7. Repeat until green or until five materially different, evidence-based attempts have failed.
8. If still blocked, document the blocker and continue independent tasks; do not suppress the error.

A green test suite with a missing required test suite is not a full pass. A successful build does not prove runtime behavior. A successful runtime smoke test does not prove science. Keep those evidence types separate.

---

## 5. Engineering correctness and architecture hardening

Audit these areas against the current code and address all confirmed P0/P1 defects.

### 5.1 Strict scientific workflow schemas

- Make every node configuration reject unknown fields unless there is a documented forward-compatibility reason.
- Use typed contracts and Pydantic validation for every input/configuration path (UI, CLI, HTTP API, imported workflow and agent-generated workflow).
- Validate finite numeric values; reject unintended `NaN`, positive/negative infinity, negative counts, out-of-range values and invalid combinations.
- Enforce operator-specific types for filters (`le`, `lt`, `ge`, `gt`, `eq`, `ne`, `between`); check that `between` bounds make sense and are documented; never let invalid types fail only during expensive execution.
- Validate objective semantics: maximize/minimize, target range, hard constraint and informational-only fields are distinct. Do not confuse a constraint with an objective or let irrelevant fields silently affect a Pareto front.
- Define missing-value behavior explicitly for filtering, joins, scoring and exports.
- When configuration is invalid, return a stable error code plus field-level information that the GUI can display next to the affected input.

### 5.2 Workflow graph and table correctness

- Validate unique node IDs, unique edges, known source/target nodes, cycle absence, valid root/terminal conditions, required input columns and compatible output types.
- Ensure the topological order is deterministic for a fixed workflow specification.
- Test fan-out and fan-in/`table.join` behavior with identity keys, not row position. Define duplicate-key behavior for left/inner/outer joins and test it. Do not silently duplicate or discard compounds.
- Detect output-column name collisions; make suffix behavior deterministic and clear in the UI.
- Ensure cancellation is checked at sensible intervals inside long loops and immediately before/after expensive node invocations where practical.
- Preserve stable compound/row identities through branches and exports.
- Every result column needs a meaning, unit where applicable, method/model, direction where meaningful, and explicit caveat if it is a score rather than a measured endpoint.

### 5.3 Pareto and composite ranking

- Prove Pareto non-dominated sorting is invariant to input row permutation, including tied/identical points and objective combinations.
- Test that no item in a later front dominates an item in an earlier front.
- Ensure filter-failing rows are not accidentally ranked as eligible candidates, while retained rows and reasons remain inspectable.
- Verify zero weights, missing values, informational fields, constraints and target-range fields do not secretly distort Pareto membership or composite scores.
- Document that min-max composite scores depend on the comparison dataset and may shift when outliers or candidates are added.
- Avoid encoding universal “good” directions for metrics unless justified; users must be able to inspect objective semantics and weights.
- Add property-based tests for plausible random objective arrays where suitable; retain small explicit counterexamples for any previous defect.

### 5.4 Chemistry parsing and standardisation

- Preserve original source values and file checksum. Standardisation must be recorded explicitly and reproducibly.
- Bound input sizes and molecule complexity; record per-row parse/standardisation failures and reasons without logging sensitive full structures unnecessarily.
- Check stereochemistry, salt stripping, neutralisation, canonical tautomer options, fragment handling, invalid structures and mixed formats.
- Do not silently swallow all errors in descriptor calculation or standardisation. Expected molecule-level failures may become row-level error results; unexpected implementation defects must surface as failed tests/runs.
- Descriptor outputs must be compared against a small fixed, redistributable reference set for the pinned RDKit version and include correct units/directions/method metadata.
- Test duplicate identity rules and explain the distinction between raw duplicates, canonical SMILES, stereoisomers and InChIKey where used.

### 5.5 Service/API/CLI parity

- Avoid having independent business logic in React, routes, CLI commands and agent handlers. Use shared services and test their contracts.
- Test error codes and appropriate HTTP/CLI exit codes for invalid input, missing resources, policy blocks, cancellation and runtime failures.
- Confirm all mutations have clear semantics and that destructive operations require proper confirmation in the CLI/UI.
- Check settings are resolved from the actual app instance where dependency injection is used; app-factory tests should override environment defaults deliberately and verify those exact values are used.
- Preserve compatibility of the versioned `/api/v1` API or explicitly document any breaking change. Add schema/API snapshots or contract tests for important responses.
- Ensure pagination is stable, bounds are enforced, and large results are not loaded into memory or returned unbounded without a reason.

### 5.6 Database/migrations/filesystem lifecycle

- Audit Alembic upgrades from an empty database and from every supported older schema. Do not mark an incomplete schema as migrated merely because one table exists.
- Test constraints, foreign keys, transactions and deletion behavior with actual data.
- Use separate temporary data directories for tests. Handle databases locked by concurrent worker/API access without corrupting the database.
- Define whether deleting projects/datasets means database deletion only, file deletion, soft delete or retention. Expose the choice accurately and safely.
- Implement a deletion preview/dry-run if file deletion is introduced, including a list/size of affected files. Prevent path traversal and symlink escapes; do not delete paths outside the configured data root.
- Cache management must use real configurable limits where promised, support status and dry-run, remove orphaned entries, and remain safe when a worker is writing.
- Cache keys must include every factor that can change scientific outputs: node implementation/version, config, exact input fingerprint, relevant engine/model/weights/preprocessing versions, schema version, stochastic seed, and other parameters that matter. Test invalidation when any factor changes.
- Use atomic writes for manifests/artifacts where practical. Verify file size/hash after writing and never expose partial artifacts as complete.

### 5.7 Queue, workers and retry semantics

- Explicitly document queue delivery semantics (for example at-least-once) and make node side effects safe under retries where feasible.
- Test heartbeat/lease expiration, duplicate claims, concurrent workers, process restart, crashes during node execution, cancellation races, retry limits and terminal states.
- Make “cancel requested”, “cancelled”, “failed”, “succeeded” and “partial” unambiguous. Never mark a cancelled/failed run succeeded because output artifacts happened to exist.
- Ensure logs/events are ordered consistently enough for UI and CLI consumers; sequence allocation must remain correct under concurrent writes.
- Avoid long blocking event-loop work in asynchronous API handlers. Heavy scientific work belongs in the worker/executor path.

---

## 6. Scientific adapter validation — no claims without evidence

Before v2 release, each adapter must have a clear status and tests appropriate to the scientific claim. Build a small, legal, reproducible fixture suite; do not try to “validate everything” by downloading a giant unrestricted dataset.

### 6.1 Common adapter contract

Every scientific adapter must document and expose:

- task, target endpoint, output units and intended use;
- input file/schema and preprocessing assumptions;
- adapter version and upstream engine/model version;
- exact command/parameters/seeds relevant to reproducibility;
- dependency/license attribution for code, weights and data separately;
- resource and platform requirements;
- known failure modes and scientifically meaningful invalid-input behavior;
- citations to primary papers and official installation/API documentation;
- offline deterministic tests where possible;
- reference/benchmark evidence and its exact scope;
- a status reflecting what has actually been proven.

### 6.2 AutoDock Vina

Inspect the whole current docking path, including binary discovery/probe, receptor validation, ligand preparation, process arguments, timeout/cancellation, output parsing, pose conversion, errors, artifact hashing and result persistence.

High-value checks:

- Verify `--version` probe checks process return code and meaningful version output; an executable that exists but fails must not be marked available.
- Ensure configured executable paths are handled correctly on Windows and Linux. Test executable discovery using fakes and a real optional integration when Vina is installed.
- Validate receptor coordinates and required atom/type fields. Reject a file with atom records but invalid/non-finite coordinates rather than deriving invalid bounds.
- Check PDBQT torsion trees and flexible-bond representation. The existing custom preparation code must not be assumed correct simply because it emits `ROOT`, atom lines and `TORSDOF`. Compare against the official Vina requirements and a known-good preparation tool such as Meeko; adopt the established tool if that is safer and properly licensed.
- Validate stereochemistry, protonation/tautomer assumptions, salts/mixtures, hydrogens, charges, atom types, rotatable bonds, atom naming, coordinate ranges and pose SDF conversion.
- Do not suppress unexpected failures in MMFF or charge calculation without recording a scientifically meaningful warning/status. If a fallback is used, disclose it in provenance.
- Use subprocess argument arrays rather than a shell command string. Bound time/resources, terminate cleanly on timeout/cancellation where possible, redact errors and limit raw stderr disclosure.
- Verify that failed ligands are represented as failed/missing outputs with per-ligand reasons, not a binding score of zero or a misleading success.
- Provide deterministic parser/adapter tests with fixtures, plus an optional real-engine integration test.
- Provide a documented redocking benchmark using structures/ligands that can legally be used and redistributed or retrieved reproducibly. Record PDB identifiers/source/version, preparation, coordinates/box, random seed, exhaustiveness, RMSD definition, success threshold with scientific justification, number of targets, failures and results. Do not claim pose-recovery performance without executing it.
- A widely used RMSD threshold such as 2 Å may be a reference point in some redocking protocols, but it is not a universal guarantee; justify the protocol and limitations.
- Keep docking score caveats visible in the UI, exported reports and model/adapter metadata.

### 6.3 Property prediction and scores

- Audit each current model's formula/coefficient provenance, units, training-data citation, domain definition, weight/coefficient hash, missing-value semantics and reported metrics.
- Distinguish a learned model, a published linear equation, a heuristic descriptor score and an empirical scoring function. Do not label all as “AI prediction”.
- CNS MPO is a multiparametric desirability score and must not be misrepresented as direct experimental BBB permeability.
- Check descriptor formulae against the cited original paper or an authoritative implementation. Include tests for molecules on both sides of domain boundaries, uncommon elements, invalid SMILES, charged species, outliers and edge cases.
- Do not treat a distance-based error proxy as calibrated uncertainty unless coverage/calibration is evaluated on a valid independent set.
- Define a reproducible benchmark protocol with data source/version, retrieval date, hash, license, endpoint/unit, curation, exclusions, duplicate handling, split strategy, seed, baselines, metrics and results.
- For regression, report appropriate metrics (for example MAE/RMSE/R²) with sample counts and confidence intervals where appropriate. Use task-appropriate ranking/classification metrics for other endpoints. Report all predefined primary metrics, not only the best result.
- Avoid data leakage: scaffold split is a sensible default for many molecular property tasks; use time splits when the intended use is prospective and data permits. Explain when a split is inappropriate.
- Keep the held-out test set untouched during model selection. If it has already guided development, say so and obtain an independent test set for a final claim.
- Benchmark scripts must emit machine-readable results plus a human-readable report and an exact command/commit record. Default CI should use small offline correctness tests; longer scientific benchmark suites can be scheduled or manually triggered, but the release claim must link to their real result.

### 6.4 PubChem and ChEMBL connectors

- Default local/network policy must block remote access until explicit opt-in. Make outbound calls visible to the user and include source URL, retrieval timestamp, source ID, license/attribution and payload checksum in saved provenance.
- Test host allowlisting, redirect behavior, timeout, request size, rate limit, retries, 404/429/5xx, malformed JSON, oversized response and offline mode with deterministic mock transports.
- Ensure redirected requests cannot silently escape the intended allowlist. Validate actual destination hosts on every redirect or disable redirects unless explicitly safe.
- Respect each provider's usage policies and attribution/licensing rules. Do not bundle restricted external database dumps in the repository.
- Cache stable responses transparently and distinguish cached data from current provider data.

### 6.5 Other engines and GPU/Vulkan

- Do not include a large model merely to advertise breadth. Add an adapter only when there is a concrete user path, license/weight/data audit, resource estimate, tested version and acceptance suite.
- Large GPU models (structure prediction, molecular dynamics and ML inference) should be optional extras, not hard dependencies for the base CPU workflow.
- If Vulkan is a goal, identify the specific model runtime/API that actually supports it, use real test inputs, compare its outputs against a valid reference/tolerance, measure speed and memory, and record device/driver/library versions. Device presence alone is not model support.
- Keep the core CPU path working on supported Windows/Linux machines without CUDA, Docker, cloud credentials or a runtime model download.

---

## 7. Research Agent correctness and safety

Treat the agent as a controlled interface to existing scientific capabilities, not an autonomous authority.

### 7.1 One source of truth for tool contracts

- Build plans from the real NodeRegistry/model catalog and their JSON schemas rather than hardcoded node-name or model guesses.
- Reject unknown fields on every agent tool payload.
- Fix all discrepancies between generated configuration and target schemas. Audit `PropertyPredictorConfig` and all callers: a model selection must use the schema's actual `model_id` field; never assume a field such as `models` works.
- Ensure requested endpoint and chosen adapter actually match. CNS MPO/ESOL/docking/descriptor tasks must not silently substitute one another.
- Validate the entire proposed graph and every config before presenting `valid=true` or “PASS”. Preserve the validation issues; do not swallow an exception and only show a boolean without actionable detail.
- Do not rely on a keyword-only planner if it cannot handle the requested semantics. If the request cannot be mapped safely to a supported workflow, say so and provide a plan with an explicit unsupported step rather than inventing a workflow.

### 7.2 Ask → Plan → Approve → Run → Explain

- Ask mode is read-only and should not mutate database/filesystem state.
- Plan mode must not queue runs or create persistent objects. It returns a typed, editable plan with real node definitions, required inputs, resources, network access, outputs, limitations and unsupported assumptions.
- Approval binds to an exact canonical plan (include its content hash and workflow/config hash). Before executing, revalidate the submitted plan and compare the hash. If any field, model, target, path or parameter changed after approval, require a new approval.
- Run mode executes only allowlisted, typed server-side functions. Never add arbitrary shell, Python eval, unrestricted filesystem access, SQL, network URL fetch or dynamic import tools for convenience.
- Server-side policy must not trust a client-provided boolean or `approved_tool_calls` field without validating that the user/session is authorised to approve the specific current plan. If the local single-user product has no identity system, explicitly scope this as local-operator authorization and require the strongest feasible confirmation boundary.
- Mutating/destructive/high-cost operations require explicit confirmation with meaningful details. The plan should show dataset size, external calls, expected runtime/resource estimate when it can be estimated, files/objects created, and cancellation behavior.
- Treat compound names, dataset contents, external API text and model output as untrusted data. Structured separation is preferable to delimiter-only `<untrusted_data>` wrappers; never assume delimiter tags alone defeat prompt injection.
- Do not pass secrets to an LLM. Local mode must be truthful about whether the model endpoint is local or remote. Remote use needs explicit policy opt-in.
- Show actual executed tool names, arguments with sensitive values redacted, result states, failures and run IDs. Never mark a tool as successful because a call was attempted.
- Add adversarial tests in which an imported compound name or external text instructs the model to ignore rules, reveal secrets or execute unsupported actions. Verify such data cannot grant permissions or bypass the allowlist.

### 7.3 Resource estimation and failure containment

- Do not use hardcoded resource/runtime estimates that conflict with dataset size, model, backend or platform. Either provide a defensible estimate/range or label it unknown.
- Enforce queue/run/resource limits where practical and handle cancellation.
- A provider outage should produce an explicit error or an accurately labelled deterministic fallback; never silently report an LLM response that was not generated.
- Test no-provider, unreachable-provider, blocked remote policy, malformed model output, invalid plan, approval mismatch, tool error and partial execution.

---

## 8. User experience, accessibility and real visual QA

Visual QA is mandatory and must use the actual application running against the real backend. Do not use generated mockups as proof of UI functionality.

### 8.1 Review every route

Enumerate actual routes from React Router and exercise them. At minimum inspect:

- workspace/dashboard and system/diagnostics state;
- project list/detail and project creation/edit/delete flows;
- dataset import, validation, row/error inspection and deletion;
- compound/library search, detail, structure depiction and copy/export actions;
- workflow list, create, edit, validate, save, clone/import/export where supported;
- run monitor, event/log stream, cancellation, failure and completed status;
- results table, Pareto scatter, filters, sort and report downloads;
- model/adapter registry, data sources, settings, about and not-found pages;
- agent Ask/Plan/Run modes if they are included in the final capability contract.

Every visible button/link must perform its advertised action or be clearly disabled with a reason. No dead controls, placeholder handlers, fake progress, mock success states or unhandled browser errors.

### 8.2 Viewports and themes

Use Playwright and screenshots at these viewport widths at minimum:

- 320 px (small mobile),
- 390 px (mobile baseline),
- 768 px (tablet),
- 1024 px (small laptop),
- 1280 px (desktop),
- 1440 px (wide desktop).

Review light and dark themes wherever supported. At least 320/390, 768 and 1440 should have screenshot evidence for critical pages. Ensure:

- no horizontal page overflow unless a table has intentional, accessible horizontal scrolling;
- dialogs fit the viewport and remain scrollable;
- tables preserve identity and provide sensible small-screen behavior;
- charts have readable axes, legends and accessible alternative summaries;
- loading/empty/error/success states are visually distinct;
- keyboard focus is visible;
- color is not the only indicator of status;
- text contrast and controls meet WCAG 2.2 AA where applicable;
- all interactive controls have accessible names/labels and useful focus order;
- reduced-motion preferences are respected where animation exists.

### 8.3 Visual QA loop

For each meaningful UI change:

1. Build the frontend from current source.
2. Start API and worker using a temporary isolated data directory.
3. Start or serve the actual built SPA (not a stale bundle).
4. Run Playwright E2E and capture screenshots.
5. Inspect screenshot files as images. Use a screenshot review tool/viewer and compare the actual pixels/content; do not assume the test passed because the image was saved.
6. Check console errors, uncaught page errors, failed network requests, clipped content, overlap, layout shifts, missing glyphs/assets and responsive behavior.
7. Run accessibility scans/tests if available. Add a maintained accessibility test tool if it provides meaningful value and can be installed/licensed safely.
8. Fix issues and repeat until clean.
9. Re-capture after the final frontend build and keep only screenshots that correspond to real current UI state.

Do not commit build/test screenshots containing real user data, secrets, local filesystem paths or tokens. Use synthetic, clearly labelled fixtures. Visual snapshots must not pretend optional engines worked if the engines were unavailable.

### 8.4 UI implementation quality

- Reuse common components, style tokens and layout primitives.
- Keep API error messages and field errors actionable and accessible.
- Use explicit skeleton/loading states only while work is happening; do not fake progress.
- Make long-running operations cancellable where supported and show what is being cancelled.
- Explain scientific terms/units next to results and preserve the limitations disclosure in context.
- Ensure all data is reachable by keyboard and that charts are not the only means of understanding a result.
- Keep the HCS brand visually consistent without allowing branding to obscure status, warnings or scientific caveats.

---

## 9. Security, privacy, dependency and supply-chain gates

### 9.1 Application-level checks

- Default host is loopback. Non-loopback binding requires explicit secure configuration, authenticated access and clear documentation that token-only deployment without TLS is not a hardened remote-service configuration.
- Review CORS, CSP, security headers, API auth, request limits, rate limits and error envelopes against current source and actual browser behavior.
- Test path traversal, absolute paths, Windows reserved names, symlink escapes where feasible, unsafe artifact names, large uploads, malformed CSV/SDF, huge molecules, timeout/cancellation and malformed provider replies.
- Validate allowed outbound hosts at connection time and handle redirects safely; use strict timeouts and response-size limits.
- Ensure logs, run events, reports, diagnostics and agent outputs redact credentials and sensitive values. Prefer not to log raw input data at all.
- Test policy enforcement with both permitted and forbidden network requests using mocked transports; ordinary tests must not unintentionally hit the internet.
- Re-review local data handling and deletion lifecycle. Make retention behavior explicit; do not promise secure erasure unless it is implemented and testable.
- Revisit `docs/security/THREAT_MODEL.md` after any changes to agent tools, plugin loading, external connectors, model weights, remote hosting or filesystem handling.

### 9.2 GitHub Actions hardening

Inspect every workflow and enforce, where compatible with required behavior:

- explicit minimum `permissions:` at workflow/job level;
- third-party actions pinned to reviewed full commit SHAs (the repository already does this in inspected workflows; preserve it and verify any new action);
- pinned/locked tool versions and consistent dependency setup;
- `persist-credentials: false` for checkout jobs that do not need authenticated pushes;
- no secrets or write tokens in untrusted PR code paths;
- no unsafe `pull_request_target` pattern that checks out/executes fork code with privileged secrets;
- concurrency settings that cancel obsolete CI runs but do not cancel a release mid-publication;
- reasonable job timeouts and useful failure artifacts;
- dependency review, secret scanning, CodeQL and license/SBOM policy;
- release permissions separated from ordinary CI jobs;
- no broad write permissions in tests or pull-request workflows;
- no `continue-on-error` for mandatory release gates.

Do not blindly update GitHub Actions to a new major version without verifying its official docs, full commit SHA, runtime compatibility and change log.

### 9.3 Dependency and license auditing

- Check Python lockfile, npm lockfile, transitive dependencies, installed optional adapters, bundled assets and model weights.
- Run the repository's current dependency audit commands; fix known relevant vulnerabilities, prioritising exploitable runtime issues. Document justified exceptions precisely with affected versions, risk, mitigation and expiry/review date.
- Run license checks for source, dependencies, data, models and weights separately. A repository license for code does not automatically license bundled model weights or a dataset.
- Generate a current SBOM from the actual release environment and verify that its dependencies match the wheel.
- Do not commit large/restricted data or model weights. Use a manifest, official source link, license conditions and checksum when redistribution is not permitted.
- Review generated artifacts to ensure no `.env`, test database, fixture results from private data, cache, API key, debug dump or local absolute path has been packaged.

---

## 10. Performance and resilience test plan

Do not invent performance targets before measuring the baseline. Define and report realistic baselines with environment metadata, then set acceptance thresholds that guard against material regression.

### 10.1 Representative sizes

For operations where appropriate, test small and medium data sizes (for example 100, 1,000, 10,000 and the configured supported maximum where practical). Do not force an expensive external engine to run at the maximum without checking resource/time expectations first.

Measure:

- import throughput and memory;
- RDKit standardisation/descriptors/fingerprint similarity throughput;
- filtering and multi-objective ranking runtime;
- table joins and result persistence;
- cache hit/miss/serialization costs;
- API response latency for list/detail/paged results;
- SSE/event update behavior under long jobs;
- cancellation latency;
- restart recovery after worker/API failure;
- artifact size, storage growth, cleanup and cache pruning.

Record CPU, RAM, OS, Python/RDKit/runtime versions and seed. Avoid brittle unit tests for wall-clock seconds; use a separate benchmark script/report for performance and a loose regression threshold only where stable enough.

### 10.2 Resilience cases

- Stop a worker while it is running a multi-node workflow, restart it, and verify recovery semantics.
- Expire a lease and ensure duplicate work/terminal status is handled according to the documented queue contract.
- Cancel before start, during a cancellable node and during an external process.
- Fill the cache past its configured limit and prove the policy works with `dry-run`/status output.
- Corrupt a cache entry or artifact and verify it is rejected and regenerated/failed safely.
- Simulate read-only directories, disk-full/permission errors where feasible, SQLite lock contention and invalid migration state.
- Confirm failed runs retain enough diagnostics without exposing secrets or raw private datasets.

---

## 11. Test construction guide: make tests prove the behavior

Tests are executable specifications. Build tests from observed contracts and invariants, not from assumptions about how the code ought to work.

### 11.1 Unit tests

Use small, deterministic inputs. Cover:

- normal/edge/invalid values;
- numerical tolerances, units and return types;
- unknown fields and out-of-range values;
- duplicate/tie/missing-value cases;
- exception mapping and error codes;
- path and network-policy invariants;
- cache invalidation and stable serialization.

A good regression test must fail if the bug is reintroduced. Avoid assertions so weak that a wrong result still passes (for example “the output is a number” when an exact/tolerance-bound reference is known).

### 11.2 Property-based tests

Use Hypothesis (already in the development dependency group unless current metadata says otherwise) where it helps explore combinations that humans do not enumerate:

- Pareto sorting invariants under permutations and duplicate points;
- canonical hashing stability and key sensitivity;
- joins with missing/duplicate keys;
- workflow graph generation and cycle detection;
- safe path joining and filename sanitisation;
- import parsing and row outcome totals.

Keep seeds/examples reproducible and save reduced minimal counterexamples as explicit regression tests when a property fails.

### 11.3 Integration tests

Test the real contracts across services, database, queue, API and CLI with isolated temporary settings. Check persistent side effects before and after each operation. Assert both success and expected failure codes. Avoid network calls by using mock transports and fake executable scripts where an external binary is optional.

### 11.4 Scientific tests

Maintain separate categories:

- **offline correctness/fixture tests**: part of default CI and expected to be deterministic;
- **reference tests**: small, legal reference data and known outputs/tolerances;
- **benchmark suites**: fixed documented datasets/protocols and all primary metrics;
- **optional integrations**: tests that need Vina, GPU, large model weights or external network access.

Clearly label each category in pytest markers and documentation. A passing fixture test must never be reported as an accuracy benchmark.

### 11.5 API/CLI contract tests

For every important user action, prove the API and CLI call the same business behavior and persist compatible state. Test JSON output, stable error envelopes, pagination, auth/policy gates and cancellation semantics.

### 11.6 End-to-end tests

At minimum prove:

1. fresh install → launch → workspace;
2. create project → import valid/invalid fixture → inspect errors;
3. pick/edit/save workflow → intentionally invalid workflow is rejected before queueing;
4. run → monitor → success/failure → results;
5. inspect output columns/units/provenance → download complete artifacts;
6. restart app → history persists;
7. unavailable optional engine is reported clearly and cannot be submitted as though it were available;
8. planned/unsupported functions cannot appear to succeed;
9. agent plan cannot execute without the right approval and cannot execute a mutated approved plan;
10. an unknown ID displays a genuine error state instead of fabricated data.

Do not use `test.only`, silently skip critical specs, or let a Playwright retry hide a flaky test. If retries are configured for diagnostics, fail the release if a retry was needed or explicitly classify it as flaky and fix the cause before release.

---

## 12. Mandatory full local gates before the first push

Before the first push containing implementation changes, all applicable local gates below must pass on the exact working tree. Store a short machine-readable summary with command, exit code, timestamp, environment, and result. Record the git diff/commit associated with the run.

### 12.1 Clean/format/type gates

- `uv lock --check`
- Python format check and Ruff lint
- Python type check using the current supported strategy; if an RDKit-stubs workaround remains necessary, document why, ensure no application code is skipped, and add an expiry/review condition
- frontend TypeScript typecheck
- frontend production build
- license checks for Python and Node packages
- dependency audit / secret scan where tools are available

### 12.2 Backend tests

- complete offline unit/integration/security suite;
- coverage gate equal to or stronger than current CI (do not lower it to pass); raise it for critical new paths where practical;
- fresh SQLite migration plus supported upgrade path;
- queue/worker recovery and concurrency cases;
- scientific fixture/reference tests;
- API and CLI parity tests.

### 12.3 Frontend and visual tests

- Playwright E2E against a fresh build and isolated data directory;
- screenshots at the required viewport widths and themes;
- inspect screenshots visually, not just by existence;
- no uncaught browser errors, console errors relevant to the app, failed required network requests or broken assets;
- no horizontal page overflow, clipped modal content, inaccessible controls or placeholder behavior on critical pages;
- run accessibility checks and fix high-severity issues.

### 12.4 Package tests

- build wheel from the final frontend bundle;
- inspect the wheel file list to ensure it contains the correct built SPA and required package assets but no private data, `.env`, tests-only files or cache;
- install it into a **fresh, isolated environment**;
- run version/doctor commands;
- launch server and test health/readiness/root SPA endpoints;
- perform a minimal real project→import→run→report journey from the wheel;
- verify that runtime does not need Node or a source checkout;
- compare package version, CLI version, API version and release metadata;
- on Windows, verify path handling and wheel launch; use local Windows execution if available and retain Windows cloud CI as a mandatory platform gate.

### 12.5 Mandatory stop condition

**Do not push implementation code until all mandatory local checks pass.** If a non-available OS or optional GPU cannot be tested locally, clearly mark the local check `NOT AVAILABLE` and ensure an explicit cloud test or scope limitation covers it. Do not claim local proof for a check that was not run.

---

## 13. Push and Cloud CI fix loop

This phase starts only after Section 12 passes for the exact source tree.

### 13.1 Before pushing

1. Review `git diff --check`, `git diff --stat`, full diff and `git status`.
2. Search for secrets, local paths, generated data, `TODO`/`FIXME`, debug prints, `test.only`, skipped tests, accidental version drift and unsupported claims.
3. Commit logically grouped work.
4. Re-run all tests affected by the last change; if it is release-ready, run the full mandatory local gate again.
5. Verify the branch is based on the intended latest main and there are no unexpected deletions/overwrites.
6. Push the branch and create/update a PR using the repository's templates where possible. Include a factual summary, change rationale, tests actually run, risks, screenshots and links to scientific validation evidence.

### 13.2 Cloud loop

After each push:

1. Read the remote branch head SHA; it must match the intended commit.
2. Find the CI, CodeQL, security, dependency-review, license, migration, E2E, package/wheel and other required Actions runs for that exact SHA/PR.
3. Wait/poll for completion using the GitHub UI/CLI/available connector; do not declare success while a run is queued or in progress.
4. If any mandatory job fails, get the job summary and logs. Identify the first causal failure, not just downstream failures.
5. Reproduce the issue locally, or document why it is cloud-specific and create a deterministic local reproduction when feasible.
6. Fix the cause locally; add a regression test; run the focused test, relevant integration tests and all mandatory local gates affected by the change.
7. Commit/push the fix. Inspect the new remote SHA and repeat from step 2.
8. Repeat until all mandatory gates are green on the newest commit. Never use a successful run from an earlier SHA as evidence for a later one.

### 13.3 Cloud-specific failure examples

- Linux passes but Windows fails: inspect path separators, reserved filenames, subprocess executable suffixes, encoding/locale, line endings, file permissions and shell syntax. Add/adjust a platform-specific test.
- Local E2E passes but CI E2E fails: inspect trace/screenshots, server readiness, ports, isolated data directory, stale frontend bundle, timing assumptions and browser version. Fix the root cause rather than increasing sleeps blindly.
- Wheel smoke fails but source tests pass: inspect package build inclusion, asset resolution, migrations, runtime data paths and optional imports. Test the actual wheel in a fresh environment.
- Dependency audit fails: inspect exact affected package/version/advisory and update compatibly with lockfiles; rerun tests. Do not suppress advisories indiscriminately.
- CodeQL or security check fails: investigate the finding and add a justified code change/test. Suppress only a demonstrable false positive with a precise explanation and minimal scope.
- License gate fails: audit whether code/weights/data are compatible and properly attributed. Replace/remove incompatible content if necessary; do not simply edit the scanner allowlist to hide the issue.

### 13.4 Merge policy

- Do not merge while required status checks fail, are pending or are missing.
- Follow branch-protection rules, required review and conversation resolution. Do not bypass a human review if the repository requires one.
- After merge, verify the final `main` commit has its own required cloud checks green. If the merge commit's checks are not green or are absent, fix and verify before tagging.

---

## 14. Release workflow and publication safety

The release pipeline is part of the product. Inspect the current `.github/workflows/release.yml` rather than assuming that a version tag alone proves release readiness.

### 14.1 Release workflow requirements

The release path must:

1. Validate tag/package/changelog version agreement and reject an existing tag mapped to different source.
2. Check out the exact tagged commit and record the full commit SHA.
3. Run the full mandatory test gates on that source (or verify unambiguously that required successful CI checks exist for that exact SHA plus run any release-specific checks still needed).
4. Build frontend and Python artifacts from a clean reproducible environment.
5. Produce a software bill of materials (SBOM), checksums and supported build provenance/attestation.
6. Verify the wheel can be installed and the app starts/serves its bundled SPA.
7. Generate release notes from correct user-visible changes and link to validation/known limitations.
8. Attach all assets before publication where the repository/platform supports draft release preparation.
9. Verify uploaded asset names and sizes/digests against local build outputs.
10. Publish only after every release gate passes, then verify the published release/tag/assets/attestation through GitHub itself.

### 14.2 Do not let a tag race ahead of tests

Review workflow triggers and dependencies. A `push` of a `v*` tag should not publish a Stable release after running only a small subset of the required release tests while other CI workflows can still fail. Either centralise all mandatory gates in the release workflow or implement reliable dependencies on the exact successful commit's gate results.

Prefer a draft-first process: build and verify all files, upload to a draft, verify the complete asset set, then publish. If immutable releases are enabled, respect their behavior and never design a workflow that relies on replacing assets after publication. Do not modify an existing stable release to force a passing result; create a new valid version if an actual post-release fix is required.

### 14.3 RC then Stable

- Build and publish a release candidate first (for example `v2.0.0-rc.1` with the package's corresponding valid pre-release version). The exact naming can differ, but tags, package metadata and release notes must be tested to remain consistent.
- Test the downloaded RC wheel in a new environment, not only the source tree.
- Run the same user journey and review the actual release notes, screenshots and known limitations.
- If a defect is found, fix it locally, run all affected/full local gates, push, await cloud gates, and make a new RC tag. Never mutate an existing tag to reuse its name.
- Once the RC is accepted with no open release-blocking defects and all gates green on the final commit, update final version/changelog, rerun the complete gates, merge if policy allows, and tag/publish `v2.0.0`.
- For Stable, ensure package version and release tag truly represent 2.0.0, not an RC version; inspect installed `importlib.metadata`/CLI/API versions.

### 14.4 Release asset verification

After publication:

- Fetch release metadata from GitHub and verify tag, target commit, title, notes and Stable/prerelease flag.
- Confirm the expected wheel, `SHA256SUMS.txt`, SBOM and provenance/attestation exist.
- Download each asset to a temporary directory and recompute SHA-256; verify checksums match.
- Verify build provenance/attestation using the documented official command when available.
- Install the downloaded public wheel in a fresh environment and repeat version/doctor/health/root-SPA and minimal workflow smoke tests.
- Verify the GitHub release page links to correct documentation, has no stale v1 text, and does not claim unsupported scientific capabilities.
- Record exact tag, commit SHA, workflow run URLs, asset hashes and smoke-test results in `docs/releases/v2.0.0.md` or a release verification report.

If GitHub permissions, branch protection or required human approval prevents the final publication, do not bypass it. Leave a fully tested candidate and precise instructions showing exactly what remains.

---

## 15. Final README, docs and GitHub repository polish — do this after implementation stabilises

Do not write promotional final documentation while the feature implementation is still changing. Keep internal engineering notes and tests up to date throughout development; perform the user-facing content pass only when the code and capability contract are stable. Then rerun all relevant final gates because docs, package version and workflow files can themselves introduce release errors.

### 15.1 README requirements

Treat the README as a reliable product entry point. It should be concise enough to scan while linking to detailed guides. Include, in a sensible order:

1. Original HCS Discovery Studio mark/wordmark with alt text and working relative paths.
2. Accurate product name and one-line description; brand line `Open science. Reproducible discovery. Made with ❤️ by hcsmedia.`
3. CI/security/license/version/release badges only when each badge target is real and correct.
4. A short, truthful capability summary distinguishing available, optional, planned and validated features.
5. A “what it is / what it is not” section, including scientific and non-clinical limitations.
6. Current genuine screenshots of the real app, with alt text and desktop/mobile representations.
7. A clean quickstart for the supported OS, exact Python/Node/tool prerequisites, copy-paste commands, first launch URL and a working demo workflow.
8. A clearly documented release-wheel installation path with the actual current filename/version and checksum/attestation verification.
9. The typical research workflow and sample CLI/API commands.
10. A readable architecture overview and links to architecture, node/plugin API, data model and workflow engine docs.
11. Reproducibility/provenance explanation and a real example artifact/manifest when safe and accurate.
12. Current CI/test commands and links to actual recent green workflow runs, not stale run IDs.
13. Security defaults, network-policy behavior, data privacy/telemetry behavior and how to report security issues.
14. Exact known limitations, supported platform/backend matrix, and unsupported GPU/engine claims.
15. Links to installation, quickstart, CLI, workflows, model/local-provider, scientific limitations, validation, contribution and troubleshooting docs.
16. License, citation, conduct, support/contribution and release links.

Use tables only where they improve comparison. Avoid huge walls of prose, empty sections, duplicated feature lists, broken badges, stale version numbers and “perfect/SOTA/industry-grade” marketing without scope-specific proof.

### 15.2 Screenshot and brand assets

- Generate screenshots only by running the actual final application with the final build and synthetic fixtures.
- Verify every markdown/HTML image path and case sensitivity. Keep assets reasonably sized and compressed without destroying legibility.
- Ensure SVGs are valid and safe; include accessible alt text for embedded images.
- Update the 1280×640 Open Graph/social preview only if it accurately reflects the final product. Verify dimensions/file size with a script. Do not make claims in the social card that are stronger than the code/benchmark evidence.
- GitHub README images should use repository-relative paths where appropriate; release/download links should point to actual releases. Do not use broken local paths or temporary screenshots.

### 15.3 Documentation reconciliation

Audit and correct every current doc against code and test evidence, including:

- `docs/engineering/IMPLEMENTATION_STATUS.md`;
- historical v1 gap analyses (preserve, mark historical, add a current v2 gap/plan instead of leaving stale content looking authoritative);
- `docs/developer-guide/TESTING.md`;
- scientific validation protocol and each actual report;
- security threat model and residual-risk list;
- architecture, workflow engine, data model and plugin API docs;
- Windows/Linux install and quickstart guides;
- CLI, workflows and local-model docs;
- component/license audit and dependency audit process;
- changelog, release notes, citation metadata and contribution guide.

Every table of test results must be based on the actual final runs. Historical test counts, CI URLs and package names must be clearly dated or updated. Unsupported or incomplete capability statements must be corrected everywhere, not only in the README.

### 15.4 GitHub metadata and open-source hygiene

Inspect repository settings and metadata where permissions allow. Recommend or configure (only where authorised and safe):

- short, accurate repository description;
- relevant non-spammy topics such as cheminformatics, drug-discovery, RDKit, reproducible-workflows, virtual-screening (only if supported);
- correct website/homepage if there is a real project page;
- GitHub About text and social-preview card;
- license, `CITATION.cff`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md` and issue/PR templates;
- Dependabot alerts/security updates, secret scanning and push protection where available;
- protected `main`, required CI checks and review/conversation-resolution rules where the owner/account plan permits;
- current CODEOWNERS entries for critical workflow/release/security files if appropriate;
- a release procedure that does not allow unreviewed or untested Stable publication.

Do not assume repository settings were changed merely because files documenting them were committed. If settings cannot be changed through available permissions, document the exact manual step and leave repository code safe by default.

### 15.5 SEO without keyword spam

- Use the actual project name and specific supported description in the title/head metadata.
- Ensure `apps/web/index.html` has a truthful title, concise description, correct favicon and social metadata if the deployed UI is shared on the web.
- Use meaningful headings, stable links, readable installation instructions, project topics and high-quality screenshots.
- Use relevant terms naturally: computational drug discovery, cheminformatics, RDKit, reproducible workflows, virtual screening and local-first research where accurate.
- Never keyword-stuff or imply unimplemented integrations, clinical use, benchmark leadership or GPU support to improve search placement.
- Check the built output and GitHub-rendered relative links rather than assuming metadata works.

### 15.6 Link and artifact verification

Run the existing docs-link checker and any frontend link validation. Verify internal anchors, README relative paths, badges, screenshots, releases, user guides, citations and official upstream URLs. Avoid indiscriminate crawling of sites that rate-limit or require credentials; for a failing external link, verify manually and distinguish a transient upstream issue from a genuinely broken target.

---

## 16. Full final acceptance checklist

Do not check an item until there is evidence. The checklist should be mirrored in the final engineering report and, if useful, in a release checklist file.

### Repository and implementation

- [ ] Actual v1 baseline and repository permissions inspected; working changes preserved.
- [ ] All P0 correctness defects fixed or explicitly blocked with evidence (no hidden P0 remains).
- [ ] Every shipped adapter has accurate capability status and documented requirements.
- [ ] Unknown node/config fields and invalid values fail early with actionable errors.
- [ ] API, UI, CLI and agent use the same business contracts.
- [ ] Queue, cancellation, cache, migrations and filesystem lifecycle are tested.
- [ ] No known critical security issue remains; residual risks are documented.
- [ ] No credentials, restricted data or accidental private output committed.

### Scientific correctness

- [ ] Descriptor correctness tests use fixed inputs and justified tolerances.
- [ ] Ranking/joins pass invariant/property tests.
- [ ] Docking path, if advertised runnable, has valid preparation/parser/integration tests and a documented evidence level.
- [ ] Property models/scores have accurate endpoint names, units, formulas/citations and limitations.
- [ ] Every published benchmark is real, reproducible, licensed, versioned and linked to its report.
- [ ] No unsupported SOTA/accuracy/experimental/clinical claims remain.
- [ ] Any unvalidated adapter is labelled accordingly in the UI, CLI, docs and report.

### Build and tests

- [ ] Lockfile current and dependency installs clean.
- [ ] Format, lint, type checks pass.
- [ ] Full backend/unit/integration/security suite passes.
- [ ] Scientific reference tests pass; long benchmark status is reported accurately.
- [ ] All required E2E tests pass without hidden flakiness.
- [ ] Visual QA screenshots were inspected at mobile/tablet/desktop widths and applicable themes.
- [ ] Accessibility, error/loading/empty states and core controls are verified.
- [ ] Wheel builds, installs and runs from an isolated environment.
- [ ] Supported Windows and Linux CI gates pass on the newest release commit.
- [ ] No failing/required job was skipped or softened merely to obtain green status.

### Cloud and release

- [ ] Exact source SHA has green required CI/security/package checks.
- [ ] PR/branch protection policies were followed; merge is verified.
- [ ] Release candidate was built and tested from a tag/commit.
- [ ] Stable version, tag, changelog and Python package version agree.
- [ ] README/docs/screenshots reflect final implementation and real final CI data.
- [ ] SBOM, checksum file and build provenance/attestation exist.
- [ ] Public assets were downloaded and their hashes independently recomputed.
- [ ] Public wheel smoke journey passed in a fresh environment.
- [ ] GitHub Stable release points at the intended final commit and has correct notes/assets.
- [ ] `v2.0.0` was not published until all the above were true.

---

## 17. Required final verification report

Only after all possible work is completed, write/update `docs/releases/v2.0.0.md` and an engineering verification record containing:

- final version/tag and exact full commit SHA;
- branch/PR/merge link and current `main` SHA;
- local OS/tool versions;
- exact local gate commands with passed/failed/not-run results;
- number of tests only if captured from actual test output;
- test/coverage/E2E/visual QA evidence links and screenshot paths;
- scientific benchmark names, dataset/version/licenses, commands, metrics, artifact links and limitations;
- supported OS/backends and explicitly untested configurations;
- exact cloud workflow run URLs and conclusions for the final SHA;
- public release URL and the asset list;
- wheel/SBOM/checksum hashes and provenance verification result;
- fresh-install/package smoke-test evidence;
- known limitations, incomplete non-blocking items and any permissions that remain outside the agent's control.

Use precise statuses: `PASS`, `FAIL`, `BLOCKED`, `NOT RUN`, `NOT APPLICABLE`. Do not present missing evidence as success. A summary like “everything is perfect” is not acceptable without a traceable evidence set; report the real outcomes.

### Completion message

When v2 Stable is genuinely published and verified, send a concise but complete final message with:

1. `v2.0.0` release URL and final commit SHA;
2. major improvements delivered;
3. exact local/cloud test-gate results;
4. scientific validation links and their scope;
5. wheel/SBOM/checksum/provenance verification;
6. remaining limitations or `None identified beyond the documented list` only if that is accurate.

If publication is blocked by required approval, permissions or a repository policy, state that exact blocker, link the ready PR/RC, show that all other work is completed, and provide the minimum owner action needed. Do not claim a Stable release exists unless GitHub confirms it.

---

## 18. Official references to consult during execution

Re-open current official docs when applying these practices; versions and GitHub UI may change.

- GitHub repository best practices: https://docs.github.com/en/repositories/creating-and-managing-repositories/best-practices-for-repositories
- GitHub secure use of Actions: https://docs.github.com/en/actions/reference/security/secure-use
- GitHub protected branches: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- GitHub immutable releases: https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases
- GitHub pull request standardisation: https://docs.github.com/en/pull-requests/reference/managing-and-standardizing-pull-requests
- AutoDock Vina documentation: https://autodock-vina.readthedocs.io/
- Meeko documentation: https://meeko.readthedocs.io/
- RDKit documentation: https://www.rdkit.org/docs/
- Chemprop repository/docs: https://github.com/chemprop/chemprop
- MoleculeNet paper: https://pubs.rsc.org/en/content/articlehtml/2018/sc/c7sc02664a

These references guide engineering decisions but do not substitute for tests against this repository.

---

## Final instruction

**Execute the entire lifecycle autonomously, in order, using real evidence. Build and fix locally first; prove the code and live UI locally; only then push. After each push, iterate on actual cloud failures until the newest commit is green. Once the implementation is stable, reconcile the README and all documentation with the actual code, run the final gates again, validate the release candidate, publish v2.0.0, download and verify its assets, and only then report completion.**

Do not stop at planning, do not ask routine questions, do not claim a step was completed when it was merely attempted, and do not bypass a safety, scientific, repository or permission gate to force a one-shot success.
