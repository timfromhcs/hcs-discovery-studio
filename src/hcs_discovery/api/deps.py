"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from ..core.config import Settings, get_settings


def settings_dep() -> Settings:
    return get_settings()


def get_session_factory(request: Request) -> sessionmaker[Session]:
    return request.app.state.session_factory


def db(request: Request) -> Iterator[Session]:
    factory: sessionmaker[Session] = request.app.state.session_factory
    session = factory()
    try:
        yield session
    finally:
        session.close()


SessionDep = Depends(db)
SettingsDep = Depends(settings_dep)
