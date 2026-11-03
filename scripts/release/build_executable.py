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

PyInstaller is a build-only tool and is deliberately kept out of the lockfile
(its bootloader is GPL-with-exception). Install it into the environment first:

    uv pip install "pyinstaller==6.22.3"
"""

from __future__ import annotations

import argparse
import hashlib
import json
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
    # Windows resolves npm/npx through .cmd shims, which CreateProcess does not
    # find from a bare name. CI runs on Linux; a developer on Windows must not get
    # a FileNotFoundError for a script that is otherwise correct.
    resolved = list(argv)
    if sys.platform == "win32" and resolved and resolved[0] in {"npm", "npx"}:
        resolved[0] = f"{resolved[0]}.cmd"
    print("+ " + " ".join(resolved), flush=True)
    return subprocess.run(
        resolved, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=check
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
    # Run a copy of the binary, not build/exe-dist/hcs-discovery.exe: a one-file
    # PyInstaller executable keeps its own file open while it runs, so the next build
    # would fail with a PermissionError on a file the smoke test itself started.
    with tempfile.TemporaryDirectory(prefix="hcs-exe-smoke-", ignore_cleanup_errors=True) as data_dir:
        env["HCS_DATA_DIR"] = data_dir
        target = Path(data_dir) / exe.name
        shutil.copy2(exe, target)

        def call(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [str(target), *args], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace"
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

        # The GPU path is optional on the host, never on the bundle: if the frozen
        # executable can see an adapter, the WGSL kernel must be inside it and the
        # verified GPU search must actually run there (a missing kernel data file
        # used to fall back to the CPU without saying so).
        probe = json.loads(call("gpu", "probe").stdout or "{}")
        if probe.get("status") == "available":
            library = REPO_ROOT / "examples" / "datasets" / "demo_library.csv"
            gpu_run = call(
                "similarity", "search", "--query", "c1ccccc1", "--file", str(library), "--engine", "gpu", "--json"
            )
            try:
                payload = json.loads(gpu_run.stdout)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"exe GPU search produced no JSON:\n{gpu_run.stdout}\n{gpu_run.stderr}") from exc
            if payload.get("engine", {}).get("name") != "gpu" or not payload.get("parity_checked"):
                raise SystemExit(
                    "exe GPU similarity search did not run on the adapter, although the adapter is available:\n"
                    + json.dumps(payload, indent=2)[:1000]
                )

        server = subprocess.Popen(
            [str(target), "serve", "--port", "8807"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        try:
            if not _wait_ready("http://127.0.0.1:8807/api/v1/ready"):
                raise SystemExit("exe server did not become ready")
        finally:
            server.terminate()
            try:
                server.wait(timeout=30)
            except subprocess.TimeoutExpired:  # pragma: no cover - defensive
                server.kill()
                server.wait(timeout=10)

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
