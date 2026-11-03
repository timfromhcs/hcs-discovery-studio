# Plan of record — zero-backend web app, containers, MCP and local acceleration

**Date:** 2026-11-03
**Branch:** `main` (follow-up work continues on `feat/zero-backend-workspace`)
**Status:** executing
**Owner:** hcsmedia

This plan supersedes the "browser compute" work packages in
[`ROADMAP_TO_V2_STABLE.md`](ROADMAP_TO_V2_STABLE.md) and extends the SOTA reading
in [`../research/SOTA_GAP_ANALYSIS.md`](../research/SOTA_GAP_ANALYSIS.md).

The ground rules are the ones this repository already uses, and they do not
change because the scope grew:

1. **No claim without a command.** Every "works" below names the test, gate or
   measurement that produced it.
2. **Honest degradation.** A weaker engine (CPU instead of GPU, low precision
   instead of float64, in-memory instead of persistent) is reported, never
   hidden.
3. **Local first, cloud second.** A capability is verified on this machine
   before it is deployed anywhere.
4. **No silent data loss.** Anything a user typed or imported either persists
   where the UI says it persists, or the UI says it does not.
5. **No invented SOTA.** Where the project is behind, the document says so.

---

## 1. Research digest (2026-11-03)

What the platform actually offers today, and what that means for the design.
Sources are listed in §8.

### 1.1 Vercel

| Constraint | Value | Consequence for this plan |
|---|---|---|
| Python function bundle (standard) | 500 MB | RDKit + SPA + migrations fit; the wheel already proves it |
| Large functions (beta) | up to 5 GB, Node/Bun/Python, opt-in via `VERCEL_SUPPORT_LARGE_FUNCTIONS=1`, Fluid compute only | The 561 MB backend is no longer fundamentally blocked — it can be attempted as an explicit experiment, not a promise |
| Function duration | default 300 s; up to 800 s with function config | Docking/MD do not belong in a function; keep the queue local or move to Workflows |
| Containers | OCI images run as Functions, stored in Vercel Container Registry, HTTP on an injected port, SIGTERM with 30 s grace | A `Dockerfile` gives one artifact for local, cloud container and "own machine" |
| Static deployments | SPA + rewrites, no server code | The zero-backend browser mode is the only way the demo works for a visitor without an account |
| Deployment protection | on by default for this project | Browser verification uses the CLI's development OIDC token as `x-vercel-trusted-oidc-idp-token`; protection is not disabled |

### 1.2 Browser runtimes

- **RDKit MinimalLib (WASM)** already ships in this repo and is the chemistry
  engine for the browser mode: parse, canonical SMILES, descriptors, SVG,
  Morgan fingerprints. It is 7.4 MB (2.4 MB gzip) and loads lazily.
- **WebGPU** runs the shared Tanimoto kernel with integer popcounts, so the
  result is exact rather than approximate. Measured parity is already in
  `docs/validation/gpu-tanimoto.md` and on the deployed site.
- **OPFS + SQLite WASM** is the mature persistence story (SQLite's own
  `opfs-sahpool` VFS needs no COOP/COEP headers; `opfs` VFS needs them).
  IndexedDB is the lower-risk fallback. Both are per-origin, per-browser
  storage — which is exactly "each user's data stays on their machine".
- **Pyodide** can run CPython in the browser, but pulling a 10–30 MB Python
  runtime to re-implement what RDKit WASM and NumPy-free TypeScript already do
  is not justified. Decision: no Pyodide.

### 1.3 Acceleration

- The GPU path is limited by three things today: it scans the whole library
  (no popcount bound), it uploads the library per search unless resident, and
  the CPU sits idle while the GPU works.
- A **hybrid split** (GPU on one chunk, NumPy on the remaining chunks in
  parallel worker threads, merged with a stable sort) converts idle CPU into
  throughput on integrated GPUs, which have modest compute relative to the
  core count. This is the honest "CPU boost that turns on automatically".
- **More kernels** pay off in this order: threshold prefilter by popcount
  bound, batched multi-query, then diversity selection (MaxMin). Descriptor
  computation on the GPU is not worth it (RDKit is already fast and the data
  transfer dominates).

### 1.4 SAT and constraint selection

A SAT solver is useful here for one concrete question: *choose a subset of
compounds that satisfies hard constraints* (cover each property bin at least
once, at most k compounds, no duplicates). A dependency-free DPLL solver with
watched literals and unit propagation is enough for library-sized instances
(hundreds to a few thousand clauses), testable against brute force, and it
keeps the install free of native SAT bindings. Full CDCL with clause learning
is a later optimisation, not a requirement for correctness.

### 1.5 Packaging and distribution

- `uv build` wheel works and is smoke-tested; the PyInstaller one-file
  executable works and is smoke-tested (including the GPU kernel).
- Publishes: `npm publish` for a small client package, `uv publish`/PyPI for the
  wheel are *prepared* but only executed with the owner's credentials. The plan
  includes the metadata, the `--dry-run` verification and the exact commands;
  it does not claim a published package until one exists.
- Docker: a multi-stage `Dockerfile` (uv → slim runtime) produces the same API
  the exe serves, with `HCS_DATA_DIR` as a volume.

---

## 2. Target architecture

```text
                        ┌─────────────────────────────┐
   phone / tablet ─────► │  Static SPA (Vercel / any   │  no backend
   desktop, offline     │  static host)               │  IndexedDB + RDKit WASM
                        │  • offline triage           │  WebGPU similarity
                        │  • local datasets + runs    │
                        └──────────────┬──────────────┘
                                       │ optional (same UI)
                        ┌──────────────▼──────────────┐
   desktop (full)  ───► │  Local server / exe / wheel │  SQLite, queue, worker,
                        │  FastAPI + CLI + MCP (stdio)│  docking, reports
                        └──────────────┬──────────────┘
                                       │ optional container
                        ┌──────────────▼──────────────┐
                        │  Docker image (Vercel VCR / │  same API, volume for
                        │  own machine)               │  HCS_DATA_DIR
                        └─────────────────────────────┘
```

One rule ties them together: **the browser pipeline mirrors the server rules and
says when it cannot**. Descriptor names, filter operators, ranking directions
and the Tanimoto metric are identical. Where the browser cannot match the server
(e.g. AutoDock Vina, MMFF), the UI says so instead of showing a plausible number.

---

## 3. Phases, tasks and acceptance gates

Each phase ends with: tests green, gate runner green (`scripts/gates.py`), a
changelog entry, and a docs update. Nothing is marked done in the README before
the gate ran.

### P1 — Zero-backend browser workspace (the "works without a server" ask)

- **P1.1 Import in the browser.** CSV/SDF/SMILES via file input and drag-drop;
  row-level errors kept visible; no upload, no network.
- **P1.2 Standardise + describe in the browser.** RDKit WASM: canonical SMILES,
  MW, cLogP, TPSA, HBD, HBA, rotatable bonds, rings, QED if available.
- **P1.3 Triage in the browser.** The same rule semantics as `filter.rules`
  (le/lt/ge/gt/eq/ne/between) and the same Pareto + weighted composite ranking
  as `rank.pareto`, implemented once in TypeScript and tested against fixture
  values produced by the Python implementation.
- **P1.4 Similarity in the browser.** Query SMILES against the imported library
  through the WebGPU kernel with the existing parity check; CPU reference
  fallback, labelled.
- **P1.5 Persistence.** Datasets and runs in IndexedDB, with an explicit
  "stored on this device only" statement, export/import of a run as JSON/CSV,
  and a delete action that actually deletes.
- **P1.6 Phone layout.** 390 px and 360 px layouts, touch targets ≥ 44 px, no
  horizontal scrolling; verified by Playwright viewport tests and screenshots.
- **P1.7 Offline.** Service worker caches the shell and the WASM module; the
  app opens with the network disabled and reports what is unavailable.

**Gate:** Playwright runs the whole flow against the **static** build with no
API server (a static file server), at 390 px and 1440 px, and asserts: rows
imported, filter counts, ranking order, similarity parity, persistence after
reload, and zero `/api/v1` requests.

### P2 — API parity for similarity

- `POST /api/v1/similarity/search` (dataset id + query + k/threshold + engine),
  `GET /api/v1/similarity/engines` (probe + supported fingerprint), OpenAPI
  schema, error envelopes.
- **Gate:** API tests for success, invalid SMILES, unknown dataset, engine=gpu
  without adapter (structured error, no fallback), and parity with the CLI
  payload (`hcs.similarity-search.v1`).

### P3 — MCP server (stdio, dependency-free)

- `hcs-discovery mcp serve` speaks JSON-RPC 2.0 over stdin/stdout:
  `initialize`, `tools/list`, `tools/call`, `ping`. Tools: `hcs_doctor`,
  `hcs_similarity_search`, `hcs_gpu_bench`, `hcs_workflow_validate`,
  `hcs_models_list`.
- Read-only by default; no shell execution; every tool returns the same payload
  as the CLI, with `isError` on structured failures.
- **Gate:** a scripted client test drives a full session; unknown tools and bad
  arguments produce JSON-RPC errors, not crashes; no stdout pollution.

### P4 — Hybrid CPU+GPU boost, automatically

- `TanimotoIndex(boost="auto")`: on a hardware adapter, split the library into a
  GPU chunk and N CPU chunks (N = min(4, cpu_count-1)), run concurrently
  (`ThreadPoolExecutor`; NumPy releases the GIL in the popcount path), merge in
  library order. `boost="cpu"`/`"gpu"` pin one engine; `"auto"` picks hybrid
  when the adapter is an integrated GPU and the library is large enough,
  otherwise the faster single engine.
- CLI `similarity search --boost auto|cpu|gpu|hybrid`; the JSON payload reports
  `engine.mode` and the per-engine timings so the merge is auditable.
- **Gate:** bit-exact equality between all modes on the same library; a
  benchmark row showing hybrid vs GPU-only; a test that disables threading and
  still gets exact results.

### P5 — SAT-based constraint selection

- `hcs_discovery/sat.py`: DPLL with watched literals, unit propagation, pure
  literal elimination, deterministic variable order; CNF from a small builder;
  `solve()` returns a model or `Unsatisfiable`.
- `hcs-discovery sat solve --cnf file.dimacs` and a `select` mode that encodes
  "cover each property bin, at most k compounds, one compound per bin-slot".
- **Gate:** random 3-SAT vs brute force (n ≤ 12), pigeonhole UNSAT, empty
  formula, unit propagation chains, and a deterministic proof trace.

### P6 — Packaging and distribution

- `Dockerfile` (multi-stage, uv, non-root, `HCS_DATA_DIR=/data`, healthcheck),
  `.dockerignore`, `docker-compose.yml`, and a documented `vercel` container
  path. Local `docker build` + `docker run` smoke test.
- `npm` client package (`@hcs/discovery-client`) with typed fetch helpers and a
  `--dry-run` publish check; PyPI metadata verified with `uv build` and
  `twine check --strict` in a throwaway venv.
- **Gate:** container serves `/api/v1/health` and runs one workflow; wheel and
  npm tarball pass `--dry-run` checks.

### P7 — Docs, SEO, i18n

- Zero-to-hero guides in **EN, DE, FR**: install, first project, first run,
  browser mode, troubleshooting, "what is honest here".
- Static SEO: unique title/description per route, Open Graph + Twitter cards,
  `sitemap.xml`, `robots.txt`, JSON-LD `SoftwareApplication`, canonical URLs,
  and a real 404 page. Pre-rendered meta for the static host.
- **Gate:** link checker, a Playwright SEO test (title/description/OG present,
  canonical correct), sitemap well-formed XML with every public route, and the
  three guides linked from the README.

### P8 — Hourly autonomous wake-up

- A Windows Scheduled Task runs every hour, invokes the OpenCode CLI against
  **this session** with a timestamped prompt, writes to a log, and takes a lock
  so two runs never overlap. It does not bypass permissions (`--auto` is
  explicit and documented), and it stops if the repository has uncommitted
  merge state.
- **Gate:** the task exists (`schtasks /query`), a dry run writes the expected
  log line, and the lock prevents a second simultaneous run.

### P9 — Release hygiene

- Gate runner `full` green, G15 exe green, evidence regenerated, README and
  ledger reconciled, merge to `main`, production deploy verified again.

---

## 4. Order and dependency graph

```text
P1 (browser)  ─┬─► P7 (docs/SEO needs the browser mode to describe)
P2 (API)      ─┼─► P3 (MCP wraps the same services)
P4 (boost)    ─┼─► P1.4 (browser benefits from the same kernel semantics)
P5 (SAT)      ─┴─► P7 (guide section)
P6 (container) ──► P9 (release)
P8 (scheduler) runs in parallel, independent of the code
```

## 5. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Browser pipeline drifts from server semantics | Two different answers for one dataset | One fixture: Python produces expected values, TS test asserts the same numbers |
| IndexedDB quota / eviction | Silent data loss | `navigator.storage.estimate()` shown; explicit export; no claim of durability beyond "this device" |
| WebGPU absent on a phone | Similarity unavailable | CPU reference path with an explicit label and a measured time |
| Hybrid threading and GIL | No speed-up, added complexity | Measure before claiming; keep `cpu`/`gpu` modes; parity test independent of mode |
| SAT solver bugs | Wrong subset silently | Brute-force differential tests, UNSAT proofs tested, deterministic order |
| Docker image too large | Slow cold start | Multi-stage, no dev deps, no CUDA, `--no-install-recommends` |
| Scheduler wakes an agent that fights the current one | Corrupted working tree | Lock file, `git status` check, one run at a time, log |
| Vercel protection on the demo | Visitor sees a login | Documented; demo path is the static host the owner chooses; verification uses the OIDC header |

## 6. Acceptance checklist (the definition of "done" for this plan)

- [x] Browser workspace imports, triages, ranks and scores similarity with no
      backend, at 360 px, and persists after reload.
      (`apps/web/e2e/offline.spec.ts` against `vite preview`, no API.)
- [ ] Offline after the first visit (service worker caching the shell + WASM).
      **Not done**: the lab works without a backend but still needs its assets from
      the network on first load.
- [x] API and CLI share the similarity payload; API tests cover 404, invalid SMILES
      and engine=gpu without an adapter.
- [x] MCP server exposes five working tools with a scripted stdio session test.
- [x] Hybrid boost is bit-exact; measured 1.03–1.09× over the GPU upload path on
      this host, and `auto` keeps GPU-only when the calibration says so.
- [x] SAT solver passes 40 brute-force differential cases, pigeonhole UNSAT, unit
      chains and the cardinality encodings; CLI exposes `solve` and `select`.
- [x] Container builds, serves, runs a similarity search and reports healthy
      (`docker build` + `docker run` smoke test on this host).
- [ ] Published npm package and PyPI upload. **Prepared only**: no registry
      credentials were used and nothing was published.
- [x] Guides EN/DE/FR exist and are linked; sitemap, robots, OG tags, JSON-LD and
      a real 404 are verified by Playwright. UI strings themselves are English
      only — the guides are translated, not the interface.
- [x] Hourly task exists (`schtasks /Query` → Ready), is logged, takes a lock and
      refuses to run with unmerged paths.
- [x] `scripts/gates.py --level full` passes on this tree (G0–G11; G13 skipped
      because gitleaks is not installed) and G15 passes at release level.
- [x] README states exactly what works, what is weak, and what is planned.
- [x] Merged to `main` and pushed; the production deployment was re-verified
      afterwards (RDKit WASM self-test, WebGPU parity, offline-lab import and
      persistence).

## 7. What this plan deliberately does not do

- No boat: no molecular dynamics, no learned ADMET model, no structure
  prediction, no multi-tenant hosting.
- No GPU descriptor computation, no CUDA dependency.
- No Pyodide runtime in the browser.
- No claim that the browser matches the server for docking or force fields.
- No disabling of Vercel deployment protection to make a link public.
- No published package, image or release tag without the owner's credentials and
  an explicit publish step.

## 8. Sources

- Vercel, *Functions limits* (2026-08-24) — <https://vercel.com/docs/functions/limitations>
- Vercel, *Functions can now be up to 5 GB in package size* (2026-06-29) —
  <https://vercel.com/changelog/vercel-functions-can-now-be-up-to-5-gb-in-package-size>
- Vercel, *Running Docker on Vercel* / *Does Vercel support Docker deployments?* —
  <https://vercel.com/kb/guide/does-vercel-support-docker-deployments>
- SQLite, *Wasm persistence options* (OPFS, `opfs-sahpool`) —
  <https://sqlite.org/wasm/doc/trunk/persistence.md>
- PowerSync, *The current state of SQLite persistence on the web* (2026-05) —
  <https://powersync.com/blog/sqlite-persistence-on-the-web>
- W3C, *WebGPU* Candidate Recommendation Draft (2026) — <https://www.w3.org/TR/2026/CRD-webgpu-20260102>
- NVIDIA, *nvMolKit* (CUDA-only GPU RDKit functions) — <https://research.nvidia.com/labs/dbr/blog/nvMolKit/>
- Dalke, *The chemfp project* (popcount bounds, throughput baseline) —
  <https://jcheminf.biomedcentral.com/articles/10.1186/s13321-019-0398-8>

Sources were read on 2026-11-03. Platform limits change; the plan cites the date
so a later reader can tell whether it is stale.
