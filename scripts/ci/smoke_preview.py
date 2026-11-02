"""Smoke-test a deployed preview: does the demo actually exist and finish a run?

PLAN.md R0.6 exists because the hosted demo was *claimed* but never observed (finding F3),
and because it seeds at application start (F4). This script only reads: it calls the
health and readiness endpoints, lists the projects, checks that the demo project is
there, that at least one run finished with results, and that the page says "synthetic"
so nobody mistakes the demonstration library for measured data.

    python scripts/ci/smoke_preview.py https://<preview>.vercel.app
    python scripts/ci/smoke_preview.py http://127.0.0.1:8793 --json

Exit codes: 0 all checks observed, 1 a check failed, 2 the deployment did not answer.

Nothing here writes to the deployment and nothing prints a secret: only URLs derived from
the base URL you pass in, plus response bodies that are already public.
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from typing import Any

TIMEOUT = 30.0


def _get(base: str, path: str) -> tuple[int, str]:
    url = base.rstrip("/") + path
    request = urllib.request.Request(url, headers={"Accept": "application/json, text/html"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as exc:
        return 0, f"{type(exc).__name__}: {exc}"


def check(base: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        results.append({"check": name, "ok": ok, "detail": detail})

    status, body = _get(base, "/api/v1/health")
    record("health", status == 200, f"{status}: {body[:160]}")

    status, body = _get(base, "/api/v1/ready")
    record("ready", status == 200 and '"status":"ready"' in body.replace(" ", ""), f"{status}: {body[:160]}")

    status, body = _get(base, "/")
    record("spa root", status == 200 and 'id="root"' in body, f"{status}: {len(body)} bytes")

    status, body = _get(base, "/api/v1/projects")
    projects: list[dict[str, Any]] = []
    if status == 200:
        try:
            parsed = json.loads(body)
            projects = parsed.get("items", parsed) if isinstance(parsed, dict) else parsed
        except json.JSONDecodeError:
            projects = []
    record("projects listed", status == 200 and bool(projects), f"{status}: {len(projects)} project(s)")

    demo = None
    for project in projects if isinstance(projects, list) else []:
        name = str(project.get("name", "")).lower()
        if "demo" in name or "synthetic" in name:
            demo = project
            break
    record("demo project present", demo is not None, str(demo.get("name") if demo else "no project named demo"))

    if demo is not None:
        project_id = demo.get("id")
        status, body = _get(base, f"/api/v1/projects/{project_id}/runs")
        runs: list[dict[str, Any]] = []
        if status == 200:
            try:
                parsed = json.loads(body)
                runs = parsed.get("items", parsed) if isinstance(parsed, dict) else parsed
            except json.JSONDecodeError:
                runs = []
        finished = [
            run
            for run in runs
            if str(run.get("status", "")).lower() in ("finished", "succeeded", "success", "completed")
        ]
        record("a run finished", bool(finished), f"{len(finished)} of {len(runs)} run(s) finished")

    status, body = _get(base, "/")
    record(
        "page says synthetic",
        status == 200 and "synthetic" in body.lower(),
        f"{status}: {'found' if 'synthetic' in body.lower() else 'not found in the served page'}",
    )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("url", help="base URL of the deployment, e.g. https://preview.vercel.app")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    results = check(args.url)
    if args.json:
        print(json.dumps({"url": args.url, "checks": results}, indent=2))
    else:
        for entry in results:
            print(f"{'PASS' if entry['ok'] else 'FAIL'}  {entry['check']}: {entry['detail']}")
    unreachable = [entry for entry in results if entry["detail"].startswith("0:")]
    if unreachable:
        return 2
    return 0 if all(entry["ok"] for entry in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
