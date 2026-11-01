# Release evidence

Exact, reproducible evidence for the release decision. Nothing here is a
projection: each row names the command or job that produced the result, and the
result that was observed.

This file is updated at each release gate. It is intentionally blunt about what
was **not** run.

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

### Known limitations at this commit

- Docking is regression-checked on one complex, not benchmarked.
- Property estimates are weak and have no calibrated uncertainty.
- No MD, no learned ADMET model, no structure prediction, no GPU execution.
- No target UI page; targets/structures exist as service + API + CLI.
- Single machine: SQLite queue, no distributed workers, no multi-tenant hosting.
- No TLS; any non-loopback deployment needs a hardened proxy.
- The SPA ships in the wheel; a source build without `apps/web/dist` has no UI.

### What is still required before publication

1. Owner approval for the Stable tag (`AGENTS.md` §0.2, §30.4).
2. One release-candidate execution of `release.yml` (its first real run).
3. Verification of the published assets: wheel, `sbom.cdx.json`,
   `SHA256SUMS.txt`, and `gh attestation verify`.
