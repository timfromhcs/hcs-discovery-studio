"""Hosted-instance configuration: an external database URL instead of SQLite.

These tests keep the local default intact and prove that the override is a plain
SQLAlchemy URL, never a secret that leaks through ``public_dict``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import event

from hcs_discovery.core.config import Settings
from hcs_discovery.database.base import (
    _apply_sqlite_pragmas,
    _wants_sqlite_pragmas,
    create_db_engine,
    dispose_engines,
    get_engine,
)

POSTGRES_URL = "postgresql+pg8000://hcs:sup3rsecret@db.example.com:5432/hcs"


@pytest.fixture(autouse=True)
def _clean_engines():
    dispose_engines()
    yield
    dispose_engines()


def test_default_database_url_stays_sqlite(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)

    assert settings.database_url == f"sqlite+pysqlite:///{settings.db_path.as_posix()}"
    assert settings.uses_sqlite is True


def test_database_url_override_is_used_verbatim(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, database_url_override=POSTGRES_URL)

    assert settings.database_url == POSTGRES_URL
    assert settings.uses_sqlite is False


def test_public_dict_reports_the_backend_without_the_url(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, database_url_override=POSTGRES_URL)

    public = settings.public_dict()

    assert public["database_backend"] == "external"
    rendered = repr(public)
    assert "sup3rsecret" not in rendered
    assert "db.example.com" not in rendered


def test_pragma_decision_is_sqlite_only() -> None:
    assert _wants_sqlite_pragmas("sqlite+pysqlite:///data/hcs.sqlite3") is True
    assert _wants_sqlite_pragmas(POSTGRES_URL) is False


def test_sqlite_engine_installs_pragmas_and_postgres_does_not(tmp_path: Path) -> None:
    sqlite_settings = Settings(data_dir=tmp_path)
    sqlite_engine = create_db_engine(settings=sqlite_settings)
    assert event.contains(sqlite_engine, "connect", _apply_sqlite_pragmas) is True

    pytest.importorskip("pg8000", reason="the postgres extra is optional")
    postgres_engine = create_db_engine(POSTGRES_URL, settings=sqlite_settings)
    assert event.contains(postgres_engine, "connect", _apply_sqlite_pragmas) is False
    postgres_engine.dispose()


def test_engine_cache_is_keyed_by_url_not_by_data_dir(tmp_path: Path) -> None:
    sqlite_settings = Settings(data_dir=tmp_path)
    postgres_settings = Settings(data_dir=tmp_path, database_url_override=POSTGRES_URL)

    sqlite_engine = get_engine(sqlite_settings)

    assert sqlite_engine is get_engine(sqlite_settings)
    assert get_engine(postgres_settings) is not sqlite_engine
