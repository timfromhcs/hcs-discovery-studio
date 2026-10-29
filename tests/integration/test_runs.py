"""End-to-end run execution, caching, cancellation and recovery."""

from __future__ import annotations

import threading
import time

from pydantic import BaseModel
from sqlalchemy import select

from hcs_discovery.database.models import Artifact, Run, RunEvent, RunNode, RunResult
from hcs_discovery.jobs.queue import claim_next_run, recover_stale_runs, request_cancel
from hcs_discovery.jobs.worker import Worker
from hcs_discovery.services import create_run, results_page
from hcs_discovery.workflow.executor import RunExecutor
from hcs_discovery.workflow.nodes import register_builtin_nodes
from hcs_discovery.workflow.registry import NodeDefinition, NodeRegistry


def _execute(settings, run_id, registry=None):
    executor = RunExecutor(
        run_id=run_id,
        session_factory=__import__("hcs_discovery.database.base", fromlist=["get_session_factory"]).get_session_factory(
            settings
        ),
        settings=settings,
        registry=registry,
        worker_id="test-worker",
    )
    return executor.execute()


def test_full_run_persists_results_artifacts_and_manifest(settings, session, project, dataset, triage_definition):
    run = create_run(
        session,
        project_id=project.id,
        workflow=triage_definition,
        dataset_id=dataset.id,
    )
    assert run.status == "queued"
    assert _execute(settings, run.id) == "succeeded"

    session.expire_all()
    stored = session.get(Run, run.id)
    assert stored.status == "succeeded"
    assert stored.manifest["environment"]["rdkit"]
    assert stored.manifest["artifact_rel_path"] == "manifest.json"

    results = session.execute(select(RunResult).where(RunResult.run_id == run.id)).scalars().all()
    assert len(results) == 16
    top = min(results, key=lambda item: item.rank or 10_000)
    assert top.rank == 1
    assert top.metrics["mw"] is not None
    assert any(result.rejected for result in results)

    artifacts = session.execute(select(Artifact).where(Artifact.run_id == run.id)).scalars().all()
    names = {artifact.rel_path for artifact in artifacts}
    assert "results.csv" in names
    assert "results.json" in names
    assert "manifest.json" in names
    assert any(name.endswith("summary.md") for name in names)

    events = session.execute(select(RunEvent).where(RunEvent.run_id == run.id).order_by(RunEvent.seq)).scalars().all()
    assert events[0].type == "run.started"
    assert events[-1].type == "run.succeeded"
    assert [event.seq for event in events] == list(range(1, len(events) + 1))

    page = results_page(session, run.id, sort="composite_score", order="desc", limit=5)
    assert page["total"] == 16
    assert len(page["items"]) == 5
    assert page["items"][0]["composite_score"] >= page["items"][1]["composite_score"]
    assert page["columns"]


def test_results_pagination_sorts_missing_values_last(settings, session, project, dataset, triage_definition):
    run = create_run(session, project_id=project.id, workflow=triage_definition, dataset_id=dataset.id)
    assert _execute(settings, run.id) == "succeeded"
    session.expire_all()
    stored = session.execute(select(RunResult).where(RunResult.run_id == run.id).order_by(RunResult.id)).scalars().all()
    stored[0].composite_score = None
    stored[1].rank = None
    session.commit()

    for order in ("asc", "desc"):
        page = results_page(session, run.id, sort="composite_score", order=order, limit=16)
        scores = [item["composite_score"] for item in page["items"]]
        assert scores[-1] is None
        non_null = [score for score in scores if score is not None]
        assert non_null == sorted(non_null, reverse=(order == "desc"))

        ranks = [item["rank"] for item in results_page(session, run.id, sort="rank", order=order, limit=16)["items"]]
        assert ranks[-1] is None
        non_null_ranks = [rank for rank in ranks if rank is not None]
        assert non_null_ranks == sorted(non_null_ranks, reverse=(order == "desc"))

    full = [item["compound_id"] for item in results_page(session, run.id, limit=16, sort="rank")["items"]]
    paged: list[str] = []
    for offset in range(0, len(full), 5):
        page = results_page(session, run.id, sort="rank", limit=5, offset=offset)
        paged.extend(item["compound_id"] for item in page["items"])
    assert paged == full
    assert len(set(paged)) == len(paged)

    metrics = [
        item["metrics"]["mw"]
        for item in results_page(session, run.id, sort="mw", order="desc", limit=16)["items"]
        if item["metrics"].get("mw") is not None
    ]
    assert metrics == sorted(metrics, reverse=True)


def test_results_query_and_passing_filters_apply_before_pagination(
    settings, session, project, dataset, triage_definition
):
    run = create_run(session, project_id=project.id, workflow=triage_definition, dataset_id=dataset.id)
    assert _execute(settings, run.id) == "succeeded"
    session.expire_all()

    everything = results_page(session, run.id, limit=2000)
    passing = results_page(session, run.id, only_passing=True, limit=2000)
    assert passing["total"] <= everything["total"]
    assert all(not item["rejected"] for item in passing["items"])

    needle = everything["items"][0]["compound_id"]
    matched = results_page(session, run.id, q=needle, limit=5)
    assert matched["total"] == 1
    assert matched["items"][0]["compound_id"] == needle


def test_results_columns_fall_back_to_artifact_for_legacy_runs(settings, session, project, dataset, triage_definition):
    run = create_run(session, project_id=project.id, workflow=triage_definition, dataset_id=dataset.id)
    assert _execute(settings, run.id) == "succeeded"

    session.expire_all()
    stored = session.get(Run, run.id)
    legacy_manifest = {key: value for key, value in stored.manifest.items() if key != "columns"}
    stored.manifest = legacy_manifest
    session.commit()

    page = results_page(session, run.id, limit=5)
    names = {column["name"] for column in page["columns"]}
    assert {"compound_id", "composite_score", "rank"} <= names


def test_second_run_reuses_cache(settings, session, project, dataset, triage_definition):
    first = create_run(session, project_id=project.id, workflow=triage_definition, dataset_id=dataset.id)
    assert _execute(settings, first.id) == "succeeded"
    second = create_run(session, project_id=project.id, workflow=triage_definition, dataset_id=dataset.id)
    assert _execute(settings, second.id) == "succeeded"
    session.expire_all()
    nodes = session.execute(select(RunNode).where(RunNode.run_id == second.id)).scalars().all()
    assert all(node.cached for node in nodes)
    first_results = session.execute(select(RunResult).where(RunResult.run_id == first.id)).scalars().all()
    second_results = session.execute(select(RunResult).where(RunResult.run_id == second.id)).scalars().all()
    assert sorted((r.compound_id, r.composite_score) for r in first_results) == sorted(
        (r.compound_id, r.composite_score) for r in second_results
    )


def test_changed_configuration_invalidates_cache(settings, session, project, dataset, triage_definition):
    first = create_run(session, project_id=project.id, workflow=triage_definition, dataset_id=dataset.id)
    assert _execute(settings, first.id) == "succeeded"
    changed = {**triage_definition}
    changed["nodes"] = [dict(node) for node in triage_definition["nodes"]]
    changed["nodes"][2] = {
        "id": "ranking",
        "type": "rank.pareto",
        "config": {"objectives": [{"column": "mw", "direction": "higher", "weight": 1.0}]},
    }
    second = create_run(session, project_id=project.id, workflow=changed, dataset_id=dataset.id)
    assert _execute(settings, second.id) == "succeeded"
    session.expire_all()
    ranking = session.execute(
        select(RunNode).where(RunNode.run_id == second.id, RunNode.node_id == "ranking")
    ).scalar_one()
    assert ranking.cached is False


class SlowConfig(BaseModel):
    iterations: int = 40


def _slow_handler(table, config, ctx):  # type: ignore[no-untyped-def]
    for index in range(config.iterations):
        time.sleep(0.03)
        ctx.check_cancel()
        ctx.report_progress(index / config.iterations)
    return table


def _slow_registry() -> NodeRegistry:
    registry = NodeRegistry()
    register_builtin_nodes(registry)
    registry.register(
        NodeDefinition(
            type="test.slow",
            title="Slow node",
            category="testing",
            version="1.0.0",
            description="Test-only slow node used for cancellation tests.",
            config_model=SlowConfig,
            handler=_slow_handler,
        )
    )
    return registry


def test_cancellation_stops_a_running_node(settings, session, project, dataset):
    registry = _slow_registry()
    workflow = {
        "schema_version": 1,
        "id": "slow",
        "name": "Slow test",
        "nodes": [{"id": "slow", "type": "test.slow", "config": {"iterations": 60}}],
        "edges": [],
    }
    run = create_run(session, project_id=project.id, workflow=workflow, dataset_id=dataset.id, registry=registry)
    thread = threading.Thread(target=_execute, args=(settings, run.id, registry))
    thread.start()
    time.sleep(0.5)
    request_cancel(session, run.id)
    thread.join(timeout=30)
    assert not thread.is_alive()
    session.expire_all()
    assert session.get(Run, run.id).status == "cancelled"


def test_cancel_before_start_is_immediate(settings, session, project, dataset, triage_definition):
    run = create_run(session, project_id=project.id, workflow=triage_definition, dataset_id=dataset.id)
    request_cancel(session, run.id)
    session.expire_all()
    assert session.get(Run, run.id).status == "cancelled"


def test_worker_claims_and_executes(settings, session, project, dataset, triage_definition):
    run = create_run(session, project_id=project.id, workflow=triage_definition, dataset_id=dataset.id)
    worker = Worker(settings=settings, worker_id="worker-test")
    claimed = worker.run_once()
    assert claimed is not None and claimed.id == run.id
    session.expire_all()
    assert session.get(Run, run.id).status == "succeeded"
    assert worker.run_once() is None


def test_claim_is_exclusive(settings, session, project, dataset, triage_definition):
    from hcs_discovery.database.base import get_session_factory

    run = create_run(session, project_id=project.id, workflow=triage_definition, dataset_id=dataset.id)
    factory = get_session_factory(settings)
    first = claim_next_run(factory, worker_id="a", lease_seconds=60)
    second = claim_next_run(factory, worker_id="b", lease_seconds=60)
    assert first is not None and first.id == run.id
    assert second is None


def test_expired_lease_is_requeued_then_failed(settings, session, project, dataset, triage_definition):
    from datetime import timedelta

    from hcs_discovery.core.timeutil import db_now
    from hcs_discovery.database.base import get_session_factory

    run = create_run(session, project_id=project.id, workflow=triage_definition, dataset_id=dataset.id)
    run.status = "running"
    run.attempt = 1
    run.lease_owner = "dead-worker"
    run.lease_expires_at = db_now() - timedelta(seconds=5)
    session.commit()
    factory = get_session_factory(settings)
    recovered = recover_stale_runs(factory, settings)
    assert recovered == [{"run_id": run.id, "outcome": "requeued"}]
    session.expire_all()
    assert session.get(Run, run.id).status == "queued"

    stored = session.get(Run, run.id)
    stored.status = "running"
    stored.attempt = settings.max_run_attempts
    stored.lease_owner = "dead-worker"
    stored.lease_expires_at = db_now() - timedelta(seconds=5)
    session.commit()
    recovered = recover_stale_runs(factory, settings)
    assert recovered == [{"run_id": run.id, "outcome": "failed"}]
    session.expire_all()
    failed = session.get(Run, run.id)
    assert failed.status == "failed"
    assert failed.error["code"] == "lease_expired"


def test_node_failure_fails_run_visibly(settings, session, project, dataset):
    class BrokenConfig(BaseModel):
        message: str = "intentional failure"

    def _broken(table, config, ctx):  # type: ignore[no-untyped-def]
        raise ValueError(config.message)

    registry = NodeRegistry()
    registry.register(
        NodeDefinition(
            type="test.broken",
            title="Broken",
            category="testing",
            version="1.0.0",
            description="Test-only failing node.",
            config_model=BrokenConfig,
            handler=_broken,
        )
    )
    workflow = {
        "schema_version": 1,
        "id": "broken",
        "name": "Broken run",
        "nodes": [{"id": "broken", "type": "test.broken", "config": {}}],
        "edges": [],
    }
    run = create_run(session, project_id=project.id, workflow=workflow, dataset_id=dataset.id, registry=registry)
    assert _execute(settings, run.id, registry) == "failed"
    session.expire_all()
    stored = session.get(Run, run.id)
    assert stored.status == "failed"
    assert stored.error["code"] == "internal_error"
    node = session.execute(select(RunNode).where(RunNode.run_id == run.id)).scalar_one()
    assert node.status == "failed"


def test_executor_detects_missing_dataset(settings, session, project, dataset, triage_definition):
    run = create_run(session, project_id=project.id, workflow=triage_definition, dataset_id=dataset.id)
    run.dataset_id = None
    session.commit()
    assert _execute(settings, run.id) == "failed"
