"""Alembic migration helpers used by the CLI, API startup and tests."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from ..core.config import Settings
from .base import get_engine
from .models import Base

PROJECT_ROOT = Path(__file__).resolve().parents[3]
# Wheels ship the migration scripts inside the package (see pyproject force-include).
PACKAGED_SCRIPTS = Path(__file__).resolve().parents[1] / "_alembic"


def alembic_config(settings: Settings) -> Config | None:
    """Return an Alembic config for a source checkout or an installed wheel.

    Returns ``None`` only when no migration scripts can be found at all.
    """
    ini = PROJECT_ROOT / "alembic.ini"
    if ini.exists():
        config = Config(str(ini))
        config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    elif (PACKAGED_SCRIPTS / "env.py").exists():
        config = Config()
        config.set_main_option("script_location", str(PACKAGED_SCRIPTS))
    else:
        return None
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def upgrade_database(settings: Settings) -> str:
    """Bring the database to the latest revision.

    Databases created before Alembic was introduced are stamped at head because
    their schema already matches revision ``0001``. Returns ``"alembic"`` or
    ``"create_all"`` so callers can report which path was used.
    """
    config = alembic_config(settings)
    if config is None:  # pragma: no cover - package installed without migration assets
        Base.metadata.create_all(get_engine(settings))
        return "create_all"

    engine = get_engine(settings)
    tables = set(inspect(engine).get_table_names())
    if tables and "alembic_version" not in tables:
        command.stamp(config, "head")
    command.upgrade(config, "head")
    return "alembic"


def current_revision(settings: Settings) -> str | None:
    engine = get_engine(settings)
    with engine.connect() as connection:
        if "alembic_version" not in set(inspect(connection).get_table_names()):
            return None
        return connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
