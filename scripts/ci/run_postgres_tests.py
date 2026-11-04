"""Run the PostgreSQL integration tests against a disposable container.

    uv run python scripts/ci/run_postgres_tests.py
    uv run python scripts/ci/run_postgres_tests.py --keep

Starts ``postgres:16-alpine`` (pinned by digest) on a random loopback port, waits for
it, runs ``tests/integration/test_postgres.py``, and removes the container. Exit codes:
0 = tests passed, 1 = tests failed, 2 = Docker is unavailable (the gate runner reports
that as ``skipped``, never as ``passed``).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
#: Pinned so a moving tag cannot change what the gate tested.
IMAGE = "postgres:16-alpine@sha256:0cefaabd882e42bcb2a2f3dc56d3ce4770560ba62fd7f197f1a2e008fd5731ab"
PASSWORD = "hcs_gate_pw"
USER = "hcs"
DATABASE = "hcs"


def _docker(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args], capture_output=True, text=True, encoding="utf-8", errors="replace", check=check
    )


def _wait_ready(container: str, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = _docker("exec", container, "pg_isready", "-U", USER, check=False)
        if result.returncode == 0:
            return
        time.sleep(1)
    logs = _docker("logs", container, check=False)
    raise SystemExit(f"PostgreSQL did not become ready:\n{logs.stdout}\n{logs.stderr}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true", help="leave the container running for diagnosis")
    args = parser.parse_args(argv)

    if shutil.which("docker") is None:
        print("docker is not installed; the PostgreSQL gate cannot run here.", file=sys.stderr)
        return 2
    if _docker("info", "--format", "{{.ServerVersion}}", check=False).returncode != 0:
        print("the Docker daemon is not reachable.", file=sys.stderr)
        return 2

    container = f"hcs-pg-{uuid.uuid4().hex[:8]}"
    try:
        _docker(
            "run",
            "-d",
            "--rm",
            "--name",
            container,
            "-e",
            f"POSTGRES_PASSWORD={PASSWORD}",
            "-e",
            f"POSTGRES_USER={USER}",
            "-e",
            f"POSTGRES_DB={DATABASE}",
            "-p",
            "127.0.0.1::5432",
            IMAGE,
        )
        _wait_ready(container)
        port_output = _docker("port", container, "5432/tcp").stdout.strip()
        port = port_output.rsplit(":", 1)[-1]
        url = f"postgresql+pg8000://{USER}:{PASSWORD}@127.0.0.1:{port}/{DATABASE}"
        env = dict(os.environ, HCS_TEST_POSTGRES_URL=url)
        print(f"PostgreSQL {container} on 127.0.0.1:{port}; running the integration suite.", flush=True)
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "tests/integration/test_postgres.py", "-rs"],
            cwd=REPO_ROOT,
            env=env,
        )
        return result.returncode
    finally:
        if not args.keep:
            _docker("stop", container, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
