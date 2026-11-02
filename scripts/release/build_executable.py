"""Build and smoke-test the one-file ``hcs-discovery`` executable.

PyInstaller bundles the CLI + FastAPI app, RDKit, the compiled SPA and the Alembic
migration scripts into a single Windows ``.exe`` (or a single binary on the host
platform). The smoke test proves the frozen executable runs the same journey the
wheel does: ``version``, ``doctor``, ``db upgrade``, and a served SPA + API.

Run from the repository root:

    uv run python scripts/release/build_executable.py
    uv run python scripts/release/build_executable.py --skip-build

Requires the frontend to be built first (``npm ci && npm run build`` in
``apps/web``) unless ``--skip-build`` is given.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC = REPO_ROOT / "scripts" / "release" / "hcs_discovery.spec"
DIST = REPO_ROOT / "build" / "exe-dist"
WORK = REPO_ROOT / "build" / "exe-build"


def run(argv: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(argv), flush=True)
    return subprocess.run(
        argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=check
    )


def exe_path() -> Path:
    name = "hcs-discovery.exe" if sys.platform == "win32" else "hcs-discovery"
    return DIST / name


def build_frontend() -> None:
    web = REPO_ROOT / "apps" / "web"
    run(["npm", "ci"], cwd=web)
    run(["npm", "run", "build"], cwd=web)


def build_executable() -> None:
    shutil.rmtree(DIST, ignore_errors=True)
    shutil.rmtree(WORK, ignore_errors=True)
    run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--distpath",
            str(DIST),
            "--workpath",
            str(WORK),
            str(SPEC),
        ]
    )


def _wait_ready(url: str, timeout: float = 60.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            import urllib.request

            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


def smoke_test(exe: Path) -> None:
    if not exe.is_file():
        raise SystemExit(f"executable not found: {exe}")

    env = dict(os.environ)
    with tempfile.TemporaryDirectory(prefix="hcs-exe-smoke-") as data_dir:
        env["HCS_DATA_DIR"] = data_dir

        def call(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [str(exe), *args], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace"
            )

        version = call("version")
        if "2.0.0" not in version.stdout:
            raise SystemExit(f"exe version check failed:\n{version.stdout}\n{version.stderr}")

        call("db", "upgrade")
        current = call("db", "current")
        if "not initialised" in current.stdout:
            raise SystemExit(f"exe did not record a migration revision:\n{current.stdout}")

        doctor = call("doctor")
        if "RDKit 2026" not in doctor.stdout:
            raise SystemExit(f"exe doctor failed to load RDKit:\n{doctor.stdout}\n{doctor.stderr}")

        server = subprocess.Popen(
            [str(exe), "serve", "--port", "8807"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        try:
            if not _wait_ready("http://127.0.0.1:8807/api/v1/ready"):
                raise SystemExit("exe server did not become ready")
        finally:
            server.terminate()

    print(f"smoke test passed for {exe.name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-build", action="store_true", help="reuse the existing exe instead of rebuilding")
    args = parser.parse_args(argv)

    if not args.skip_build:
        build_frontend()
        build_executable()

    exe = exe_path()
    smoke_test(exe)
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    print(f"artifact: {exe} ({exe.stat().st_size} bytes)")
    print(f"sha256:   {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
