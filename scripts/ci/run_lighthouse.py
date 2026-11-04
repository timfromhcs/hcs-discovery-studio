"""Build, preview and Lighthouse-check the SPA with budgets.

    uv run python scripts/ci/run_lighthouse.py

Serves ``apps/web/dist`` on a loopback port, runs
``apps/web/scripts/check_lighthouse.mjs`` against it and stops the server. The build is
reused when it exists; ``--build`` forces a fresh one.

Chrome is found by chrome-launcher on CI. Locally the Playwright Chromium is used when
``CHROME_PATH`` is unset, so the gate works without a system Chrome install.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "apps" / "web"
PORT = 8794


def _npm() -> str:
    return "npm.cmd" if sys.platform == "win32" else "npm"


def _run(argv: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    print("+ " + " ".join(argv), flush=True)
    subprocess.run(argv, cwd=cwd, env=env, check=True)


def _wait_ready(url: str, timeout: float = 60.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.5)
    return False


def _playwright_chrome() -> str | None:
    if sys.platform != "win32":
        return None
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    candidates = sorted(base.glob("chromium-*/chrome-win64/chrome.exe"), reverse=True)
    return str(candidates[0]) if candidates else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="rebuild the SPA first")
    args = parser.parse_args(argv)

    if shutil.which("node") is None or shutil.which(_npm()) is None:
        print("node/npm are not installed; the Lighthouse gate cannot run.", file=sys.stderr)
        return 2
    if args.build or not (WEB / "dist" / "index.html").is_file():
        _run([_npm(), "run", "build"], cwd=WEB)

    env = dict(os.environ)
    if not env.get("CHROME_PATH"):
        detected = _playwright_chrome()
        if detected:
            env["CHROME_PATH"] = detected

    vite = WEB / "node_modules" / "vite" / "bin" / "vite.js"
    server = subprocess.Popen(
        ["node", str(vite), "preview", "--port", str(PORT), "--strictPort", "--host", "127.0.0.1"],
        cwd=WEB,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        if not _wait_ready(f"http://127.0.0.1:{PORT}/"):
            print("the preview server did not become ready.", file=sys.stderr)
            return 1
        return subprocess.run(
            [
                "node",
                "scripts/check_lighthouse.mjs",
                "--base-url",
                f"http://127.0.0.1:{PORT}",
            ],
            cwd=WEB,
            env=env,
        ).returncode
    finally:
        server.terminate()
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
