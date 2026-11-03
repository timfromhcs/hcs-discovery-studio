"""Inline execution: a hosted instance completes a run without a worker process.

``HCS_RUN_MODE=inline`` exists for serverless hosts, where the embedded worker
thread cannot survive the HTTP response. The default (``queue``) must not change:
the run stays queued until a worker claims it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hcs_discovery.api.app import create_app
from hcs_discovery.core.config import Settings, reset_settings
from hcs_discovery.database.base import dispose_engines, init_db

DEMO_CSV = Path(__file__).resolve().parents[2] / "examples" / "datasets" / "demo_library.csv"


def _client_for(tmp_path: Path, **overrides) -> tuple[TestClient, Settings]:
    data_dir = tmp_path / "data"
    current = Settings(
        data_dir=data_dir,
        network_policy="local",
        max_import_rows=5000,
        **overrides,
    )
    current.ensure_dirs()
    reset_settings(current)
    dispose_engines()
    init_db(current)
    return TestClient(create_app(current)), current


@pytest.fixture()
def inline_client(tmp_path: Path):
    client, current = _client_for(tmp_path, run_mode="inline")
    with client:
        yield client, current
    dispose_engines()
    reset_settings(None)


def _prepare(client: TestClient) -> tuple[str, str]:
    project = client.post("/api/v1/projects", json={"name": "inline", "description": ""}).json()
    dataset = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        files={"file": ("demo_library.csv", DEMO_CSV.read_bytes(), "text/csv")},
    ).json()
    return project["id"], dataset["id"]


def test_inline_mode_completes_the_run_inside_the_request(inline_client, triage_definition):
    client, _settings = inline_client
    project_id, dataset_id = _prepare(client)

    created = client.post(
        "/api/v1/runs",
        json={
            "project_id": project_id,
            "dataset_id": dataset_id,
            "workflow": triage_definition,
            "seed": 3,
        },
    )

    assert created.status_code == 202, created.text
    payload = created.json()
    assert payload["execution"] == "inline"
    assert payload["status"] == "succeeded"
    assert payload["inline_status"] == "succeeded"
    assert all(node["status"] == "succeeded" for node in payload["nodes"])

    results = client.get(f"/api/v1/runs/{payload['id']}/results", params={"limit": 5}).json()
    assert results["total"] == 16


def test_queue_mode_still_leaves_the_run_pending(client, triage_definition):
    project_id, dataset_id = _prepare(client)

    payload = client.post(
        "/api/v1/runs",
        json={
            "project_id": project_id,
            "dataset_id": dataset_id,
            "workflow": triage_definition,
        },
    ).json()

    assert payload["status"] == "queued"
    assert "execution" not in payload


def test_inline_retry_executes_the_new_run(inline_client, triage_definition):
    client, _settings = inline_client
    project_id, dataset_id = _prepare(client)
    first = client.post(
        "/api/v1/runs",
        json={
            "project_id": project_id,
            "dataset_id": dataset_id,
            "workflow": triage_definition,
        },
    ).json()

    retried = client.post(f"/api/v1/runs/{first['id']}/retry")

    assert retried.status_code == 202, retried.text
    body = retried.json()
    assert body["id"] != first["id"]
    assert body["execution"] == "inline"
    assert body["status"] == "succeeded"
