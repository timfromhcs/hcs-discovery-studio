# Release evidence

Exact, reproducible evidence for the release decision. Nothing here is a
projection: each row names the command or job that produced the result, and the
result that was observed.

This file is updated at each release gate. It is intentionally blunt about what
was **not** run.

---

## v3.0.1 — 2026-11-04 (published)

The feature evidence below was produced on the 3.0.0/3.0.1 tree. `v3.0.0` was tagged
but not published (the macOS x64 binary job could not install RDKit — no x86_64
wheel); `v3.0.1` is the first published 3.0 release with Windows x64, Linux x64 and
macOS arm64.

| Gate | Command | Observed |
|---|---|---|
| Format | `uv run ruff format --check .` | 236 files already formatted |
| Lint | `uv run ruff check .` | All checks passed |
| Types | `uv run mypy` | Success: no issues in 103 source files |
| Tests | `uv run pytest -q` | 635 passed, 4 skipped (PostgreSQL tests skip without `HCS_TEST_POSTGRES_URL`), 1 deselected |
| Coverage | `uv run pytest --cov=hcs_discovery --cov-branch` via G4 | 83 % branch |
| Frontend types/build | `npm run typecheck`, `npm run build` | clean |
| Visual/a11y QA | `node apps/web/scripts/visual_qa.mjs` against a demo instance | 180 captures (every route × 6 widths × 2 themes), 0 automatic findings |
| End-to-end | `npm run test:e2e` | 19 passed; timeline duration formatting is asserted against `data-duration-ms` |
| Encoding gate | `uv run python scripts/ci/check_text_encoding.py` | clean; 4 unit tests |
| Docs links | `uv run python scripts/ci/check_links.py` | 60 Markdown files, 0 broken local links |
| Wheel | `uv build --wheel` + clean-venv smoke | `hcs_discovery_studio-3.0.1-py3-none-any.whl` |
| PostgreSQL | `scripts/ci/run_postgres_tests.py` | migrations, full run, 4-worker claim race, `/ready`, stale-lease recovery on `postgres:16-alpine` |
| Lighthouse | `scripts/ci/run_lighthouse.py` | workspace 97 / lab 98 perf, 100 a11y, LCP 2.3/1.8 s, CLS 0/0, TBT 91/52 ms (hard: a11y/CLS + catastrophic floor) |
| Executable | `scripts/release/build_executable.py` | smoke test: `version`, `db upgrade`, `doctor`, `/api/v1/ready`, GPU search when an adapter exists |
| Release version | `scripts/release/verify_version.py v3.0.1` | tag/version/changelog agree |
| Similarity k-NN | generated report | full-scan-equivalent ranking; 6.0×/3.9× clustered, 0.85× unclustered |
| Batched multi-query | generated report | 10.9× at 100k, 9.7× at 500k; parity per query |
| ESOL | `validate_esol_delaney.py --check` | RMSE 1.099, R² 0.725; held-out 1.201/0.640 |

**Not run:** a managed PostgreSQL deployment (the container is exercised, not a hosted
database); multi-target docking (no receptor preparation).

---

## Browser compute on Vercel — verified 2026-11-03

The static SPA (no backend) was deployed to the `hcs-discovery-studio` project and
verified in a real browser session against the deployed URL, not locally:

| Item | Value |
|---|---|
| Deployment | `https://hcs-discovery-studio.vercel.app` (production) and `https://hcs-discovery-studio-g7i0jm3zf-hcsmediacorp.vercel.app` (first preview of the same build) |
| Protection | Vercel Authentication is enabled; automated access used the CLI's development OIDC token as `x-vercel-trusted-oidc-idp-token`. Nothing was made public for the test. |
| Browser | system Chrome 141 with `--enable-unsafe-webgpu` |
| RDKit WebAssembly self-test | **verified** — canonical SMILES `CC(=O)Oc1ccccc1C(=O)O`, descriptors and SVG rendered client-side |
| WebGPU Tanimoto | **parity: bit-exact** over 100,000 fingerprints against the JavaScript reference; 10.5× measured speed-up on the preview and 11.2× on production (same visitor GPU, repeated run) |
| Page errors | none |
| Backend | **absent by design** — every `/api/v1` call fails in the static preview; this deployment demonstrates the client-side compute path only |

---

## Full application on Vercel — verified 2026-11-03 (v2.2.0)

The same project now serves the SPA **and** `/api/v1`. The former blocker (561 MB
bundle against the 500 MB Python limit) is resolved by Vercel's Large Functions
beta; nothing was made public to run the checks.

| Item | Value |
|---|---|
| Project | `hcsmediacorp/hcs-discovery-studio` |
| Production | `https://hcs-discovery-studio.vercel.app` (behind Vercel Authentication; probed with `vercel curl`) |
| Verified build | `https://hcs-discovery-studio-g8scjirtg-hcsmediacorp.vercel.app`, then deployed to production |
| Function config | root `app.py`, `maxDuration` 300 s, `includeFiles: apps/web/dist/**`, `VERCEL_SUPPORT_LARGE_FUNCTIONS=1` |
| Environment | `HCS_DATA_DIR=/tmp/hcs`, `HCS_DEMO_MODE=true`, `HCS_RUN_MODE=inline`, `HCS_NETWORK_POLICY=local`, `HCS_WEB_DIST=/var/task/apps/web/dist` |
| `GET /api/v1/health` | `{"status":"ok","product":"HCS Discovery Studio","version":"2.2.0"}` |
| `GET /api/v1/ready` | `{"status":"ready","database":"ok"}` (cold start ≈2–3 s) |
| `GET /api/v1/projects` | one demo project, **16 compounds**, **1 run**, computed on that instance at start-up |
| Demo run | `status: succeeded`, started and finished within the first cold start |
| `POST /api/v1/runs` | `status: succeeded` in **2.1 s** round trip (`execution: inline`) |
| SPA | `GET /` and `GET /lab` return the app shell; unknown client paths fall through to it |
| Depiction | `424 missing_dependency` on hosts without `libXrender`; every other endpoint unaffected |

Reproduce: `vercel deploy --prod`, then
`vercel curl https://hcs-discovery-studio.vercel.app/api/v1/ready` (the CLI adds
the deployment-protection token itself). The browser probes from the section above
still apply to the SPA half of the deployment.

---

## Re-measurement 2026-11-03 (branch `feat/v2-stable-readiness`)

Produced by the gate runner, not by hand: `uv run python scripts/gates.py --level fast
--only G4` writes `build/junit.xml` and `build/coverage.json`, and
`uv run python scripts/ci/check_doc_claims.py --write` renders the numbers below into
every document that quotes them. The historical rows further down are kept as the record
of that earlier run; they are not edited retroactively.

| Measurement | Command | Observed |
|---|---|---|
| Tests | `uv run pytest -q` via G4 | <!-- gen:tests -->635 passed, 4 skipped<!-- /gen:tests --> (live docking tests included) |
| Coverage | same run, `--cov-branch` | <!-- gen:coverage -->83 % branch coverage<!-- /gen:coverage --> |
| Tests with the docking binary | `HCS_REQUIRE_VINA=1 uv run pytest tests/scientific/test_vina_adapter.py` | **NOT RUN** locally: no Vina binary is installed on this host (PLAN.md R0.4) |

---

## v2.0.0 — Stable (unpublished as of 2026-11-01)

### Identity

| Item | Value |
|---|---|
| Package version | `2.0.0` (`pyproject.toml`) |
| Branch | `main` |
| Commit at audit | `f023c70` (v2.0.0 content after PR #8) |
| Published tags | `v0.1.0` (prerelease), `v1.0.0` |
| `v2.0.0` tag | **not created** |
| GitHub Release | **not published** — requires owner approval |

### Local gates (Windows 11, Python 3.12.13, uv 0.12.3, Node 22.23.1)

| Gate | Command | Observed |
|---|---|---|
| Format | `uv run ruff format --check .` | 167 files already formatted |
| Lint | `uv run ruff check .` | All checks passed |
| Types | `uv run python scripts/ci/prepare_typecheck.py` then `uv run mypy` | Success: no issues in 89 source files |
| Tests (no docking binary) | `uv run pytest -q` | 419 passed, 2 skipped, 1 deselected |
| Tests (docking binary) | `HCS_VINA_BINARY=… HCS_REQUIRE_VINA=1 uv run pytest -q` | 421 passed, 1 deselected |
| Coverage | `uv run pytest --cov=hcs_discovery --cov-branch` | 81 % branch; HAEL modules 94–99 % |
| Frontend types | `npm run typecheck` (apps/web) | clean |
| Frontend build | `npm run build` (apps/web) | clean, 96 modules |
| E2E | `npm run test:e2e` (apps/web) | 3 passed |
| Visual/a11y QA | `HCS_BASE_URL=… node apps/web/scripts/visual_qa.mjs` | 192 captures, 0 findings |
| Licenses (Python) | `uv run python scripts/ci/check_licenses.py` | 51 packages, 0 outside policy |
| Licenses (npm) | `node scripts/ci/check_licenses.mjs` | 11 packages, 0 outside policy |
| Docs links | `uv run python scripts/ci/check_links.py` | 37 files, 0 broken local links |
| Wheel | `uv build --wheel` | `hcs_discovery_studio-2.0.0-py3-none-any.whl` |
| Wheel smoke | clean venv install, `db upgrade` → project → import → run → `worker --once` | run succeeded, revision `558a25772f08` |

### Cloud gates

| Job | Run | Result |
|---|---|---|
| CI on `main` @ `12febcf` | 40947455326 | success |
| CodeQL on `main` @ `12febcf` | 40947455914 | success |
| CI on PR #8 | 41348985990 | all required jobs success |
| CI on PR #9 | 41350283459 | all required jobs success |
| CI on PR #10 | (see the PR) | see the PR |

The release workflow (`release.yml`) gates publication on exact-SHA CI and CodeQL,
builds and verifies a draft before publishing, and has **not yet run end to end**.
Its first real execution will be the release-candidate run.

### Scientific evidence shipped with this version

| Report | Claim, bounded |
|---|---|
| [`validation/vina-redocking-1iep.md`](../validation/vina-redocking-1iep.md) | One complex (1IEP imatinib/Abl), 5 seeds, top pose 0.42–0.94 Å; Vina-example control 0.29–0.37 Å. Reproduced 2026-11-01. **Not** a docking benchmark. |
| [`validation/ligand-prep-meeko.md`](../validation/ligand-prep-meeko.md) | Ligand PDBQT matches Meeko 0.8.0 on 48/51 fixture ligands; 3 macrocycles kept rigid on purpose. |
| [`validation/esol-solubility.md`](../validation/esol-solubility.md) | Reduced ESOL on 45 independent measured compounds: RMSE 0.968, R² 0.072, bootstrap 95 % CI [0.708, 1.260]; mean baseline RMSE 1.004. **Weak.** |
| [`research/HAEL.md`](../research/HAEL.md) | Synthetic matched-budget ablation only. HAEL is `experimental`, not the default, not wired into a workflow. |
| [`validation/gpu-tanimoto.md`](../validation/gpu-tanimoto.md) | Shared WGSL Tanimoto kernel on one integrated AMD GPU: exact counts against the numpy reference and bit-identical scores to RDKit; 500k fingerprints in about 5 ms resident (roughly 100 M Tanimoto/s, 19x RDKit's bulk call). Not a comparison with CUDA libraries. |

### Known limitations at this commit

- Docking is regression-checked on one complex, not benchmarked.
- Property estimates are weak and have no calibrated uncertainty.
- No MD, no learned ADMET model, no structure prediction. GPU execution exists for
  the Tanimoto similarity kernel only.
- No target UI page; targets/structures exist as service + API + CLI.
- Single machine: SQLite queue, no distributed workers, no multi-tenant hosting.
- No TLS; any non-loopback deployment needs a hardened proxy.
- The SPA ships in the wheel; a source build without `apps/web/dist` has no UI.

### What is still required before publication

1. Owner approval for the Stable tag (`AGENTS.md` §0.2, §30.4).
2. One release-candidate execution of `release.yml` (its first real run).
3. Verification of the published assets: wheel, `sbom.cdx.json`,
   `SHA256SUMS.txt`, and `gh attestation verify`.
