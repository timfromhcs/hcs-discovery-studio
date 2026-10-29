"""Cache integrity and worker-lease heartbeat contracts."""

from __future__ import annotations

import json
import time
from pathlib import Path

from hcs_discovery.core.timeutil import db_now
from hcs_discovery.database.base import get_session_factory
from hcs_discovery.services.runs import create_run
from hcs_discovery.workflow.cache import CachedOutput, NodeCache
from hcs_discovery.workflow.executor import _LeaseHeartbeat
from hcs_discovery.workflow.table import Column, Table

KEY = "ab" + "0" * 62


def _output(tmp_path: Path) -> tuple[CachedOutput, dict[str, Path]]:
    artifact = tmp_path / "summary.md"
    artifact.write_text("# summary\n", encoding="utf-8")
    table = Table(rows=[{"x": 1.0}], columns=[Column("x", "X", "number")])
    output = CachedOutput(
        table=table,
        artifacts=[
            {
                "filename": "summary.md",
                "media_type": "text/markdown",
                "kind": "node_artifact",
            }
        ],
        summary={"rows": 1},
    )
    return output, {"summary.md": artifact}


def _entry(cache: NodeCache) -> Path:
    return cache.root / KEY[:2] / KEY


def test_cache_round_trip_verifies_content_and_artifacts(tmp_path: Path):
    cache = NodeCache(tmp_path / "cache")
    output, files = _output(tmp_path)
    assert cache.put(KEY, output, files) is True

    cached = cache.get(KEY)
    assert cached is not None
    assert cached.table.rows == [{"x": 1.0}]
    assert cached.summary == {"rows": 1}

    manifest = json.loads((_entry(cache) / "entry.json").read_text(encoding="utf-8"))
    assert manifest["content_hash"] == output.table.content_hash()
    assert manifest["artifacts"][0]["sha256"]


def test_cache_rejects_tampered_rows(tmp_path: Path):
    cache = NodeCache(tmp_path / "cache")
    output, files = _output(tmp_path)
    assert cache.put(KEY, output, files)

    manifest_path = _entry(cache) / "entry.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["rows"] = [{"x": 999.0}]
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    assert cache.get(KEY) is None
    assert not _entry(cache).exists()


def test_cache_rejects_tampered_or_missing_artifact(tmp_path: Path):
    cache = NodeCache(tmp_path / "cache")
    output, files = _output(tmp_path)
    assert cache.put(KEY, output, files)

    artifact_path = _entry(cache) / "artifacts" / "summary.md"
    artifact_path.write_text("# tampered\n", encoding="utf-8")
    assert cache.get(KEY) is None

    assert cache.put(KEY, output, files)
    artifact_path.unlink()
    assert cache.get(KEY) is None


def test_cache_refuses_to_publish_when_an_artifact_is_missing(tmp_path: Path):
    cache = NodeCache(tmp_path / "cache")
    output, _files = _output(tmp_path)
    assert cache.put(KEY, output, {"summary.md": tmp_path / "does-not-exist.md"}) is False
    assert not _entry(cache).exists()
    assert cache.get(KEY) is None


def test_lease_heartbeat_renews_and_detects_loss(settings, session, triage_definition, project, dataset):
    run = create_run(
        session=session,
        project_id=project.id,
        workflow=triage_definition,
        dataset_id=dataset.id,
    )
    run.lease_owner = "worker-a"
    run.lease_expires_at = db_now()
    run.heartbeat_at = None
    session.commit()
    factory = get_session_factory(settings)

    beat = _LeaseHeartbeat(factory, run_id=run.id, worker_id="worker-a", lease_seconds=1, interval=0.05)
    beat.start()
    time.sleep(0.3)
    beat.stop()

    session.refresh(run)
    assert beat.lost is False
    assert run.heartbeat_at is not None
    assert run.lease_expires_at is not None and run.lease_expires_at > db_now()

    stale = _LeaseHeartbeat(factory, run_id=run.id, worker_id="worker-b", lease_seconds=1, interval=0.05)
    stale.start()
    time.sleep(0.3)
    stale.stop()
    assert stale.lost is True
