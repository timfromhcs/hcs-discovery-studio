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


def test_cache_key_changes_with_every_output_relevant_factor():
    from hcs_discovery.workflow.cache import cache_key

    base = {
        "node_type": "dock.vina",
        "node_version": "1.2.5",
        "config": {"seed": 1},
        "input_hash": "a" * 64,
        "engine_versions": {"rdkit": "1", "autodock_vina": "1.2.5", "receptor_sha256": "r1"},
        "schema_version": 1,
        "implementation_hash": "impl",
        "package_fingerprint": "pkg",
    }
    reference = cache_key(**base)
    assert cache_key(**base) == reference
    variants = {
        "node_version": "1.2.6",
        "config": {"seed": 2},
        "input_hash": "b" * 64,
        "engine_versions": {**base["engine_versions"], "autodock_vina": "1.2.6"},
        "schema_version": 2,
        "implementation_hash": "impl2",
        "package_fingerprint": "pkg2",
    }
    for field, value in variants.items():
        assert cache_key(**{**base, field: value}) != reference, field
    receptor_changed = {**base["engine_versions"], "receptor_sha256": "r2"}
    assert cache_key(**{**base, "engine_versions": receptor_changed}) != reference


def test_package_fingerprint_covers_helper_modules(monkeypatch, tmp_path):
    from hcs_discovery.workflow import registry

    package = tmp_path / "hcs_discovery"
    (package / "workflow").mkdir(parents=True)
    (package / "web").mkdir()
    (package / "workflow" / "registry.py").write_text("# stub\n", encoding="utf-8")
    helper = package / "helper.py"
    helper.write_text("COEFFICIENT = 1.0\n", encoding="utf-8")
    (package / "web" / "index.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(registry, "__file__", str(package / "workflow" / "registry.py"))

    def fingerprint() -> str:
        registry.package_fingerprint.cache_clear()
        return registry.package_fingerprint()

    try:
        first = fingerprint()
        (package / "web" / "index.html").write_text("<html>changed</html>", encoding="utf-8")
        assert fingerprint() == first, "bundled SPA must not affect scientific cache keys"
        helper.write_text("COEFFICIENT = 1.1\n", encoding="utf-8")
        changed = fingerprint()
        assert changed != first
        helper.write_bytes(b"COEFFICIENT = 1.1\r\n")
        assert fingerprint() == changed, "CRLF and LF checkouts must share cache keys"
    finally:
        registry.package_fingerprint.cache_clear()
