"""PostgreSQL integration: migrations, a full run, queue exclusivity and readiness.

Skipped unless ``HCS_TEST_POSTGRES_URL`` points at a disposable database. The CI job
starts a ``postgres:16`` service container and sets that variable; locally:

    docker run -d --name hcs-pg -e POSTGRES_PASSWORD=hcs_test_pw \
      -e POSTGRES_USER=hcs -e POSTGRES_DB=hcs -p 55432:5432 postgres:16-alpine
    HCS_TEST_POSTGRES_URL=postgresql+pg8000://hcs:hcs_test_pw@127.0.0.1:55432/hcs \
      uv run pytest -q tests/integration/test_postgres.py

The tests drop the schema before and after each case; the database must be disposable.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from hcs_discovery.api.app import create_app
from hcs_discovery.core.config import Settings
from hcs_discovery.database.base import dispose_engines, get_session_factory, init_db
from hcs_discovery.database.models import Base
from hcs_discovery.jobs.queue import claim_next_run
from hcs_discovery.services import create_project, create_run, import_dataset
from hcs_discovery.workflow.executor import RunExecutor
from tests.conftest import DEMO_CSV

PG_URL = os.environ.get("HCS_TEST_POSTGRES_URL", "").strip()
pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not PG_URL, reason="HCS_TEST_POSTGRES_URL is not set"),
]


@pytest.fixture()
def pg_settings(tmp_path: Path):
    settings = Settings(data_dir=tmp_path / "data", network_policy="local", database_url_override=PG_URL)
    settings.ensure_dirs()
    dispose_engines()
    _drop_schema(settings)
    init_db(settings)
    yield settings
    _drop_schema(settings)
    dispose_engines()


def _drop_schema(settings: Settings) -> None:
    engine = create_engine(settings.database_url)
    try:
        Base.metadata.drop_all(engine)
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
    finally:
        engine.dispose()


def _import_demo(settings: Settings, session, project_id: str):
    return import_dataset(
        session=session,
        settings=settings,
        project_id=project_id,
        filename="demo_library.csv",
        data=DEMO_CSV.read_bytes(),
        fmt="auto",
    )


def test_migrations_and_a_full_run_persist_on_postgres(pg_settings: Settings, triage_definition: dict) -> None:
    factory = get_session_factory(pg_settings)
    with factory() as session:
        project = create_project(session, name="Postgres project")
        dataset = _import_demo(pg_settings, session, project.id)
        run = create_run(session, project_id=project.id, workflow=triage_definition, dataset_id=dataset.id)
        run_id = run.id

    executor = RunExecutor(
        run_id=run_id,
        session_factory=factory,
        settings=pg_settings,
        worker_id="postgres-test",
    )
    assert executor.execute() == "succeeded"

    with factory() as session:
        detail = session.execute(text("SELECT status FROM runs WHERE id = :id"), {"id": run_id}).scalar_one()
        rows = session.execute(text("SELECT COUNT(*) FROM run_results WHERE run_id = :id"), {"id": run_id}).scalar_one()
        artifacts = session.execute(
            text("SELECT COUNT(*) FROM artifacts WHERE run_id = :id"), {"id": run_id}
        ).scalar_one()
    assert detail == "succeeded"
    assert rows == 16
    assert artifacts >= 4


def test_two_workers_cannot_claim_the_same_run(pg_settings: Settings, triage_definition: dict) -> None:
    factory = get_session_factory(pg_settings)
    with factory() as session:
        project = create_project(session, name="Claim project")
        dataset = _import_demo(pg_settings, session, project.id)
        run = create_run(session, project_id=project.id, workflow=triage_definition, dataset_id=dataset.id)
        run_id = run.id

    claimed: list[str] = []
    lock = threading.Lock()

    def claim(worker: str) -> None:
        result = claim_next_run(factory, worker_id=worker, lease_seconds=60)
        if result is not None:
            with lock:
                claimed.append(result.id)

    threads = [threading.Thread(target=claim, args=(f"worker-{index}",)) for index in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert claimed == [run_id], f"exactly one worker may claim the run, got {claimed}"


def test_api_readiness_reports_the_external_database(pg_settings: Settings) -> None:
    app = create_app(pg_settings)
    with TestClient(app) as client:
        ready = client.get("/api/v1/ready")
        assert ready.status_code == 200
        body = ready.json()
        assert body["status"] == "ready"
        assert body["database"] == "ok"
        assert client.get("/api/v1/health").json()["status"] == "ok"


def test_stale_lease_is_recovered_on_postgres(pg_settings: Settings, triage_definition: dict) -> None:
    from datetime import timedelta

    from hcs_discovery.jobs.queue import recover_stale_runs

    factory = get_session_factory(pg_settings)
    with factory() as session:
        project = create_project(session, name="Lease project")
        dataset = _import_demo(pg_settings, session, project.id)
        run = create_run(session, project_id=project.id, workflow=triage_definition, dataset_id=dataset.id)
        run.status = "running"
        run.attempt = 1
        run.lease_owner = "crashed-worker"
        run.lease_expires_at = __import__("hcs_discovery.core.timeutil", fromlist=["db_now"]).db_now() - timedelta(
            seconds=5
        )
        session.commit()
        run_id = run.id

    recovered = recover_stale_runs(factory, pg_settings)
    assert recovered == [{"run_id": run_id, "outcome": "requeued"}]
    with factory() as session:
        status = session.execute(text("SELECT status FROM runs WHERE id = :id"), {"id": run_id}).scalar_one()
    assert status == "queued"
