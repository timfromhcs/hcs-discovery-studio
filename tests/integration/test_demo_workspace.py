"""Hosted-preview demo workspace and SPA path resolution.

The demo must be real, disposable and non-destructive: it seeds a workspace with
the normal services, computes it with the normal worker, refuses to touch a data
directory that already holds a project, and never invents results.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hcs_discovery import demo
from hcs_discovery.api.app import _resolve_web_dist, create_app
from hcs_discovery.core.config import Settings, reset_settings
from hcs_discovery.database.base import dispose_engines
from hcs_discovery.services import list_projects


@pytest.fixture()
def demo_settings(tmp_path: Path):
    current = Settings(data_dir=tmp_path / "demo-data", network_policy="local", demo_mode=True)
    current.ensure_dirs()
    reset_settings(current)
    dispose_engines()
    yield current
    dispose_engines()
    reset_settings(None)


# ------------------------------------------------------------------ web dist
def test_web_dist_override_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html>", encoding="utf-8")
    monkeypatch.setenv("HCS_WEB_DIST", str(dist))
    assert _resolve_web_dist() == dist.resolve()


def test_invalid_web_dist_override_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A wrong override must not silently fall back to a different build."""
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("HCS_WEB_DIST", str(empty))
    assert _resolve_web_dist() is None


# --------------------------------------------------------------------- demo
def test_demo_workspace_is_real_computed_and_labelled(demo_settings):
    result = demo.ensure_demo_workspace(demo_settings)
    assert result["status"] == "ready", result
    assert result["project_id"]

    app = create_app(demo_settings)
    with TestClient(app) as client:
        projects = client.get("/api/v1/projects").json()["items"]
        assert [item["name"] for item in projects] == [demo.DEMO_PROJECT_NAME]
        project = projects[0]
        assert "synthetic" in project["description"].lower()
        assert project["compound_count"] == 16

        runs = client.get(f"/api/v1/runs?project_id={project['id']}").json()["items"]
        assert len(runs) == 1
        assert runs[0]["status"] == "succeeded"

        results = client.get(f"/api/v1/runs/{runs[0]['id']}/results?limit=5").json()
        assert results["total"] == 16
        metrics = results["items"][0]["metrics"]
        # Real RDKit descriptors, not a fixture table.
        assert {"qed", "mw", "logp"}.issubset(metrics)
        assert results["items"][0]["rank"] == 1

        manifest = client.get(f"/api/v1/runs/{runs[0]['id']}").json()["manifest"]
        assert len(manifest["dataset"]["sha256"]) == 64


def test_demo_seeding_is_idempotent(demo_settings):
    first = demo.ensure_demo_workspace(demo_settings)
    second = demo.ensure_demo_workspace(demo_settings)
    assert first["project_id"] == second["project_id"]
    from hcs_discovery.database.base import get_session_factory

    with get_session_factory(demo_settings)() as session:
        assert len(list_projects(session)) == 1


def test_demo_refuses_to_touch_a_real_project(demo_settings):
    from hcs_discovery.database.base import get_session_factory, init_db
    from hcs_discovery.services import create_project

    init_db(demo_settings)
    with get_session_factory(demo_settings)() as session:
        create_project(session, name="My real research project")

    result = demo.ensure_demo_workspace(demo_settings)
    assert result["status"] == "skipped"
    assert "already holds a project" in result["error"]

    with get_session_factory(demo_settings)() as session:
        names = [item["name"] for item in list_projects(session)]
    assert names == ["My real research project"]


def test_demo_mode_is_off_by_default(settings):
    assert settings.demo_mode is False


def test_demo_status_does_not_seed(demo_settings):
    status = demo.demo_status(demo_settings)
    assert status["projects"] == 0
