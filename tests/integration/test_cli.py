"""CLI contract tests: exit codes, JSON output and headless parity."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from hcs_discovery.cli.main import app
from tests.conftest import DEMO_CSV, TRIAGE_YAML

runner = CliRunner()


def _json(result) -> dict:  # type: ignore[no-untyped-def]
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def test_doctor_json(settings):
    result = runner.invoke(app, ["--json", "doctor"])
    payload = _json(result)
    ids = {check["id"] for check in payload["checks"]}
    assert {"data_dir", "database", "rdkit"} <= ids
    assert "llm_api_key" not in json.dumps(payload)


def test_project_and_dataset_flow(settings, tmp_path: Path):
    created = _json(runner.invoke(app, ["--json", "project", "create", "--name", "CLI project"]))
    project_id = created["id"]
    listing = _json(runner.invoke(app, ["--json", "project", "list"]))
    assert listing["items"][0]["id"] == project_id

    imported = runner.invoke(app, ["--json", "dataset", "import", str(DEMO_CSV), "--project", project_id])
    assert imported.exit_code == 0, imported.output
    dataset = json.loads(imported.output)
    assert dataset["imported"] == 16
    assert dataset["errors"] == 0

    errors = _json(runner.invoke(app, ["--json", "dataset", "errors", dataset["id"]]))
    assert errors["items"] == []


def test_workflow_validate_and_run(settings, tmp_path: Path):
    project = _json(runner.invoke(app, ["--json", "project", "create", "--name", "Run project"]))
    dataset = _json(runner.invoke(app, ["--json", "dataset", "import", str(DEMO_CSV), "--project", project["id"]]))
    valid = _json(runner.invoke(app, ["--json", "workflow", "validate", str(TRIAGE_YAML)]))
    assert valid["valid"] is True

    submitted = _json(
        runner.invoke(
            app,
            [
                "--json",
                "workflow",
                "run",
                str(TRIAGE_YAML),
                "--project",
                project["id"],
                "--dataset",
                dataset["id"],
                "--no-follow",
            ],
        )
    )
    run_id = submitted["run_id"]
    assert run_id.startswith("run_")

    worker = runner.invoke(app, ["--json", "worker", "--once"])
    assert worker.exit_code == 0, worker.output
    status = _json(runner.invoke(app, ["--json", "run", "status", run_id]))
    assert status["status"] == "succeeded"
    assert all(node["status"] == "succeeded" for node in status["nodes"])

    results = _json(runner.invoke(app, ["--json", "run", "results", run_id, "--limit", "3"]))
    assert results["items"][0]["rank"] == 1

    target = tmp_path / "report.html"
    exported = _json(
        runner.invoke(app, ["--json", "report", "export", run_id, "--format", "html", "--output", str(target)])
    )
    assert Path(exported["output"]).exists()
    assert "not measurements" in target.read_text(encoding="utf-8")


def test_compounds_validate_exit_codes(settings, tmp_path: Path):
    good = runner.invoke(app, ["--json", "compounds", "validate", str(DEMO_CSV)])
    assert good.exit_code == 0
    assert json.loads(good.output)["error_count"] == 0

    bad_file = tmp_path / "bad.csv"
    bad_file.write_text("smiles,id\nnot-a-molecule,1\nCCO,2\n", encoding="utf-8")
    bad = runner.invoke(app, ["--json", "compounds", "validate", str(bad_file)])
    assert bad.exit_code == 1
    payload = json.loads(bad.output)
    assert payload["error_count"] == 1
    assert payload["imported_count"] == 1


def test_config_show_never_prints_secrets(settings):
    settings.llm_api_key = "super-secret-key-value"
    result = runner.invoke(app, ["--json", "config", "show"])
    assert result.exit_code == 0
    assert "super-secret-key-value" not in result.output
    assert json.loads(result.output)["llm_api_key"] == "configured"


def test_models_list_marks_planned_engines(settings):
    payload = _json(runner.invoke(app, ["--json", "models", "list"]))
    by_id = {item["id"]: item for item in payload["items"]}
    assert by_id["science:rdkit"]["status"] == "available"
    assert by_id["science:openmm"]["status"] == "planned"


def test_cache_status_and_clear(settings):
    status = _json(runner.invoke(app, ["--json", "cache", "status"]))
    assert status["entries"] == 0
    dry = _json(runner.invoke(app, ["--json", "cache", "clear", "--dry-run"]))
    assert dry["dry_run"] is True


def test_invalid_workflow_exits_with_validation_code(settings, tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("schema_version: 1\nname: broken\nnodes: []\nedges: []\n", encoding="utf-8")
    result = runner.invoke(app, ["--json", "workflow", "validate", str(bad)])
    assert result.exit_code == 3
    assert json.loads(result.output)["error"]["code"] == "validation_error"


def test_cli_on_uninitialized_database(tmp_path: Path):
    from hcs_discovery.core.config import Settings, reset_settings
    from hcs_discovery.database.base import dispose_engines

    data_dir = tmp_path / "uninitialized_data"
    current = Settings(data_dir=data_dir, network_policy="local")
    reset_settings(current)
    dispose_engines()
    try:
        created = _json(runner.invoke(app, ["--json", "project", "create", "--name", "Auto Project"]))
        assert created["name"] == "Auto Project"
        assert (data_dir / "hcs.sqlite3").exists()
    finally:
        dispose_engines()
        reset_settings(None)
