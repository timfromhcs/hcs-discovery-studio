"""Lifecycle tests: deletion cascades, disk cleanup, and cache bounds."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from hcs_discovery.cli.main import app
from hcs_discovery.services.datasets import (
    delete_dataset,
    import_dataset,
)
from hcs_discovery.services.projects import (
    create_project,
    delete_project,
    preview_project_deletion,
)
from hcs_discovery.services.runs import create_run
from hcs_discovery.workflow.cache import CachedOutput, NodeCache
from hcs_discovery.workflow.table import Column, Table
from tests.conftest import DEMO_CSV

runner = CliRunner()


def test_project_deletion_cleans_on_disk_files(settings, session, triage_definition):
    # 1. Create project, import dataset, create run
    proj = create_project(session, name="Delete Test Project")
    dts = import_dataset(
        session=session,
        settings=settings,
        project_id=proj.id,
        filename="demo.csv",
        data=DEMO_CSV.read_bytes(),
    )
    run = create_run(
        session=session,
        project_id=proj.id,
        workflow=triage_definition,
        dataset_id=dts.id,
    )

    # Fake run directory on disk
    run_dir = settings.runs_dir / run.id
    run_dir.mkdir(parents=True, exist_ok=True)
    fake_artifact = run_dir / "output.csv"
    fake_artifact.write_text("a,b,c\n1,2,3\n", encoding="utf-8")

    upload_dir = settings.uploads_dir / proj.id
    assert upload_dir.exists()
    assert (upload_dir / f"{dts.id}-demo.csv").exists()

    # 2. Preview deletion
    preview = preview_project_deletion(session, proj.id, settings)
    assert preview["runs_count"] == 1
    assert preview["datasets_count"] == 1
    assert preview["total_disk_bytes"] > 0
    assert str(run_dir) in preview["disk_paths"]

    # 3. Delete with purge_files=True
    delete_project(session, proj.id, purge_files=True, settings=settings)

    # 4. Confirm database and disk cleanup
    assert not run_dir.exists()
    assert not upload_dir.exists()


def test_project_deletion_preserves_files_when_requested(settings, session, triage_definition):
    proj = create_project(session, name="Keep Files Project")
    dts = import_dataset(
        session=session,
        settings=settings,
        project_id=proj.id,
        filename="demo.csv",
        data=DEMO_CSV.read_bytes(),
    )
    run = create_run(
        session=session,
        project_id=proj.id,
        workflow=triage_definition,
        dataset_id=dts.id,
    )
    run_dir = settings.runs_dir / run.id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text("{}", encoding="utf-8")

    delete_project(session, proj.id, purge_files=False, settings=settings)
    assert run_dir.exists()
    assert (run_dir / "manifest.json").exists()


def test_dataset_deletion_cleans_upload(settings, session):
    proj = create_project(session, name="Dts Project")
    dts = import_dataset(
        session=session,
        settings=settings,
        project_id=proj.id,
        filename="demo.csv",
        data=DEMO_CSV.read_bytes(),
    )
    upload_file = settings.uploads_dir / proj.id / f"{dts.id}-demo.csv"
    assert upload_file.exists()

    delete_dataset(session, dts.id, purge_files=True, settings=settings)
    assert not upload_file.exists()


def test_cache_lru_pruning_and_corrupt_detection(tmp_path: Path):
    cache_root = tmp_path / "test_cache"
    cache = NodeCache(cache_root)

    t = Table(rows=[{"x": 1}], columns=[Column("x", "X", "number")])
    output = CachedOutput(table=t, artifacts=[], summary={"ok": True})

    # Put 3 entries
    cache.put("k1" + "0" * 62, output, {})
    cache.put("k2" + "0" * 62, output, {})
    cache.put("k3" + "0" * 62, output, {})

    stats = cache.stats()
    assert stats["entries"] == 3
    assert stats["bytes"] > 0

    # Prune with dry_run
    entries, _size = cache.prune(max_mb=0, dry_run=True)
    assert entries == 3
    assert cache.stats()["entries"] == 3

    # Prune dry_run=False down to 0 MB (removes all)
    entries, _size = cache.prune(max_mb=0, dry_run=False)
    assert entries == 3
    assert cache.stats()["entries"] == 0

    # Corrupt entry detection
    key_corrupt = "kc" + "0" * 62
    corrupt_dir = cache_root / "kc" / key_corrupt
    corrupt_dir.mkdir(parents=True, exist_ok=True)
    (corrupt_dir / "entry.json").write_text("{not valid json", encoding="utf-8")

    # get() on corrupted entry returns None and auto-purges corrupt directory
    assert cache.get(key_corrupt) is None
    assert not corrupt_dir.exists()


def test_cli_cache_prune_and_project_delete_dry_run(settings):
    # Test CLI cache prune
    res = runner.invoke(app, ["--json", "cache", "prune", "--dry-run"])
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert data["dry_run"] is True

    # Test CLI project delete --dry-run
    create_res = runner.invoke(app, ["--json", "project", "create", "--name", "CLI Preview Proj"])
    assert create_res.exit_code == 0
    proj_id = json.loads(create_res.stdout)["id"]

    del_res = runner.invoke(app, ["--json", "project", "delete", proj_id, "--dry-run"])
    assert del_res.exit_code == 0
    del_data = json.loads(del_res.stdout)
    assert del_data["dry_run"] is True
    assert del_data["project_id"] == proj_id

    # Actual delete
    real_del = runner.invoke(app, ["--json", "project", "delete", proj_id, "--yes"])
    assert real_del.exit_code == 0
    real_data = json.loads(real_del.stdout)
    assert real_data["status"] == "deleted"
