# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.1] - 2026-11-04

`v3.0.0` was tagged after its gates passed, but the release workflow failed before
publishing anything: the macOS x64 binary job could not install `rdkit==2026.9.1`,
which ships no macOS x86_64 wheel. No release, draft or asset was created for
`v3.0.0`, and the tag stays in place — this repository never moves a tag. `3.0.1` is
the first published 3.0 release.

### Fixed

- The release matrix no longer claims macOS x64. Supported release targets are
  Windows x64, Linux x64 and macOS arm64; the workflow states the RDKit wheel
  constraint instead of failing at install time.

## [3.0.0] - 2026-11-04

The first major release since `2.0`: exact similarity search that prunes, provenance
that other tools can read, an MCP server on the current specification, a property
benchmark that is measured instead of asserted, and release artifacts for every
desktop platform. Nothing in this list is claimed without a test, a generated report
or a command in the log.

### Added

- **Bound-pruned exact k-NN.** `TanimotoIndex.knn_hits` walks the library by
  popcount proximity, takes the running k-th score as a lower bound and only scores
  rows that can still reach it. It is staged into few large dispatches because a
  ring-per-dispatch version measured 14× slower than a full scan. Differential
  tests (including ties) prove the ranking equals the full scan. Measured on the
  synthetic clustered library: 6.0× faster at 100k, 3.9× at 500k; on an unclustered
  library it is 0.85×, which the report states. CLI/API/MCP use it whenever a full
  score vector is not requested.
- **Batched multi-query kernel.** `gpu/kernels/tanimoto_batch.wgsl` scores 16
  queries per library upload; `TanimotoIndex.search_many` returns one ranked result
  per query and verifies every count against the CPU reference. Kernel-level measured
  10.9× (100k) and 9.7× (500k) over the per-query path; the CLI's verification pass is
  extra. New `hcs-discovery similarity screen --queries … --file …`.
- **RO-Crate export.** `report export --format ro-crate` (CLI), `GET
  /api/v1/runs/{id}/export/ro-crate` (API) and a button in the run monitor write a
  ZIP with `ro-crate-metadata.json` (RO-Crate 1.1 context), W3C PROV terms, the
  software/environment record and every artifact with its SHA-256. A missing
  artifact aborts the export instead of producing a crate that points at nothing.
  It does not claim the Workflow Run RO-Crate profile, because the per-step
  `CreateAction` fields are not emitted yet.
- **MCP `2026-07-28` (dual-era).** `server/discover`, per-request version checks
  with `UnsupportedProtocolVersionError` (`-32022`), `resultType: "complete"`,
  `ttlMs`/`cacheScope` on list results, deterministic tool order, annotations and
  `structuredContent`. The legacy `initialize` handshake and `ping` are still
  answered for older clients, and the tests cover both eras.
- **Delaney ESOL report.** The shipped four-descriptor equation is now measured on
  the full 1,128-molecule Delaney set: RMSE 1.099, MAE 0.844, R² 0.725, held-out
  scaffold split RMSE 1.201 / R² 0.640, with a constant baseline and bootstrap CI.
  The 45-molecule stress set (R² 0.07) stays published next to it; the model
  metadata carries both. `scripts/science/validate_esol_delaney.py --check` fails
  if a dependency upgrade changes the numbers.
- **Latency metrics.** `hcs_run_duration_seconds` and
  `hcs_node_duration_seconds` histograms and `hcs_node_cache_hits_total`, all from
  persisted timestamps, so a scrape after a restart still reports what ran.
- **PostgreSQL against a real server.** `scripts/ci/run_postgres_tests.py` starts a
  pinned `postgres:16-alpine` container and runs migrations, a full workflow, four
  workers racing one claim (exactly one wins), API readiness and stale-lease
  recovery. New CI job `postgres` and gate `G16`.
- **Lighthouse budgets.** `apps/web/scripts/check_lighthouse.mjs` measures the static
  workspace and offline lab: 97/98 performance, 100 accessibility, LCP 2.3 s/1.8 s,
  CLS 0/0, TBT 91/52 ms. Accessibility and CLS are hard budgets; paint timings also
  have a catastrophic floor and an advisory target because host load moves them by
  more than 3×. Gate `G17` and CI job `lighthouse`.
- **Platform release matrix.** Release builds now produce one-file binaries for
  Windows x64, Linux x64, macOS arm64 and macOS x64, publish the container image to
  GHCR and smoke-test it, and attest every artifact. PyPI stays gated behind
  `PYPI_PUBLISH`.

### Changed

- The run monitor's report row gains the RO-Crate export; the timeline is committed.
- `IMPLEMENTATION_STATUS.md`, `README.md` and the roadmap are reconciled with the
  actual `3.0.0` tree (the status page had been three releases behind).
- Version strings in `pyproject.toml`, `__init__.py`, `package.json`,
  `package-lock.json`, `constants.ts` and `CITATION.cff` now agree.

### Fixed

- `HCS_DATABASE_URL` did nothing: the setting was named `database_url_override`, so
  pydantic-settings only read `HCS_DATABASE_URL_OVERRIDE` while every document told
  operators to set the former. A hosted instance silently stayed on SQLite. Both
  spellings are accepted now, with regression tests.
- A stray inline `border` declaration in the timeline CSS.
- `similarity search --k` no longer computes a full score vector it does not need.

## [Unreleased]

### Added

- **`select.sat` workflow node.** Chooses at most `k_max` rows so every group value
  is covered at least `min_per_group` times, using the dependency-free DPLL solver.
  It is a constraint decision, not a ranking: with `on_infeasible: fail` (the
  default) an impossible budget fails the node with the solver's reason instead of
  writing a plausible subset; `mark` writes all-false rows with that reason. The
  output is `sat_selected` plus `sat_reason`, and rows are never dropped. Covered by
  eight node tests (coverage, budget conflicts, ungrouped rows, determinism).
- **Run timeline in the UI.** The run monitor shows where the time went, built only
  from persisted timestamps: a queue segment, one row per executed node with its
  measured duration, and a `cache` marker for node-cache hits. A segment without a
  recorded start is left out instead of estimated. The end-to-end run test asserts at
  least four segments, and the component is covered by the axe gate.

## [2.2.1] - 2026-11-03

No application code changed. `v2.2.0` was tagged after its gates were green, but
the release workflow failed before publishing anything: the publish job pinned
`actions/download-artifact` to a commit that does not exist in that repository
(`3d3c42e5…`, labelled v7.0.1; the v7 line has no such tag), so GitHub could not
resolve the action. No release, draft or asset was created for `v2.2.0`, and the
tag is left in place rather than moved — this repository never reuses a tag.

### Fixed

- `release.yml` pins `actions/download-artifact` to the resolvable v7.0.0 commit
  (`37930b1c…`) matching the `actions/upload-artifact` v7 line the workflow
  already uses.

## [2.2.0] - 2026-11-03

The hosted deployment now runs the whole workbench: the SPA **and** `/api/v1`
from one Vercel project, with a real computed demo workspace. Local behaviour is
unchanged — every new switch is off by default.

### Added

- **Hosted parity: the full application on Vercel.** The FastAPI app is deployed
  as a Vercel Function next to the SPA, from the root `app.py` entrypoint. The
  blocker recorded in `ROADMAP_TO_V2_STABLE.md` (561 MB bundle against a 500 MB
  Python limit) is resolved by Vercel's Large Functions beta
  (`VERCEL_SUPPORT_LARGE_FUNCTIONS=1`, up to 5 GB). Verified on the deployment:
  `/api/v1/health`, `/api/v1/ready`, `/api/v1/projects` returning a seeded demo
  project with 16 compounds and a computed triage run, the SPA shell for `/` and
  `/lab`, and a workflow submitted over HTTP finishing `succeeded` in 2.1 s.
- **`HCS_DATABASE_URL`.** Any SQLAlchemy URL can replace the SQLite default, so a
  hosted instance can point at PostgreSQL. The optional `postgres` extra uses
  `pg8000` (BSD-3-Clause) because `psycopg` is LGPL and would fail the license
  gate. Engine caches are now keyed by URL instead of by data directory, so two
  database URLs in one process cannot share an engine. `public_dict` reports
  `database_backend` and never the URL itself. The URL and engine layer are
  unit-tested; a deployment against a real PostgreSQL server is **not** yet
  exercised and is not claimed.
- **`HCS_RUN_MODE=inline`.** On a serverless host no worker thread survives the
  response, so the submitting request claims exactly the run it created and
  executes it through the normal `Worker`. `queue` remains the default. A run
  that is still unfinished when the request ends stays claimable, and the
  existing lease recovery retries it; the mode is documented as a preview
  mechanism, not a replacement for a real worker.
- **`.vercelignore`.** The CLI previously uploaded local runtime data; a deploy
  failed on a disappearing `.e2e-data` SQLite file.

### Changed

- `rdkit.Chem.Draw` is imported lazily. It links against
  `libXrender`/Cairo, which the Vercel Python image does not ship; the eager
  import made **every** API route fail with `FUNCTION_INVOCATION_FAILED`. A
  missing drawing stack now returns a structured `424 missing_dependency` from
  the depiction endpoint only; descriptors, similarity and ranking are
  unaffected.
- The Vercel entrypoint puts `src/` on the import path, because the runtime
  installs the declared dependencies but not the project itself in a `src`
  layout.
- `vercel.json` uses the Python runtime instead of `framework: vite`: the SPA is
  served by the function's existing catch-all route, so the security headers,
  CSP and auth middleware apply to it. `maxDuration` is 300 s and
  `apps/web/dist` is included in the bundle.

### Fixed

- The engine/session caches no longer collide when a process serves more than one
  database URL.

## [2.1.0] - 2026-11-03

`2.0.0` was prepared as a release candidate and never tagged or published. This is
the first published version after it; it contains the GPU similarity engine, the
offline browser lab, the similarity API, the MCP server, the SAT solver, the
container image and the service worker described below.

### Added

- **Offline lab: the workbench without a backend.** `/lab` imports CSV/SDF/SMI,
  computes descriptors with RDKit WebAssembly, applies the same triage rules and
  the same weighted composite ranking as the server template, scores Tanimoto
  similarity through the shared WebGPU kernel (or the labelled CPU reference) and
  keeps the stored copy in IndexedDB on the device. The Playwright suite runs it
  against a static build with no API server, at 360 px, including a reload to
  prove persistence and a delete that really deletes.
- **Similarity API.** `POST /api/v1/similarity/search` and
  `GET /api/v1/similarity/engines` expose the same `hcs.similarity-search.v1`
  payload as the CLI, with structured 404/validation errors and no silent CPU
  fallback when `engine="gpu"` cannot be satisfied.
- **MCP server.** `hcs-discovery mcp serve` speaks JSON-RPC 2.0 over stdio with
  five read-only tools (`hcs_doctor`, `hcs_similarity_search`, `hcs_gpu_bench`,
  `hcs_workflow_validate`, `hcs_models_list`). No new runtime dependency; a
  scripted subprocess test asserts that stdout carries protocol messages only.
- **Hybrid GPU+CPU similarity boost.** `--boost auto|gpu|cpu|hybrid` splits the
  library between the GPU and CPU threads. `auto` turns the split on only when a
  calibration on the live library shows the CPU share can keep up; otherwise it
  stays GPU-only and says so. Measured 1.03–1.09× over the GPU upload path here.
- **SAT solver and constraint selection.** `hcs_discovery/sat.py` is a
  dependency-free DPLL solver with watched literals, unit propagation, pure
  literal elimination and deterministic branching. `hcs-discovery sat solve`
  reads DIMACS (exit 5 = unsatisfiable); `sat select` chooses at most k candidates
  covering every group, using a sequential-counter cardinality encoding. Tested
  against brute force on 40 random 3-SAT instances, pigeonhole UNSAT and unit
  chains.
- **Container image.** Multi-stage `Dockerfile` (Node build, slim Python runtime,
  non-root, healthcheck), `.dockerignore` and `docker-compose.yml`; verified by
  building, starting, and running a similarity search plus `sat select` inside it.
- **SEO and i18n documentation.** Per-route titles, descriptions, canonical and
  Open Graph tags, JSON-LD `SoftwareApplication`, `robots.txt` and `sitemap.xml`,
  plus zero-to-hero guides in English, German and French. A Playwright spec checks
  the metadata on a static build and the real 404 page.
- **Hourly autonomous wake-up.** `scripts/ops/hourly_wakeup.ps1` continues this
  session with a timestamped prompt under a lock, refusing to start with unmerged
  paths; `install_hourly_task.ps1` registers the Windows scheduled task.
- **Offline after the first visit.** A dependency-free service worker caches the
  shell and, on first use, the RDKit WebAssembly module. Navigations are
  network-first (a deployment is picked up immediately, an offline reload falls back
  to the cached shell), hashed assets are cache-first, and `/api/` is never cached.
  The first visit hands the worker its own boot URLs, because a worker cannot
  intercept the requests that loaded it. Verified by killing the static preview
  server and reloading: shell, bundle, WASM, IndexedDB copy and similarity all still
  work. A web app manifest makes it installable where the browser supports it.
- **Accessibility gate and bundle budget.** `e2e/a11y.spec.ts` runs axe-core
  (WCAG 2.0/2.1/2.2 A+AA) over seven routes; serious and critical violations fail
  the suite. It found three real defects, now fixed: inline links that relied on
  colour alone (1.4.1), and two scrollable regions without keyboard access (the
  environment table and the citation block). `scripts/ci/check_bundle_budget.mjs`
  fails the build when the gzipped JS/CSS exceeds 210/16 kB, and runs in the gate
  runner and CI.
- **Metrics endpoint.** `GET /api/v1/metrics` exposes a small Prometheus text
  exposition (build info, uptime, projects/datasets/compounds, runs by status,
  queue depth, cache entries and bytes, fingerprint-cache size, GPU availability).
  No dependency, no paths, no tokens, no per-request labels; it follows the same
  bearer-token rule as the rest of `/api/v1`. Traces and dashboards are still
  absent and listed as such.
- **Dataset fingerprint cache.** Packed Morgan fingerprints are stored once per
  dataset (`dataset_fingerprints`, migration `b7d21c4f9a03`) with a checksum over
  the compound set and one over the packed bytes. A repeated similarity search no
  longer re-fingerprints the library; a changed dataset or a truncated blob is
  detected and rebuilt instead of returning scores for the wrong rows. The API
  payload reports `fingerprints.cached` and the checksum, and the metrics endpoint
  exposes `hcs_fingerprint_cache_entries` / `hcs_fingerprint_cache_compounds`.
  Measured on a synthetic 5,000-row library: 656.9 ms to fingerprint, 15.3 ms to
  read the cached matrix (43×), checksums verified on every call
  ([report](docs/validation/fingerprint-cache.md)).
- **BitBound prefilter for threshold searches.** A fingerprint whose popcount bound
  `min(a,b)/max(a,b)` cannot reach the requested threshold is skipped without a
  comparison; only the candidates are scored. The hits are proven identical to a
  full scan by differential tests (0.0–1.0 thresholds, ties, duplicates) plus a
  bound-is-an-upper-bound property test. On the synthetic density-varied library it
  skips 32–88 % of the rows; on a uniform-density library it skips almost nothing,
  and the benchmark report states both. CLI, API and MCP expose the prefilter only
  where no per-row score list is requested, and `prefilter.enabled` says which path
  ran.

- **Targets and structures with provenance (API + CLI).** The reserved `targets`
  and `structures` tables now have services, versioned routes
  (`/api/v1/projects/{id}/targets`, `/api/v1/projects/{id}/structures`) and a
  `hcs-discovery target` command family. Structure import stores the exact bytes,
  records their SHA-256 and license, and reports an inspection built without new
  dependencies: chains, residues, missing-residue gaps, ligand types, waters,
  ions, alternate locations and warnings. mmCIF is refused with
  `unsupported_format` instead of being partially parsed.
  Additive migration `9f3c1a7d2b48` adds `structures.license`; an existing
  database upgrades with its rows intact and `license='unknown'` rather than a
  guess.
  Deleting a target keeps its structures and detaches them; deleting a structure
  removes the row and the file. No UI page yet, and no binding-site definition or
  receptor preparation.
- **HAEL adaptive scheduler (experimental, library only).**
  `src/hcs_discovery/hael/` implements the HCS Adaptive Evidence Ladder: typed
  evidence with unit/endpoint/calibration gates, an acquisition rule
  `(EHVI + λ·EIG + ν·ΔDiversity) / (C + ε)`, a measured-only cost model and a
  deterministic, auditable decision trace. 94 unit and property tests pin the
  rules that matter (dimensional integrity, gate integrity, cost and information
  monotonicity, diversity, determinism, budget, failure recovery, auditability).
  It is **not** wired into a workflow, has no API/CLI/UI, supports at most two
  objective dimensions and has no evaluation on a real task, so it stays
  `experimental` and is never a default. Design, ablation and limits:
  `docs/research/HAEL.md`.
- **Research register.** `docs/research/RESEARCH_REGISTER.md` records each open or
  answered research question with its evidence, including negative results.
- **Hosted preview on Vercel.** A `vercel.json` build, a root `app.py` entrypoint
  and `src/hcs_discovery/demo.py` serve a disposable demo workspace
  (`HCS_DEMO_MODE=true`): the instance imports the checked-in synthetic library
  and runs the triage template through the real worker. State lives in `/tmp` and
  is disposable by construction, and seeding refuses to overwrite a real project.
  This is a preview, not a production service.
- **Unified gate runner and generated documentation numbers.**
  `scripts/gates.py` mirrors `.github/workflows/ci.yml` (gates G0–G14) and writes
  `build/gate-report.json`, so "green locally" and "green in CI" mean the same
  thing. `scripts/ci/check_doc_claims.py` owns the measured test and coverage
  numbers (`docs/engineering/evidence.json`) so the README, implementation
  ledger and release evidence can no longer drift from the build.
- **Browser capability detection (WebGPU / WebAssembly).** The Settings page
  reports, client-side, whether the browser exposes WebGPU and WebAssembly —
  hardware presence only, mirroring the backend Vulkan probe. No scientific
  engine executes through the browser in this release.
- **GPU similarity search with an exact CPU reference.** The shared WGSL kernel
  (`src/hcs_discovery/gpu/kernels/tanimoto.wgsl`, the same file the browser uses)
  is now reachable from the product:
  `hcs_discovery.similarity.TanimotoIndex` scores a query against a library with
  k-nearest and threshold semantics, chunking above the storage-buffer limit and
  a resident-library mode. Integer popcounts are compared against the CPU
  reference on every verified search, so an accelerated run cannot silently
  differ; similarity is `intersection / union` in float64, bit-identical to
  RDKit's `TanimotoSimilarity`.
  `chem.similarity` gains `engine: auto | cpu | gpu` (recorded in a run event and
  in the cache runtime fingerprint), and `hcs-discovery similarity search`
  scores `.smi`/`.csv`/`.sdf` files from the CLI. `scripts/science/
  benchmark_gpu_similarity.py` generates
  [`docs/validation/gpu-tanimoto.md`](docs/validation/gpu-tanimoto.md): exact
  parity, 500k fingerprints in ≈5 ms with the library resident (≈100 M
  Tanimoto/s, ≈19× RDKit's bulk call) on this host's integrated AMD GPU.
  Scope is stated in the same document: whole-library scan, radius-2/2048-bit
  Morgan fingerprints only, no GPU fingerprint generation.
- **Browser compute is exercised, not just detected.** The Settings page runs
  RDKit WebAssembly (parse, descriptors, SVG depiction) and the WebGPU Tanimoto
  kernel against a JavaScript CPU reference. Both are covered by Playwright
  against the served application, and the WebGPU path reports parity before any
  timing.
- **SOTA gap analysis.** `docs/research/SOTA_GAP_ANALYSIS.md` records what the
  public state of the art does in similarity search, ADMET, structure prediction
  and browser compute, what this repository actually does, and what remains
  missing.

### Fixed

- **The application CSP blocked its own browser chemistry.** `script-src 'self'`
  rejected both `WebAssembly.instantiate` and Emscripten embind's generated
  bindings, so the RDKit WebAssembly panel could never have run in the served
  app. The CSP now grants `'wasm-unsafe-eval'` and `'unsafe-eval'` with no remote
  script source, and a Playwright test runs the self-test against the real
  server so the regression cannot return unnoticed.
- The About page "Limitations register" claimed docking, ADMET and structure
  prediction were all absent and that there were zero remote connectors. It now
  distinguishes Vina docking (host-dependent) and the reduced ESOL / CNS-MPO
  estimates (approximate) from the still-planned MD, learned ADMET and structure
  prediction, and reports the two policy-gated data connectors (PubChem,
  ChEMBL).

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
- **`workflow run --no-follow` and `run retry --no-follow` exited 1 after a
  successful submission** in human (non-`--json`) mode and told the user it was
  "Waiting for a worker". They now report the queued run, name the command that
  executes it, and exit 0. Following a run with no worker running also prints a
  one-time hint instead of looking hung.
- **The compound-library search field had no instantaneous focus indicator:** the
  input sets `outline: none` and the wrapper's ring was tied to a 140 ms
  `box-shadow` transition, so keyboard focus was not signalled at once (WCAG 2.2
  focus appearance). Only the resting border animates now.

- **Docking redocking gate:** `scripts/science/redock_vina_reference.py`
  redocks imatinib into PDB 1IEP using the official Vina example files
  (Apache-2.0, pinned and hash-checked) and the product's own preparation,
  with the Vina authors' preparation as a control. The new CI job
  `science-vina` downloads the pinned Vina 1.2.5 Linux binary, runs the live
  Vina tests (failing instead of skipping) and requires the top pose within
  2.0 Å of the crystal pose for every seed.
- PubChem lookups returned no structures: PubChem renamed `IsomericSMILES`
  and `CanonicalSMILES` to `SMILES` and `ConnectivitySMILES` in 2025, and the
  connector read the old keys. Both names are now read, and every PubChem and
  ChEMBL record carries a `structure_check` that recomputes the InChIKey from
  the returned SMILES. An opt-in `network` test guards against the next rename.
- Connectors enforce the network policy even with a test transport, require
  HTTPS and a JSON content type, cap the payload while streaming and honour a
  capped `Retry-After`. Network tests are excluded from the default suite.
- Agent runs are bound to the reviewed plan digest (`approved_plan_hash`, CLI
  `--plan-digest`) and each plan runs at most once, claimed atomically before
  any side effect. The CLI could previously not run a plan with more than one
  step.
- Concurrent writers of the same node-cache key could expose or delete a
  half-written entry; entries are now staged and renamed into place.
- An outer `table.join` dropped right rows with a missing key; they are now
  kept, unmatched keys are logged, and a join node with fewer than two inputs
  is rejected before queueing.
- Standardisation no longer turns arbitrary exceptions into warnings (only
  RDKit chemistry errors), and reports neutralisation or tautomer changes only
  when the structure actually changed.
- ESOL flags charged and multi-component inputs as outside its domain
  (model 1.2.0; predictions unchanged).
- Windows device names (`COM0`, `COM¹`, `CONIN$`, `NUL .txt`, …) are
  neutralised in file names.
- `docking_rmsd_lb/ub` no longer present themselves as ranking objectives;
  Vina measures them against its own best mode, so they are 0 for the best pose.
- Text contrast now meets WCAG AA in both themes (muted, faint, accent and
  status colours), page-level error views have an `h1`, and plot points show a
  clear keyboard focus ring.
- The wheel smoke test also runs on Windows and checks migrations and `/ready`.

### Validation

- Vina redocking, 1IEP, Vina 1.2.5 on Windows 11, 5 seeds: HCS preparation top
  pose 0.42–0.94 Å, Vina-example control 0.29–0.37 Å
  (`docs/validation/vina-redocking-1iep.md`).
- Extended visual QA: 16 routes × 320/390/640/768/1280/1440 px × light/dark,
  192 captures with no findings for overflow, names, contrast, headings and
  keyboard focus.
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
- Agent `run` requires `--plan-id` (CLI) or `plan_id` (API), plus an
  approval. The CLI takes `--plan-digest` instead of `--tool`/`--args`, and a
  plan cannot be run twice.
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
