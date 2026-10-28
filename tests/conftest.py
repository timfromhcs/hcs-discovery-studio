from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hcs_discovery.api.app import create_app
from hcs_discovery.core.config import Settings, reset_settings
from hcs_discovery.database.base import dispose_engines, get_session_factory, init_db

ROOT = Path(__file__).resolve().parents[1]
DEMO_CSV = ROOT / "examples" / "datasets" / "demo_library.csv"
TRIAGE_YAML = ROOT / "examples" / "workflows" / "triage.yaml"


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    data_dir = tmp_path / "data"
    current = Settings(data_dir=data_dir, network_policy="local", max_import_rows=5000)
    current.ensure_dirs()
    reset_settings(current)
    dispose_engines()
    init_db(current)
    yield current
    dispose_engines()
    reset_settings(None)


@pytest.fixture()
def session(settings: Settings):
    factory = get_session_factory(settings)
    with factory() as db_session:
        yield db_session


@pytest.fixture()
def client(settings: Settings):
    app = create_app(settings)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture()
def demo_bytes() -> bytes:
    return DEMO_CSV.read_bytes()


@pytest.fixture()
def triage_definition() -> dict:
    import yaml

    return yaml.safe_load(TRIAGE_YAML.read_text(encoding="utf-8"))


@pytest.fixture()
def project(session):
    from hcs_discovery.services import create_project

    return create_project(session, name="Test project")


@pytest.fixture()
def dataset(settings, session, project, demo_bytes):
    from hcs_discovery.datasets.readers import ImportOptions
    from hcs_discovery.services import import_dataset

    return import_dataset(
        session=session,
        settings=settings,
        project_id=project.id,
        filename="demo_library.csv",
        data=demo_bytes,
        fmt="auto",
        options=ImportOptions(),
    )


def copy_example(destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DEMO_CSV, destination)
    return destination
