# Plan: Hosted Parity + Release 2.2.0

**Date:** 2026-11-03
**Branch:** `release/v2.2.0` (from `main` @ `a3d7be9`)
**Owner gate:** tag and public publication stay with the owner; everything before
that is prepared and verified here.

This plan answers one question: **what is missing for the Vercel deployment to do
everything the local install does, and how do we ship that as a release?**

It follows the repository's evidence discipline. Every claim in the "Verified
state" section was produced by a command in this session; every work package has
a gate that must pass before the next one starts.

---

## 1. Goal

1. `main` is merged, green, and tagged as `v2.2.0` with published artifacts.
2. `https://hcs-discovery-studio.vercel.app` serves the **whole workbench** —
   SPA *and* `/api/v1` — not just the static bundle.
3. State survives a cold start (PostgreSQL), and a submitted run actually
   completes on the hosted instance.
4. Local-first stays the default: no behaviour change for `serve`, the wheel,
   the CLI or the offline lab.

Non-goals are listed in §8, on purpose.

---

## 2. Verified state (2026-11-03, this session)

| Fact | Evidence |
|---|---|
| Repo version is `2.1.0`; only `v0.1.0` and `v1.0.0` are tagged | `pyproject.toml:3`, `git tag` |
| `main` == `origin/main` at `a3d7be9`; no open PRs, no open issues | `git rev-list --count`, `gh pr list` |
| `origin/release/v2.0.0` (15), `origin/fix/v2-stable-gates` (13), `origin/fix/v2-gemini-mandate` (10) are **ahead of main** | `git rev-list --count main..<branch>` — must be checked before deleting; main may already contain the work by another path |
| Production deployment builds in **8 s** → it is the static SPA only | `vercel ls hcs-discovery-studio` |
| `vercel.json` sets `framework: vite` and `outputDirectory: apps/web/dist`; `app.py` exists but is never built | `vercel.json` |
| Root `app.py` already exposes the ASGI app and documents `HCS_DATA_DIR`, `HCS_DEMO_MODE`, `HCS_WEB_DIST` for hosted previews | `app.py:1-27` |
| Database is hard-wired to SQLite | `core/config.py:93-94` returns `sqlite+pysqlite:///…`, no override key |
| DB layer is otherwise portable: only `PRAGMA` calls are SQLite-specific and already guarded by `url.startswith("sqlite")` | `database/base.py:24-39` |
| No Postgres driver is declared | `pyproject.toml:20-33` |
| Runs require a worker process; the API only enqueues | `jobs/worker.py`, `cli/main.py:190` (`--worker/--no-worker`), no worker in `api/` |
| `HCS_DEMO_MODE=true` seeds a real project + import + triage run at startup | `demo.py:1-45` |
| All filesystem state lives under one directory | `core/config.py:69-94` (`db_path`, `runs_dir`, `cache_dir`, `uploads_dir`, `receptors_dir`) |
| Frontend talks to same-origin `/api/v1` | `apps/web/src/api/client.ts:26` |
| 573 backend tests, 11 Playwright tests, 83 % branch coverage, gates runner exists | `docs/engineering/IMPLEMENTATION_STATUS.md`, `scripts/gates.py` |

---

## 3. Web research (2026-11-03)

| Finding | Source | Consequence for this plan |
|---|---|---|
| **Large Functions (Beta)**: Python bundles up to **5 GB** instead of 500 MB; opt in with `VERCEL_SUPPORT_LARGE_FUNCTIONS=1`; requires Fluid Compute | https://vercel.com/docs/functions/limitations , https://vercel.com/changelog/vercel-functions-can-now-be-up-to-5-gb-in-package-size | **This dissolves the blocker recorded in `ROADMAP_TO_V2_STABLE.md` §1** ("561 MB > 500 MB"). The RDKit backend can be hosted. |
| **FastAPI is a first-class Vercel runtime**: `app.py`/`index.py`/`server.py`/`main.py` are auto-detected; `[tool.vercel] entrypoint` points elsewhere; `app.frontend("/", directory=…)` promotes a built SPA to the CDN while API routes keep priority | https://vercel.com/docs/frameworks/backend/fastapi | We do **not** need Services or a second project. One project = SPA on CDN + FastAPI function, same origin, no CORS. |
| Functions: default duration 300 s, Pro up to 800 s; request body max 4.5 MB; memory 2 GB (Hobby) / 4 GB (Pro) | https://vercel.com/docs/functions/limitations | Uploads > 4.5 MB must go to Blob later; a synchronous demo run must stay well under the duration cap. |
| Vercel Daemons (background workers from a Dockerfile) and Vercel Queues exist for long-running consumers | Vercel product docs (knowledge update) | Option for a real worker later; **not needed** for this release (see D4). |

---

## 4. Architecture decision

| Option | Verdict |
|---|---|
| **A. Keep static-only, add an offline lab** | Rejected for the goal: `/api/v1` parity is exactly what the owner asked for, and the app is already same-origin. |
| **B. One project: FastAPI `app.py` + `app.frontend(...)` + Large Functions** | **Chosen.** Smallest diff, matches documented platform behaviour, keeps one deploy target and one origin. |
| **C. Container image (`Dockerfile` exists) on Vercel** | Fallback only. More moving parts than needed; keep the Dockerfile for self-hosting, not for the hosted target. |

**Persistence:** SQLite on `/tmp` cannot survive a cold start. Chosen: an opt-in
`HCS_DATABASE_URL` (SQLAlchemy URL, Postgres via Neon from the Marketplace),
default unchanged (`sqlite`). Filesystem artifacts stay on `/tmp` for the hosted
demo and are documented as ephemeral.

**Job execution:** a hosted function cannot keep the embedded worker thread
alive after the response. Chosen: opt-in `HCS_RUN_MODE=inline`, which drains the
queue **inside the request** using the existing `Worker` with `--once`
semantics. Default stays `queue`. Honest limit: one bounded run per request,
subject to the function duration cap.

---

## 5. Open questions and the decisions taken

Each question is answered with a default so the work can proceed; the owner can
override any of them before the tag.

| # | Open question | Decision for this cycle | Reversible? |
|---|---|---|---|
| Q1 | Should the hosted instance be public, or stay behind Vercel Authentication? | **Stay behind Vercel Authentication** for this release. Making research data public is an owner decision, not an engineering one. | Yes (dashboard toggle) |
| Q2 | Do we provision a real Postgres, or ship the hosted app with the disposable demo workspace only? | Provision Postgres **only if** it can be done without asking for credentials mid-run; otherwise ship `HCS_DEMO_MODE` and record the gap. Persistence code lands either way. | Yes |
| Q3 | Is a hosted *write* path acceptable (import, create project, run) or read-only demo? | Write path **enabled** behind the existing bearer token + demo mode; the demo project refuses to overwrite real data (`demo.py`). | Yes |
| Q4 | Which version number? | **2.2.0** for the capability. `2.2.0` was tagged but its release workflow died on an unresolvable action pin before publishing anything, so the published version is **2.2.1** (same application code). No tag was moved. | No (after tag) |
| Q5 | Do the three stale `origin/*` branches get merged or deleted? | **Inspect, then delete** if their content is already in `main`; never force-merge stale branches into a release. | Yes (branches are remote refs) |
| Q6 | Are artifacts (poses, CSVs, reports) durable on the hosted instance? | **No, not in 2.2.0.** They are regenerable from the run manifest; Blob storage is a follow-up. Documented, not hidden. | Yes (additive) |
| Q7 | Does the RDKit WASM/offline lab keep working on the hosted domain? | Must, and it is part of the acceptance gate (Playwright against the deployment). | — |

---

## 6. Work packages

### P0 — Branch hygiene and baseline (gate: nothing red)

- [x] `uv run python scripts/gates.py --level full` on `main` (baseline).
- [x] For each of `release/v2.0.0`, `fix/v2-stable-gates`, `fix/v2-gemini-mandate`:
      list the commits not in `main`, confirm they are superseded, then delete the
      remote branch. Record the decision in `AGENT_LOG.md`.
- [x] Create `release/v2.2.0` from `main`.

**Gate:** baseline `full` green; branch list reduced to `main` + the release branch.

### P1 — Configurable database URL (gate: tests + migration still green)

- [x] `core/config.py`: add `database_url_override: str | None` (`HCS_DATABASE_URL`);
      `database_url` returns it when set, else the SQLite path.
- [x] `pyproject.toml`: optional extra `postgres = ["psycopg[binary]>=3.2"]`.
- [x] `database/base.py`: keep `pool_pre_ping`, do not apply SQLite pragmas for
      non-SQLite URLs (already guarded — add a test that proves it).
- [x] Tests: URL resolution (both paths), pragma listener not attached for Postgres,
      Alembic offline SQL generation for Postgres.

**Gate:** `pytest tests/database tests/core` green; a `create_engine` on a Postgres
URL is accepted without connecting.

### P2 — Inline run mode for hosted instances (gate: integration test)

- [x] `core/config.py`: `run_mode: Literal["queue", "inline"] = "queue"`
      (`HCS_RUN_MODE`).
- [x] Route that submits a run: when `run_mode == "inline"`, drain the queue once
      (existing `Worker`, bounded by `max_run_attempts` and a wall-clock budget)
      before returning, and report `execution: "inline"` in the response payload.
- [x] Never enable inline implicitly; log it once at startup in `app.py`.
- [x] Tests: inline completes a triage run end-to-end; queue mode leaves it
      `queued` and unchanged; inline failure surfaces `failed`, not a silent 200.

**Gate:** new integration test green; existing run tests untouched.

### P3 — Vercel: one project, SPA + API (gate: live probes)

- [x] `vercel.json`: drop `framework: vite` / `outputDirectory`; keep the SPA build
      as the build command.
- [x] `app.py`: `app.frontend("/", directory=<dist>)` when the built SPA exists, so
      the SPA is CDN-served and `/api/v1` reaches the function. Keep `HCS_WEB_DIST`.
- [x] Project env: `VERCEL_SUPPORT_LARGE_FUNCTIONS=1`, `HCS_DATA_DIR=/tmp/hcs`,
      `HCS_DEMO_MODE=true`, `HCS_RUN_MODE=inline`, `HCS_NETWORK_POLICY=local`.
- [x] Deploy preview, then production. Probe: `/api/v1/health`, `/api/v1/ready`,
      `/api/v1/projects` (returns the demo project), `/` (SPA 200), `/lab` (SPA
      fallback), and a Playwright run against the URL with the trusted-OIDC header.

**Gate:** all probes green against the deployed URL **and** `vercel ls` build
duration shows a real Python build (not 8 s).

### P4 — Documentation and release 2.2.0 (gate: verify_version + CI on the tag SHA)

- [x] `CHANGELOG.md` + `docs/releases/v2.2.0.md`.
- [x] Update `IMPLEMENTATION_STATUS.md`, `ROADMAP_TO_V2_STABLE.md` §1 (the 500 MB
      blocker is resolved — with the measured number, not a guess),
      `README.md` status table, `docs/user-guide/QUICKSTART.md` (hosted row).
- [x] Bump `pyproject.toml` to `2.2.0`; `uv run --no-project python
      scripts/release/verify_version.py v2.2.0`.
- [x] Merge to `main`, wait for CI + CodeQL on the exact SHA, then tag.

**Gate:** CI + CodeQL green on the tag SHA; release workflow publishes wheel +
SBOM + checksums + attestation (owner approves the tag).

---

## 7. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| RDKit + bundle still exceeds 5 GB | Hosted API impossible this cycle | Fall back to `HCS_DEMO_MODE` static-only and record it honestly; do not claim parity |
| Cold start with RDKit import | First request slow (seconds) | Measure it and publish the number; keep the SPA on the CDN |
| Postgres not reachable during build → migrations fail | Deploy fails | Run migrations lazily at startup *or* in the build script with a timeout; never block boot on a failed migration in demo mode |
| Inline run exceeds function duration | 504 on submit | Bound inline runs by a wall-clock budget below 300 s and fail with a structured error |
| Hosted instance mutated by a visitor | Demo data corrupted | Demo mode refuses to run on a non-empty real workspace; consider a read-only flag |
| Stale branches contain real work | Lost commits | Inspect every divergent commit before deleting (P0) |

---

## 8. Out of scope for 2.2.0

- Object storage (Blob) for uploads/artifacts; PostgreSQL-backed queue.
- Vercel Daemons/Queues as a real worker.
- Auth beyond the existing static bearer token (no users, roles, SSO).
- Target-explorer UI, pocket detection, receptor preparation.
- MD, learned ADMET, structure prediction.
- Public data exposure or a public demo URL.

---

## 9. Definition of done

1. `https://hcs-discovery-studio.vercel.app/` loads the workspace UI, and
   `/api/v1/projects` returns a real, computed demo project from the same origin.
2. A workflow submitted on the hosted instance reaches `succeeded` (inline mode).
3. With `HCS_DATABASE_URL` set, the same image reads/writes Postgres; without it,
   nothing changes locally.
4. `scripts/gates.py --level full` green; CI + CodeQL green on the release SHA.
5. `v2.2.0` published with wheel + SBOM + checksums + attestation.
6. The honest limits of the hosted instance are written down where a user will
   read them, not only here.

Execution evidence is appended to `docs/engineering/AGENT_LOG.md`.
