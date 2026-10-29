# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet.

## [2.0.0] - 2026-10-29

Hardening release. This version makes correctness claims match observable
behaviour: integrity checks fail closed, scientific metrics are measured rather
than asserted, and several silent-fallback paths were removed. Some of these
changes reject previously accepted inputs, so the major version bump is
intentional.

### Added

- **Content- and artifact-verified cache:** Cache entries now record the table
  content hash and the SHA-256 of every artifact. A missing or tampered artifact
  is a cache miss and forces a re-run; partial entries are refused.
- **Lease heartbeats:** Long-running nodes renew their queue lease in the
  background. A worker that loses its lease raises `LeaseLostError` and can no
  longer write terminal run state.
- **Docking outcome columns:** `dock.vina` writes `{prefix}_status` and
  `{prefix}_error` for each ligand, distinguishing `docked`, `no_pose`,
  `invalid_input`, `ligand_preparation_failed` and `docking_failed` instead of
  aborting the whole run on one bad ligand.
- **Persisted agent plans:** Agent plans are stored under `data_dir/agent_plans`
  with a digest. `agent run` requires a `plan_id`, and every approved call must
  match the planned tool and arguments exactly.
- **SQL-backed results pagination:** Result counting, filtering, sorting and
  pagination now run in SQL, including JSON metric sorts, with deterministic
  `RunResult.id` tie-breaking and NULLs last in both directions.
- **ESOL validation report:** A checked-in, reproducible 45-molecule benchmark
  derived from AqSolDB's curation of the Llinas et al. (2008) Solubility
  Challenge, with per-molecule predictions and a bootstrap confidence interval
  in `docs/validation/esol-solubility.md`.

### Changed

- **Strict configuration:** Every workflow node config and agent tool payload
  rejects unknown fields (`extra="forbid"`), so a typo can no longer be silently
  ignored.
- **Constraint objectives are eligibility gates:** Rank nodes force constraint
  weights to zero, exclude constraint objectives from composite scores and the
  Pareto front, and expose `constraint_pass` / `constraint_reasons` columns.
- **Safe joins:** `table.join` rejects duplicate right-side keys and suffix
  collisions with `ValidationError` instead of duplicating rows or overwriting
  columns.
- **No silent redirects:** Connectors reject 3xx responses, raise on 404 unless
  `allow_not_found=True`, require a JSON object, and normalise allowlisted hosts
  against case, trailing dots, ports and IDNA lookalikes.
- **Honest engine probes:** Vina availability requires exit code 0 and a
  recognisable version string. `ENGINE_VERSION` is no longer fabricated when the
  binary cannot be verified.
- **Honest ESOL metadata:** Fabricated scaffold-test metrics were removed. The
  model now publishes measured independent-challenge metrics (n=45, RMSE 0.968,
  R² 0.072, mean-baseline RMSE 1.004) and states that its uncertainty column is a
  heuristic error scale, not a calibrated confidence interval.
- **Version surfaces:** Python package, React SPA, `CITATION.cff` and release
  documentation now report `2.0.0`.

### Fixed

- Server-Sent Events log streaming now stops when the client disconnects
  instead of holding a worker and database session open.
- Malformed connector JSON responses become `ValidationError` instead of
  leaking parse exceptions.
- A cache hit can no longer be reported as `succeeded` when its artifact is
  missing or modified.
- Docking input failures are recorded per ligand rather than masking the
  remaining library.
- Node cache keys now include a fingerprint of the installed package (so edits
  to helper modules or model coefficients invalidate cached results), the
  AutoDock Vina version actually detected on the host and the SHA-256 of the
  docking receptor. Previously a replaced receptor file reused stale poses.
- Installed wheels ship their Alembic migrations and record a revision instead
  of falling back to `create_all`.
- **Docking ligands were rigid.** Ligand PDBQT files put every atom in `ROOT`
  with no `BRANCH` records, so Vina never sampled torsions despite the
  `TORSDOF` line. Preparation (`hcs-pdbqt-1`) now builds a real torsion tree
  with Meeko's default conventions: non-polar hydrogens merged, AutoDock 4 atom
  types on the original aromaticity, rigid rings and amides, graph-centre root.
  On the 51 fixture ligands it matches Meeko 0.8.0 for torsion count, atom count,
  root size, atom types and charges in 48 cases; the other 3 contain 7+-membered
  rings that are kept rigid here (see `docs/validation/ligand-prep-meeko.md`).
- Ligand preparation no longer swallows MMFF94 or Gasteiger failures. Undefined
  charges and unsupported elements are per-ligand errors; skipped optimisation,
  random-coordinate embedding, salt stripping and rigid macrocycles are reported
  in the new `{prefix}_prep_notes` column.
- **CNS MPO used invented inputs.** ClogD was cLogP − 0.5 and the "pKa" was
  7 + 1.5 × (nitrogens bearing H), which counted amides and anilines as basic
  and ignored tertiary amines; a fixed 0.25 "standard error" was reported and
  invented lower penalties were applied to cLogP and MW. The model (now v2.0.0,
  "CNS MPO approximation") uses Wager's six functions exactly, cLogP in place of
  ClogD, and an explicitly reported assumed pKa (9.0 aliphatic amines, 11.0
  amidines/guanidines) only when a basic centre is detected. It reports no
  uncertainty and is not described as a BBB-penetration probability.
- **Release workflow could publish untested or overwrite releases.** A tag ran
  only `pytest` before publishing and `--clobber` replaced assets of an existing
  release. Publication now requires successful CI and CodeQL runs for the exact
  tagged SHA, refuses existing releases, smoke-tests the installed wheel, and
  verifies assets in a draft before publishing; only the publish job has write
  permissions. See `docs/developer-guide/RELEASING.md`.
- Release candidate tags (`vX.Y.Z-rc.N`) now map to PEP 440 versions
  (`X.Y.ZrcN`); previously no candidate tag could pass the version check.
- **UI:** `Input`, `Select` and `Textarea` lost their base styling whenever a
  caller passed `className` (the spread props overwrote it). The editor's
  "Node ID" field had no accessible name. At 320 px, long local paths in the
  diagnostics and long SMILES/IDs in page headers caused horizontal scrolling.
  The workflow editor's node table hid its Edit/Delete actions behind a
  horizontal scroll at every width, and table action cells used `display: flex`
  on `<td>`, misaligning row borders.
- **Agent Ask mode hid provider failures.** When the configured LLM failed or
  was unavailable, the error was swallowed and a canned local answer returned as
  if nothing happened. Responses now carry `source` (`llm` or `local_rules`) and
  `provider_error`, and a fallback answer says that no language model answered.
  The local ESOL answer no longer claims atom contributions or leverage-based
  domain bounds.
- Docked pose SDF files now carry bonds, rebuilt from `REMARK SMILES` records
  that Vina copies into its output; previously they contained atoms only.

### Validation

- Visual QA (`apps/web/scripts/visual_qa.mjs`): 17 routes × 320/390/768/1280/1440
  px × light/dark against a synthetic dataset; 170 captures with no automatic
  findings after the fixes above, and the screenshots were reviewed by hand.

- Full local gates: Ruff format/check, mypy, pytest with coverage, frontend
  typecheck/build and Playwright end-to-end tests.
- ESOL independent challenge set: 45 measured compounds, RMSE 0.968 log10 units,
  R² 0.072, bootstrap 95% CI [0.708, 1.260]; the report is regenerated by
  `scripts/science/validate_esol.py` and verified by a regression test.

### Breaking changes

- Unknown node config or agent tool payload fields are rejected.
- `table.join` fails on duplicate right keys and suffix collisions.
- Agent `run` requires `--plan-id` (CLI) or `plan_id` (API).
- Connector 3xx responses are errors; 404s raise unless explicitly tolerated.
- Constraint objectives no longer contribute to composite scores or Pareto
  ranking; they gate eligibility instead.
- `cns_mpo_bbb` scores change (see Fixed) and its uncertainty column is empty.
- `dock.vina` reads receptors only from `<HCS_DATA_DIR>/receptors` (relative
  names resolve there). Absolute paths elsewhere, and resolution against the
  server's working directory, are refused unless
  `HCS_ALLOW_EXTERNAL_RECEPTOR_PATHS=true`, so an HTTP client cannot make the
  server read arbitrary host files.

## [1.0.0] - 2026-10-28

Production stable v1.0.0 release for Windows and Linux. Deliver working code, working user journeys, credible scientific validation, robust local CPU operation, DAG workflow branching, safe research assistance, authentic branding, and complete build provenance.

### Added

- **AutoDock Vina CPU Docking Adapter:** Integrated native CPU molecular docking workflow node (`dock.vina`) with automated RDKit 3D conformer embedding, MMFF94 force field optimization, Gasteiger charge assignment, AutoDock PDBQT atom typing, receptor bounding box validation, pose parser, and PDBQT-to-SDF conversion.
- **Learned Property Prediction:** Integrated Delaney (2004) ESOL aqueous solubility prediction with leverage-based uncertainty calibration and applicability domain detection, and Wager et al. (2010) CNS Multiparameter Optimization (CNS MPO) scoring for blood-brain barrier alignment.
- **Scaffold Splitting:** Added Bemis-Murcko generic scaffold extraction and leakage-free dataset splitting for cheminformatics model benchmarking.
- **Public Biological Data Connectors:** Added NCBI PubChem PUG REST and EMBL-EBI ChEMBL web services connectors with strict local-first network policy gating, rate limiting, and exponential backoff.
- **DAG Workflow Engine:** Added Kahn's topological sorting, fan-out branching, cycle detection, and key-based table joining (`table.join`) aligning multi-branch tables by compound identity.
- **Safe Agentic Research Assistant:** Implemented local research assistant (`hcs-discovery agent` / `/api/v1/agent`) supporting Ask (read-only Q&A), Plan (DAG formulation with schema validation), and Run (approved typed tool execution) modes with strict tool allowlist and prompt-injection isolation.
- **Report Table Truncation Disclosure:** Added prominent table truncation notices in Markdown (>200 rows) and HTML (>500 rows) reports with full complete exports available in CSV, JSON, and SDF formats.
- **Bounded Cache & Cascade Deletion:** Added cache lifecycle management (`cache prune --max-size-mb --max-age-days`) and complete cascade deletion of run artifacts and uploaded files.
- **Official Brand Assets:** Original vector mark (`hcs-discovery-mark.svg`), wordmark (`hcs-discovery-wordmark.svg`), and 1280x640 OpenGraph social preview card.

### Changed

- Replaced greedy Pareto front accumulation with Deb's Fast Non-dominated Sorting algorithm, guaranteeing dominance invariance under input permutations.
- Strengthened filter validation against non-finite thresholds and type mismatches.
- Upgraded package version to `1.0.0 Stable` across Python, React SPA, and documentation.

## [0.1.0] - 2026-10-28

First public preview. This release is an honest vertical slice, not a complete
drug-discovery platform. See `docs/engineering/IMPLEMENTATION_STATUS.md` for the
feature-by-feature status.

### Added

- Project, dataset, compound, workflow and run domain model persisted in SQLite
  through SQLAlchemy 2, with Alembic as the schema authority.
- CSV, SDF and SMILES import with row-level outcomes, duplicate retention,
  configurable standardisation (salt stripping, neutralisation, canonical
  tautomer) and SHA-256 file checksums.
- RDKit-backed descriptor calculation, Morgan/Tanimoto similarity, explicit
  rule filters, Pareto non-dominated sorting and a transparent weighted
  composite score.
- Lease-based local job queue with restart recovery, cancellation, per-node
  timeouts, a content-addressed node cache and at-least-once execution.
- Run manifests containing workflow snapshots, dataset checksums, engine and
  Python versions, hardware description, artifact checksums and limitations.
- Server-Sent Events run log streaming, run retry, artifact download and
  HTML/Markdown/JSON/CSV report export.
- React + TypeScript single-page UI covering workspace, project overview,
  compound library, compound detail, workflow library, visual workflow editor,
  run monitor, results explorer, model registry, data-source status, settings
  and about pages, with light/dark themes and a narrow-screen layout.
- Headless `hcs-discovery` CLI with project, dataset, compound, workflow, run,
  report, model, config, cache and database commands. `--json` works before or
  after the subcommand.
- Versioned `/api/v1` HTTP API with bearer-token enforcement for non-loopback
  binding, loopback-only CORS, request IDs, security headers, payload limits,
  rate limiting and a redacted error envelope.
- Local OpenAI-compatible LLM provider probe with a local-only network policy
  and an explicit opt-in for remote endpoints. No LLM feature is required for
  the CPU demo.
- Vulkan device probe that reports hardware presence only and never implies
  model support.
- Self-contained wheel that bundles the built SPA, so a `pip install` serves the
  UI without a Node toolchain.
- Backend test suite (82 tests), frontend typecheck/build, three Playwright
  end-to-end tests, Ruff and mypy gates, Alembic migration tests and security
  tests for redaction and network policy.
- GitHub Actions CI for Linux and Windows backend gates, frontend build and
  Playwright end-to-end tests, CodeQL analysis, dependency review, a license
  policy check and secret scanning. The pipeline is green on both operating
  systems, and the tag-triggered release workflow published `v0.1.0` as a
  prerelease with a CycloneDX SBOM, `SHA256SUMS.txt` and a verified
  build-provenance attestation.
- Apache-2.0 license, NOTICE, citation metadata, security policy, code of
  conduct, contribution guide and the documentation set required by the
  project brief.

### Fixed

- `uv sync` now works on a fresh checkout before the SPA is built. A Hatch build
  hook creates the missing `apps/web/dist` directory; release builds still
  compile the frontend before packaging.
- Narrow-screen tables no longer clip primary data. Secondary columns are hidden
  deliberately, identifiers ellipsize, card headers wrap their actions, and the
  settings environment table stacks label above value.
- Mypy no longer aborts on RDKit 2026.9.1's invalid bundled type stubs; the CI
  job removes only that stub package before type checking.

### Known limitations

- Docking, molecular dynamics, learned property prediction and structure
  prediction adapters are listed as `planned` and are not runnable.
- Workflows are linear single-input chains. Multi-input merge nodes are
  explicitly rejected by validation.
- The queue and database target a single local machine. There is no
  multi-tenant isolation, PostgreSQL deployment or distributed worker support.
- The LLM provider is a client and a registry entry, not an autonomous agent.
- No predictive-accuracy claim is made. The included validation protocol
  describes what would be required before such a claim could be made.
- There is no hosted service, telemetry, account system or cloud dependency.
