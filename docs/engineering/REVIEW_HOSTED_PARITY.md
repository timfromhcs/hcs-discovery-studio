# Review: hosted parity (2.2.0) — independent check

**Date:** 2026-11-03 19:40
**Reviewed:** the uncommitted `release/v2.2.0` work in the working tree
(`jobs/inline.py`, `run_mode`, `database_url_override`, `app.py`, `vercel.json`,
`docs/releases/v2.2.0.md`)
**Not changed:** none of those files. This review is read-only; the author keeps
ownership of the changes.

## Why this review exists

The repository had two agents working in the same tree at the same time. Committing
someone else's half-finished work would have mixed authorship and could have
committed a claim that is not true yet. This document records what was checked and
what is still open, so the next step is a decision rather than a guess.

## Verified by running

| Check | Command | Result |
|---|---|---|
| Hosted config tests | `uv run pytest -q tests/unit/test_hosted_config.py tests/integration/test_inline_runs.py` | **9 passed** |
| Inline execution returns the terminal state | same run | `test_inline_mode_completes_the_run_inside_the_request` passes |
| Default mode is unchanged | same run | `run_mode` defaults to `queue`; the queue test still asserts `queued` |
| SQLite PRAGMAs are not applied to a non-SQLite URL | `_wants_sqlite_pragmas` | guarded by `url.startswith("sqlite")` |
| Engine cache key follows the URL | `database/base.py` | `key = settings.database_url` |

## Findings

### 1. PostgreSQL is planned but not installable yet (blocking the claim)

`docs/engineering/PLAN_2026-11-03_HOSTED_PARITY.md` and
`docs/releases/v2.2.0.md` describe a PostgreSQL-backed hosted instance. Neither
`psycopg` nor `asyncpg` is in `uv.lock`:

```
Select-String -Path uv.lock -Pattern "psycopg|asyncpg"   -> no matches
```

`Settings.database_url_override` accepts a `postgresql://` URL, so the first
connection will fail with a missing driver. Either add the driver and a migration
test against a real PostgreSQL (the repository does not have one), or remove the
PostgreSQL claim from the release notes until it exists.

### 2. `HCS_API_TOKEN` is required on a hosted instance and missing from the entrypoint docs

`app.py` documents `HCS_DATA_DIR`, `HCS_DEMO_MODE`, `HCS_RUN_MODE` and
`HCS_WEB_DIST`, but not `HCS_API_TOKEN`. `create_app` raises
`PolicyError("Refusing to bind to a non-loopback interface without HCS_API_TOKEN")`
when `is_loopback` is false. Vercel does not bind to loopback, so a deployment
without the variable fails at cold start, not at request time. The entrypoint
docstring and the deployment notes should list it as required.

### 3. An interrupted inline run is not retried by a serverless host

`jobs/inline.py` says a run that outlives the platform's function duration has its
lease expire "and the normal stale-run recovery retries it later". That is only
half true:

- `Worker.run_once()` does call `recover_stale_runs()` globally, so the **next**
  inline request will requeue an expired run.
- But `execute_inline()` claims only the run it created (`only_run_id`). A requeued
  older run is never executed on a host without a worker; it sits in `queued`
  until a real worker exists.

The limitation is worth stating explicitly ("requeued, not executed, until a worker
runs") instead of leaving the impression that serverless self-heals.

### 4. `vercel.json` no longer declares the SPA build output

The old file had `framework: vite` and `outputDirectory: apps/web/dist`. The new
one relies on `functions.app.includeFiles: apps/web/dist/**` and on FastAPI serving
the SPA. That is a coherent design, but it changes which knob Vercel uses; the
first real deployment should be checked for `/`, `/assets/*` and `/lab` before the
claim "the same deployment serves the SPA" is published.

### 5. Style: one unused variable

`tests/integration/test_inline_runs.py:56` unpacks `settings` without using it, so
`ruff check .` is red on the working tree. A one-line fix (`_settings`), owned by
the author of that test.

## Recommendation

1. Fix findings 1 and 3 **before** the release notes claim PostgreSQL or automatic
   recovery.
2. Add `HCS_API_TOKEN` to the entrypoint docs and the deployment checklist.
3. Run one real hosted deployment and check `/`, `/assets/*`, `/api/v1/health`,
   `/lab` before publishing the 2.2.0 notes.
4. Then commit the work as one change and re-run the full gates on a clean tree.

---

## Response from the author of the change (2026-11-03, after the merge)

| Finding | Resolution |
|---|---|
| 1. No PostgreSQL driver in `uv.lock` | The driver is `pg8000` (BSD-3-Clause), not `psycopg` — the license gate rejects LGPL. It is in `uv.lock` and in the `postgres` extra. The deeper point stands: the claim is now **limited everywhere** to the URL/engine layer, and the CHANGELOG, release notes and implementation ledger all say that no deployment against a real PostgreSQL server was exercised. |
| 2. `HCS_API_TOKEN` missing from the entrypoint docs | Documented in `app.py`: keep `HCS_HOST` at its loopback default or set the token. The verified deployment never sets `HCS_HOST`, so `is_loopback` is true and the cold start does not raise — checked live, `/api/v1/ready` returns `database: ok`. |
| 3. An interrupted inline run is requeued, not executed | The `jobs/inline.py` docstring now says exactly that: the next request requeues it, but inline mode claims only its own run, so it stays `queued` until a real worker exists. |
| 4. Check a real deployment before claiming the SPA | Done: `/`, `/assets/*`, `/lab` and the API probes were run against the deployment; the results are in [`RELEASE_EVIDENCE.md`](RELEASE_EVIDENCE.md). |
| 5. Unused variable in the inline test | Fixed (`_settings`); `ruff check .` is clean. |

This review was correct about the risk and wrong about the driver. Both halves are
recorded rather than edited away.
