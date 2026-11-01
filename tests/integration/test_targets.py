"""Target and structure services, API and CLI parity.

Covered: creation with provenance, duplicate rejection, structure import with
checksum and inspection, cross-project attachment refusal, deletion semantics and
the CLI/API paths that must agree with the service layer.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from hcs_discovery.cli.main import app
from hcs_discovery.core.errors import ConflictError, NotFoundError, ValidationError
from hcs_discovery.services import (
    create_project,
    create_target,
    delete_structure,
    delete_target,
    get_structure,
    import_structure,
    list_structures,
    list_targets,
    structure_detail,
    structure_path,
    target_detail,
    update_target,
)
from hcs_discovery.structures.pdb import StructureFormatError

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "structures" / "tiny_two_chain.pdb"
runner = CliRunner()


def _import(session, settings, project_id: str, *, target_id: str | None = None, filename: str = "tiny.pdb"):
    return import_structure(
        session,
        project_id=project_id,
        filename=filename,
        data=FIXTURE.read_bytes(),
        target_id=target_id,
        source="test-fixture",
        accession="1TST",
        license="synthetic-test-data",
        settings=settings,
    )


# ------------------------------------------------------------------- targets
def test_create_and_list_targets(settings, session, project):
    target = create_target(
        session,
        project_id=project.id,
        name="EGFR",
        gene_symbol="EGFR",
        uniprot_id="p00533",
        organism="Homo sapiens",
        notes="Kinase domain",
    )
    assert target.id.startswith("tgt_")
    assert target.uniprot_id == "P00533"  # normalised to upper case
    items = list_targets(session, project.id)
    assert [item["name"] for item in items] == ["EGFR"]
    assert items[0]["structure_count"] == 0


def test_duplicate_target_name_is_rejected_case_insensitively(settings, session, project):
    create_target(session, project_id=project.id, name="EGFR")
    with pytest.raises(ConflictError):
        create_target(session, project_id=project.id, name="egfr")


def test_target_name_must_not_be_empty(settings, session, project):
    with pytest.raises(ValidationError):
        create_target(session, project_id=project.id, name="   ")


def test_unknown_project_is_rejected(settings, session):
    with pytest.raises(NotFoundError):
        create_target(session, project_id="prj_missing", name="EGFR")


def test_update_target_rejects_a_clashing_name(settings, session, project):
    first = create_target(session, project_id=project.id, name="EGFR")
    create_target(session, project_id=project.id, name="KRAS")
    with pytest.raises(ConflictError):
        update_target(session, first.id, name="kras")
    updated = update_target(session, first.id, name="EGFR2", notes="moved")
    assert updated.name == "EGFR2"
    assert updated.notes == "moved"


# ---------------------------------------------------------------- structures
def test_import_structure_records_checksum_and_inspection(settings, session, project):
    target = create_target(session, project_id=project.id, name="EGFR")
    structure = _import(session, settings, project.id, target_id=target.id)

    assert structure.id.startswith("str_")
    assert structure.target_id == target.id
    assert structure.format == "pdb"
    assert len(structure.sha256) == 64
    assert structure.quality["atom_count"] == 9
    assert structure.quality["ligands"] == ["LIG"]
    stored = structure_path(structure, settings)
    assert stored.exists()
    assert stored.parent.name == "structures"


def test_importing_an_unsupported_format_leaves_no_file_behind(settings, session, project):
    before = set(Path(settings.uploads_dir).rglob("*"))
    with pytest.raises(StructureFormatError):
        import_structure(
            session,
            project_id=project.id,
            filename="structure.cif",
            data=b"data_1ABC\n#\n",
            settings=settings,
        )
    after = set(Path(settings.uploads_dir).rglob("*"))
    assert before == after


def test_importing_an_invalid_file_leaves_no_file_and_no_row(settings, session, project):
    with pytest.raises(ValidationError):
        import_structure(
            session,
            project_id=project.id,
            filename="empty.pdb",
            data=b"",
            settings=settings,
        )
    assert list_structures(session, project.id) == []


def test_structure_cannot_attach_to_a_target_in_another_project(settings, session, project):
    other = create_project(session, name="Other project")
    foreign = create_target(session, project_id=other.id, name="KRAS")
    with pytest.raises(ValidationError):
        _import(session, settings, project.id, target_id=foreign.id)


def test_structure_detail_exposes_the_full_inspection(settings, session, project):
    structure = _import(session, settings, project.id)
    payload = structure_detail(session, structure.id)
    assert payload["inspection"]["pdb_id"] == "1TST"
    assert [chain["chain_id"] for chain in payload["inspection"]["chains"]] == ["A", "B"]
    assert payload["summary"]["waters"] == 1


def test_deleting_a_target_keeps_its_structures_and_detaches_them(settings, session, project):
    target = create_target(session, project_id=project.id, name="EGFR")
    structure = _import(session, settings, project.id, target_id=target.id)

    result = delete_target(session, target.id)
    assert result["detached_structures"] == 1

    session.expire_all()
    kept = get_structure(session, structure.id)
    assert kept.target_id is None
    assert structure_path(kept, settings).exists()


def test_deleting_a_structure_removes_file_and_row(settings, session, project):
    structure = _import(session, settings, project.id)
    stored = structure_path(structure, settings)
    assert stored.exists()

    delete_structure(session, structure.id)
    assert not stored.exists()
    assert list_structures(session, project.id) == []
    with pytest.raises(NotFoundError):
        get_structure(session, structure.id)


def test_target_detail_lists_its_structures(settings, session, project):
    target = create_target(session, project_id=project.id, name="EGFR")
    _import(session, settings, project.id, target_id=target.id)
    payload = target_detail(session, target.id)
    assert len(payload["structures"]) == 1
    assert payload["structures"][0]["target_id"] == target.id


# ---------------------------------------------------------------------- API
def test_api_target_and_structure_round_trip(settings, client, session):
    created_project = client.post("/api/v1/projects", json={"name": "API project"}).json()
    project_id = created_project["id"]

    created = client.post(
        f"/api/v1/projects/{project_id}/targets",
        json={"name": "EGFR", "uniprot_id": "P00533", "organism": "Homo sapiens"},
    )
    assert created.status_code == 201, created.text
    target_id = created.json()["id"]

    with FIXTURE.open("rb") as handle:
        uploaded = client.post(
            f"/api/v1/projects/{project_id}/structures",
            files={"file": ("tiny.pdb", handle, "chemical/x-pdb")},
            data={"target_id": target_id, "source": "test-fixture", "license": "synthetic-test-data"},
        )
    assert uploaded.status_code == 201, uploaded.text
    body = uploaded.json()
    assert body["target_id"] == target_id
    assert body["inspection"]["atom_count"] == 9

    listing = client.get(f"/api/v1/projects/{project_id}/structures").json()
    assert len(listing["items"]) == 1

    detail = client.get(f"/api/v1/targets/{target_id}").json()
    assert detail["structures"][0]["id"] == body["id"]

    patched = client.patch(f"/api/v1/targets/{target_id}", json={"notes": "updated"})
    assert patched.status_code == 200
    assert patched.json()["notes"] == "updated"

    assert client.delete(f"/api/v1/structures/{body['id']}").status_code == 204
    assert client.delete(f"/api/v1/targets/{target_id}").status_code == 204


def test_api_rejects_a_duplicate_target(settings, client):
    project_id = client.post("/api/v1/projects", json={"name": "Dup"}).json()["id"]
    first = client.post(f"/api/v1/projects/{project_id}/targets", json={"name": "EGFR"})
    assert first.status_code == 201
    second = client.post(f"/api/v1/projects/{project_id}/targets", json={"name": "EGFR"})
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"


def test_api_reports_a_missing_target_as_404(settings, client):
    response = client.get("/api/v1/targets/tgt_missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# ---------------------------------------------------------------------- CLI
def test_cli_target_lifecycle(settings, tmp_path):
    project = runner.invoke(app, ["--json", "project", "create", "--name", "CLI targets"])
    assert project.exit_code == 0, project.output
    import json

    project_id = json.loads(project.stdout)["id"]

    created = runner.invoke(
        app,
        ["--json", "target", "create", "--project", project_id, "--name", "EGFR", "--uniprot", "P00533"],
    )
    assert created.exit_code == 0, created.output
    target_id = json.loads(created.stdout)["id"]

    imported = runner.invoke(
        app,
        [
            "--json",
            "target",
            "import-structure",
            str(FIXTURE),
            "--project",
            project_id,
            "--target",
            target_id,
            "--source",
            "test-fixture",
        ],
    )
    assert imported.exit_code == 0, imported.output
    structure = json.loads(imported.stdout)
    assert structure["inspection"]["atom_count"] == 9

    human_list = runner.invoke(app, ["target", "list", "--project", project_id])
    assert human_list.exit_code == 0
    assert "EGFR" in human_list.stdout
    assert "1 structure(s)" in human_list.stdout

    human_show = runner.invoke(app, ["target", "show", target_id])
    assert human_show.exit_code == 0
    assert "9 atoms" in human_show.stdout

    human_structure = runner.invoke(app, ["target", "structure", structure["id"]])
    assert human_structure.exit_code == 0
    assert "ligands: LIG" in human_structure.stdout

    deleted = runner.invoke(app, ["target", "delete", target_id, "--yes"])
    assert deleted.exit_code == 0
    assert "detached 1 structure" in deleted.stdout

    removed = runner.invoke(app, ["target", "delete-structure", structure["id"], "--yes"])
    assert removed.exit_code == 0


def test_cli_reports_a_missing_target_with_the_not_found_exit_code(settings):
    result = runner.invoke(app, ["--json", "target", "show", "tgt_missing"])
    assert result.exit_code == 4
    assert "not_found" in result.stderr or "not_found" in result.stdout
