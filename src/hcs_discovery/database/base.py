"""Engine and session management.

SQLite is the local default. We enable WAL, a busy timeout and foreign keys so a
single-process API plus a worker process can share the database safely for the
workload sizes this application supports.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from ..core.config import Settings, get_settings

_engines: dict[str, Engine] = {}
_factories: dict[str, sessionmaker[Session]] = {}
_initialized: set[str] = set()


def _apply_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=15000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def create_db_engine(url: str | None = None, *, settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    settings.ensure_dirs()
    url = url or settings.database_url
    engine = create_engine(url, future=True, pool_pre_ping=True)
    if url.startswith("sqlite"):
        event.listen(engine, "connect", _apply_sqlite_pragmas)
    return engine


def get_engine(settings: Settings | None = None) -> Engine:
    settings = settings or get_settings()
    key = str(settings.db_path)
    if key not in _engines:
        _engines[key] = create_db_engine(settings.database_url, settings=settings)
    return _engines[key]


def ensure_database_initialized(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    key = str(settings.db_path)
    if key in _initialized:
        return
    engine = get_engine(settings)
    from sqlalchemy import inspect

    tables = inspect(engine).get_table_names()
    if not tables:
        init_db(settings)
    _initialized.add(key)


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    settings = settings or get_settings()
    key = str(settings.db_path)
    if key not in _factories:
        ensure_database_initialized(settings)
        _factories[key] = sessionmaker(bind=get_engine(settings), expire_on_commit=False, future=True)
    return _factories[key]


def init_db(settings: Settings | None = None) -> None:
    """Create or migrate the local database to the current schema.

    Fresh installs and upgrades both go through Alembic. A wheel without the
    migration assets falls back to ``create_all`` so the app still starts.
    """
    from .migrations import upgrade_database

    upgrade_database(settings or get_settings())


@contextmanager
def session_scope(settings: Settings | None = None) -> Iterator[Session]:
    factory = get_session_factory(settings)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def dispose_engines() -> None:
    for engine in _engines.values():
        engine.dispose()
    _engines.clear()
    _factories.clear()
    _initialized.clear()


def database_exists(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0
