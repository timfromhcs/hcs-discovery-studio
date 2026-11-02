"""Wheel helpers for ``scripts/gates.py`` (G8 and G14).

The CI wheel job is a bash script; this module is the same thing without a shell, so the
gate runs on Windows too. It is deliberately small: create a throw-away virtual
environment, install the freshly built wheel, and run the same smoke commands CI runs
(``version``, ``doctor``, ``db upgrade``, ``db current``, then a real ``serve`` with
``/api/v1/health``, ``/api/v1/ready`` and the SPA root).

    python scripts/gates_wheel.py install
    python scripts/gates_wheel.py smoke
    python scripts/gates_wheel.py metadata
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DIST = REPO_ROOT / "dist"
VENV = REPO_ROOT / "build" / "wheel-venv"
BUILD = REPO_ROOT / "build"


def _newest_wheel() -> Path:
    wheels = sorted(DIST.glob("*.whl"), key=lambda path: path.stat().st_mtime)
    if not wheels:
        raise SystemExit(f"no wheel in {DIST}; run 'uv build --wheel' first")
    return wheels[-1]


def _venv_python() -> Path:
    candidate = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not candidate.exists():
        raise SystemExit(f"{candidate} is missing; run 'python scripts/gates_wheel.py install' first")
    return candidate


def install() -> int:
    wheel = _newest_wheel()
    if VENV.exists():
        import shutil

        shutil.rmtree(VENV)
    subprocess.run(["uv", "venv", str(VENV)], cwd=REPO_ROOT, check=True)
    python = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    print(f"installing {wheel.name} into {VENV}")
    subprocess.run(["uv", "pip", "install", "--python", str(python), str(wheel)], cwd=REPO_ROOT, check=True)
    return 0


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait(url: str, process: subprocess.Popen, timeout: float = 60.0) -> str:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        if process.poll() is not None:
            raise SystemExit(f"server exited early with {process.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=2.0) as response:
                return response.read().decode("utf-8", "replace")
        except (urllib.error.URLError, OSError) as exc:  # server not up yet
            last = str(exc)
            time.sleep(0.5)
    raise SystemExit(f"{url} did not answer within {timeout:g}s ({last})")


def smoke() -> int:
    python = _venv_python()
    binary = python.parent / ("hcs-discovery.exe" if os.name == "nt" else "hcs-discovery")
    data_dir = BUILD / "wheel-data"
    env = dict(os.environ)
    env["HCS_DATA_DIR"] = str(data_dir)
    for command in (["version"], ["doctor"], ["db", "upgrade"], ["db", "current"]):
        completed = subprocess.run([str(binary), *command], env=env, capture_output=True, text=True)
        print(f"$ hcs-discovery {' '.join(command)} -> exit {completed.returncode}")
        if completed.returncode != 0:
            print(completed.stdout[-2000:])
            print(completed.stderr[-2000:])
            return completed.returncode
    database = data_dir / "hcs.sqlite3"
    if not database.exists() or database.stat().st_size == 0:
        print(f"database {database} is missing or empty", file=sys.stderr)
        return 1

    port = _free_port()
    process = subprocess.Popen(
        [str(binary), "serve", "--port", str(port)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        print(_wait(f"{base}/api/v1/health", process)[:200])
        ready = _wait(f"{base}/api/v1/ready", process)
        if '"status":"ready"' not in ready:
            print(f"/api/v1/ready did not report ready: {ready[:300]}", file=sys.stderr)
            return 1
        root = _wait(f"{base}/", process)
        if 'id="root"' not in root:
            print('the served SPA root does not contain id="root"', file=sys.stderr)
            return 1
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
    print("wheel smoke test passed")
    return 0


def metadata() -> int:
    wheel = _newest_wheel()
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
        metadata_text = archive.read(metadata_name).decode("utf-8", "replace")
        fields = dict(
            line.split(": ", 1) for line in metadata_text.splitlines() if ": " in line and not line.startswith(" ")
        )
        assets = [name for name in names if name.startswith("hcs_discovery/web/")]
    report = {
        "wheel": wheel.name,
        "name": fields.get("Name"),
        "version": fields.get("Version"),
        "license": fields.get("License"),
        "web_assets": len(assets),
    }
    print(json.dumps(report, indent=2))
    if not report["version"]:
        print("the wheel metadata carries no Version", file=sys.stderr)
        return 1
    if not assets:
        print("the wheel carries no bundled web assets", file=sys.stderr)
        return 1
    return 0


COMMANDS = {"install": install, "smoke": smoke, "metadata": metadata}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or args[0] not in COMMANDS:
        print(__doc__, file=sys.stderr)
        return 2
    return COMMANDS[args[0]]()


if __name__ == "__main__":
    raise SystemExit(main())
