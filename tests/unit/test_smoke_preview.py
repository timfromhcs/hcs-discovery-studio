"""The preview smoke test must fail on a demo that is not there.

The script is only useful if it can be wrong. These tests serve canned responses from a
local HTTP server: the healthy case must pass, and each missing piece (no ready endpoint,
no demo project, no finished run, no word "synthetic") must turn the run red.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("smoke_preview", REPO_ROOT / "scripts" / "ci" / "smoke_preview.py")
smoke = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = smoke
SPEC.loader.exec_module(smoke)


class _Handler(BaseHTTPRequestHandler):
    routes: ClassVar[dict] = {}
    page: str = '<html><body><div id="root"></div>synthetic demo</body></html>'

    def do_GET(self):
        if self.path == "/":
            payload, status = self.page.encode("utf-8"), 200
            content_type = "text/html; charset=utf-8"
        elif self.path in self.routes:
            status, body = self.routes[self.path]
            payload, content_type = json.dumps(body).encode("utf-8"), "application/json"
        else:
            payload, status, content_type = b"{}", 404, "application/json"
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):  # keep the test output clean
        return


@pytest.fixture()
def server():
    handler = type("Handler", (_Handler,), {})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}", handler
    finally:
        httpd.shutdown()
        httpd.server_close()


def _healthy(handler) -> None:
    handler.routes = {
        "/api/v1/health": (200, {"status": "ok"}),
        "/api/v1/ready": (200, {"status": "ready"}),
        "/api/v1/projects": (200, {"items": [{"id": "p1", "name": "Synthetic demo library"}]}),
        "/api/v1/projects/p1/runs": (200, {"items": [{"id": "r1", "status": "finished"}]}),
    }


def test_healthy_preview_passes(server) -> None:
    base, handler = server
    _healthy(handler)
    results = smoke.check(base)
    assert all(entry["ok"] for entry in results), [entry for entry in results if not entry["ok"]]


def test_missing_demo_project_fails(server) -> None:
    base, handler = server
    _healthy(handler)
    handler.routes["/api/v1/projects"] = (200, {"items": [{"id": "p9", "name": "unrelated"}]})
    results = {entry["check"]: entry for entry in smoke.check(base)}
    assert results["demo project present"]["ok"] is False


def test_unfinished_run_fails(server) -> None:
    base, handler = server
    _healthy(handler)
    handler.routes["/api/v1/projects/p1/runs"] = (200, {"items": [{"id": "r1", "status": "failed"}]})
    results = {entry["check"]: entry for entry in smoke.check(base)}
    assert results["a run finished"]["ok"] is False


def test_missing_synthetic_word_fails(server) -> None:
    base, handler = server
    _healthy(handler)
    handler.page = '<html><body><div id="root"></div></body></html>'
    results = {entry["check"]: entry for entry in smoke.check(base)}
    assert results["page says synthetic"]["ok"] is False


def test_unreachable_deployment_exits_two() -> None:
    assert smoke.main(["http://127.0.0.1:1", "--json"]) == 2
