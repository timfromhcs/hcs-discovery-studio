"""HTTP API contract tests covering the full local flow."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from hcs_discovery.api.app import create_app
from hcs_discovery.core.config import Settings
from hcs_discovery.core.errors import PolicyError
from hcs_discovery.jobs.worker import Worker
from tests.conftest import DEMO_CSV


def _create_project(client) -> dict:
    response = client.post("/api/v1/projects", json={"name": "API project", "description": "via HTTP"})
    assert response.status_code == 201, response.text
    return response.json()


def _import(client, project_id: str) -> dict:
    response = client.post(
        f"/api/v1/projects/{project_id}/datasets",
        files={"file": ("demo_library.csv", DEMO_CSV.read_bytes(), "text/csv")},
        data={"format": "auto"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_health_ready_and_about(client):
    assert client.get("/api/v1/health").json()["status"] == "ok"
    ready = client.get("/api/v1/ready").json()
    assert ready["database"] == "ok"
    about = client.get("/api/v1/about").json()
    assert about["product"] == "HCS Discovery Studio"
    assert "hcsmedia" in about["credit"]
    assert client.get("/api/v1/diagnostics").json()["status"] in {"ok", "degraded"}


def test_project_crud(client):
    project = _create_project(client)
    assert project["id"].startswith("prj_")
    listed = client.get("/api/v1/projects").json()["items"]
    assert [item["id"] for item in listed] == [project["id"]]
    overview = client.get(f"/api/v1/projects/{project['id']}").json()
    assert overview["project"]["name"] == "API project"
    assert overview["counts"]["compounds"] == 0
    assert client.delete(f"/api/v1/projects/{project['id']}").status_code == 204
    assert client.get(f"/api/v1/projects/{project['id']}").status_code == 404


def test_import_dataset_and_inspect_rows(client):
    project = _create_project(client)
    dataset = _import(client, project["id"])
    assert dataset["record_count"] == 17
    assert dataset["imported_count"] == 16
    assert dataset["duplicate_count"] == 1

    rows = client.get(f"/api/v1/datasets/{dataset['id']}/rows", params={"status": "duplicate"}).json()
    assert rows["total"] == 1
    assert "Duplicate" in rows["items"][0]["error"]

    compounds = client.get(f"/api/v1/projects/{project['id']}/compounds", params={"q": "aspirin"}).json()
    assert compounds["total"] == 1
    assert compounds["items"][0]["descriptors"]["mw"] > 100

    detail = client.get(f"/api/v1/compounds/{compounds['items'][0]['id']}").json()
    assert detail["source"]["dataset_id"] == dataset["id"]
    assert detail["descriptors"]["qed"]["unit"] == "score (0-1)"

    svg = client.get(f"/api/v1/compounds/{detail['id']}/depiction.svg")
    assert svg.status_code == 200
    assert svg.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in svg.text


def test_workflow_validation_endpoint(client, triage_definition):
    ok = client.post("/api/v1/workflows/validate", json={"definition": triage_definition})
    assert ok.status_code == 200
    assert ok.json()["valid"] is True
    assert ok.json()["order"][0] == "descriptors"

    broken = json.loads(json.dumps(triage_definition))
    broken["nodes"][0]["type"] = "not.a.node"
    response = client.post("/api/v1/workflows/validate", json={"definition": broken})
    assert response.status_code == 422
    issues = response.json()["error"]["details"]["issues"]
    assert any(issue["code"] == "unknown_node_type" for issue in issues)


def test_saved_workflow_crud(client):
    project = _create_project(client)
    catalog = client.get("/api/v1/workflow-catalog").json()
    assert any(node["type"] == "chem.descriptors" for node in catalog["items"])
    definition = catalog["templates"][0]
    created = client.post("/api/v1/workflows", json={"project_id": project["id"], "definition": definition})
    assert created.status_code == 201, created.text
    workflow = created.json()
    fetched = client.get(f"/api/v1/workflows/{workflow['id']}").json()
    assert fetched["content_hash"] == workflow["content_hash"]
    listing = client.get(f"/api/v1/projects/{project['id']}/workflows").json()["items"]
    assert listing[0]["id"] == workflow["id"]
    assert client.delete(f"/api/v1/workflows/{workflow['id']}").status_code == 204


def test_full_run_flow_over_http(client, settings, triage_definition):
    project = _create_project(client)
    dataset = _import(client, project["id"])
    created = client.post(
        "/api/v1/runs",
        json={
            "project_id": project["id"],
            "dataset_id": dataset["id"],
            "workflow": triage_definition,
            "seed": 7,
        },
    )
    assert created.status_code == 202, created.text
    run = created.json()
    assert run["status"] == "queued"

    worker = Worker(settings=settings, worker_id="api-test-worker")
    assert worker.run_once() is not None

    detail = client.get(f"/api/v1/runs/{run['id']}").json()
    assert detail["status"] == "succeeded"
    assert detail["seed"] == 7
    assert all(node["status"] == "succeeded" for node in detail["nodes"])

    results = client.get(f"/api/v1/runs/{run['id']}/results", params={"limit": 10}).json()
    assert results["total"] == 16
    assert results["items"][0]["rank"] == 1
    assert results["columns"]

    events = client.get(f"/api/v1/runs/{run['id']}/events").json()
    assert events["items"][0]["type"] == "run.started"
    assert events["last_seq"] > 0

    artifacts = detail["artifacts"]
    csv_artifact = next(item for item in artifacts if item["rel_path"] == "results.csv")
    download = client.get(f"/api/v1/runs/{run['id']}/artifacts/{csv_artifact['id']}")
    assert download.status_code == 200
    assert download.headers["x-artifact-sha256"] == csv_artifact["sha256"]
    assert download.text.splitlines()[0].startswith("compound_id")

    html = client.get(f"/api/v1/runs/{run['id']}/report", params={"format": "html"})
    assert html.status_code == 200
    assert "Run report" in html.text
    markdown = client.get(f"/api/v1/runs/{run['id']}/report", params={"format": "markdown"}).text
    assert "# Basic triage - run report" in markdown
    assert "Limitations" in markdown
    payload = client.get(f"/api/v1/runs/{run['id']}/report", params={"format": "json"}).json()
    assert payload["run"]["status"] == "succeeded"
    assert "not measurements" in payload["caveat"]


def test_cancel_queued_run_and_retry(client, triage_definition):
    project = _create_project(client)
    dataset = _import(client, project["id"])
    run = client.post(
        "/api/v1/runs",
        json={
            "project_id": project["id"],
            "dataset_id": dataset["id"],
            "workflow": triage_definition,
        },
    ).json()
    cancelled = client.post(f"/api/v1/runs/{run['id']}/cancel").json()
    assert cancelled["status"] == "cancelled"
    retry = client.post(f"/api/v1/runs/{run['id']}/retry")
    assert retry.status_code == 202
    assert retry.json()["id"] != run["id"]


def test_models_registry_reports_planned_engines_honestly(client):
    items = client.get("/api/v1/models").json()["items"]
    statuses = {item["id"]: item["status"] for item in items}
    assert statuses["science:rdkit"] == "available"
    assert statuses["science:autodock-vina"] == "planned"
    vina = next(item for item in items if item["id"] == "science:autodock-vina")
    assert vina["implemented"] is False


def test_invalid_dataset_import_is_rejected(client):
    project = _create_project(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        files={"file": ("empty.csv", b"", "text/csv")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"

    no_smiles = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        files={"file": ("weird.csv", b"a,b\n1,2\n", "text/csv")},
    )
    assert no_smiles.status_code == 422


def test_upload_limit_is_enforced(settings, client):
    project = _create_project(client)
    big = b"smiles\n" + b"CCO\n" * 500_000
    response = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        files={"file": ("big.csv", big, "text/csv")},
    )
    assert response.status_code == 422
    assert "limit" in response.json()["error"]["message"].lower()


def test_cache_clear_requires_confirmation(client):
    assert client.delete("/api/v1/cache").status_code == 422
    cleared = client.delete("/api/v1/cache", params={"confirm": "true"}).json()
    assert "removed_entries" in cleared


def test_unknown_routes_return_structured_errors(client):
    response = client.get("/api/v1/runs/run_missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_remote_binding_requires_token(settings):
    with pytest.raises(PolicyError):
        create_app(Settings(data_dir=settings.data_dir, host="0.0.0.0"))


def test_remote_binding_authenticates(settings):
    remote = Settings(
        data_dir=settings.data_dir,
        host="0.0.0.0",
        api_token="test-token-value",
        network_policy="local",
    )
    app = create_app(remote)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        assert test_client.get("/api/v1/health").status_code == 200
        assert test_client.get("/api/v1/projects").status_code == 401
        headers = {"Authorization": "Bearer test-token-value"}
        assert test_client.get("/api/v1/projects", headers=headers).status_code == 200
        assert test_client.get("/api/v1/projects", headers={"Authorization": "Bearer wrong"}).status_code == 401
