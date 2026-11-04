"""RO-Crate export: structure, hashes, PROV mapping and refusal to drop evidence."""

from __future__ import annotations

import json
import zipfile

import pytest

from hcs_discovery.core.errors import NotFoundError
from hcs_discovery.database.base import get_session_factory
from hcs_discovery.reports.render import load_report_data
from hcs_discovery.reports.rocrate import SCHEMA, export_ro_crate
from hcs_discovery.services import create_run
from hcs_discovery.workflow.executor import RunExecutor


def _run(settings, session, project, dataset, definition):
    run = create_run(session, project_id=project.id, workflow=definition, dataset_id=dataset.id)
    executor = RunExecutor(
        run_id=run.id,
        session_factory=get_session_factory(settings),
        settings=settings,
        worker_id="rocrate-test",
    )
    assert executor.execute() == "succeeded"
    session.expire_all()
    return run


def test_ro_crate_contains_every_artifact_with_matching_hashes(settings, session, project, dataset, triage_definition):
    run = _run(settings, session, project, dataset, triage_definition)
    target = export_ro_crate(session, settings, run.id, settings.data_dir / "exports" / f"{run.id}.crate.zip")
    assert zipfile.is_zipfile(target)

    with zipfile.ZipFile(target) as archive:
        names = set(archive.namelist())
        assert "ro-crate-metadata.json" in names
        document = json.loads(archive.read("ro-crate-metadata.json"))
        data = load_report_data(session, run.id)
        for artifact in data["artifacts"]:
            path = f"artifacts/{artifact['rel_path']}"
            assert path in names, path
            import hashlib

            assert hashlib.sha256(archive.read(path)).hexdigest() == artifact["sha256"]

    graph = {entity["@id"]: entity for entity in document["@graph"]}
    assert document["@context"] == "https://w3id.org/ro/crate/1.1/context"
    assert graph["./"]["@type"] == "Dataset"
    action = graph["#run"]
    assert "CreateAction" in action["@type"] and "prov:Activity" in action["@type"]
    assert action["actionStatus"]["@id"].endswith("CompletedActionStatus")
    assert action["instrument"]["@id"] == "#workflow"
    assert graph["#workflow"]["identifier"] == data["run"]["workflow_hash"]
    assert graph["#software"]["softwareVersion"] == data["product"]["version"]
    assert SCHEMA in graph["ro-crate-metadata.json"]["description"]
    # No absolute paths and no secrets in the document.
    text = json.dumps(document)
    assert "C:\\" not in text and "/tmp/" not in text
    assert "token" not in text.lower() and "api_key" not in text.lower()


def test_ro_crate_is_deterministic_for_the_same_run(settings, session, project, dataset, triage_definition):
    run = _run(settings, session, project, dataset, triage_definition)
    first = export_ro_crate(session, settings, run.id, settings.data_dir / "exports" / "a.zip")
    second = export_ro_crate(session, settings, run.id, settings.data_dir / "exports" / "b.zip")
    assert first.read_bytes() == second.read_bytes()


def test_ro_crate_refuses_to_skip_a_missing_artifact(settings, session, project, dataset, triage_definition):
    run = _run(settings, session, project, dataset, triage_definition)
    data = load_report_data(session, run.id)
    victim = settings.runs_dir / run.id / data["artifacts"][0]["rel_path"]
    victim.unlink()
    with pytest.raises(NotFoundError, match="incomplete crate"):
        export_ro_crate(session, settings, run.id, settings.data_dir / "exports" / "broken.zip")
    assert not (settings.data_dir / "exports" / "broken.zip").exists()
