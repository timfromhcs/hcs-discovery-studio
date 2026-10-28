"""Application-wide configuration.

Configuration is read from environment variables prefixed with ``HCS_`` and an
optional ``.env`` file in the working directory. Every value has a safe default so
that a fresh checkout runs on loopback without any secrets.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

NetworkPolicy = Literal["local", "remote"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HCS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = Path("./data")
    network_policy: NetworkPolicy = "local"
    host: str = "127.0.0.1"
    port: int = Field(default=8787, ge=1, le=65535)
    cpu_threads: int | None = Field(default=None, ge=1, le=256)
    max_import_rows: int = Field(default=50_000, ge=1)
    max_upload_mb: int = Field(default=64, ge=1)
    worker_poll_seconds: float = Field(default=0.5, ge=0.05)
    run_lease_seconds: int = Field(default=90, ge=10)
    max_run_attempts: int = Field(default=2, ge=1, le=5)

    # Local OpenAI-compatible provider. Secrets come from the environment only and
    # are never persisted by the application.
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None

    # Remote provider opt-in. Requires network_policy="remote" as well.
    remote_llm_enabled: bool = False
    remote_llm_api_key: str | None = None

    # Required when binding to a non-loopback interface.
    api_token: str | None = None

    @field_validator("data_dir", mode="before")
    @classmethod
    def _expand(cls, value: str | Path) -> Path:
        return Path(os.path.expanduser(str(value))).resolve()

    @property
    def db_path(self) -> Path:
        return self.data_dir / "hcs.sqlite3"

    @property
    def runs_dir(self) -> Path:
        return self.data_dir / "runs"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def database_url(self) -> str:
        return f"sqlite+pysqlite:///{self.db_path.as_posix()}"

    @property
    def is_loopback(self) -> bool:
        return self.host in {"127.0.0.1", "::1", "localhost"}

    def ensure_dirs(self) -> None:
        for path in (
            self.data_dir,
            self.runs_dir,
            self.cache_dir,
            self.logs_dir,
            self.uploads_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def public_dict(self) -> dict[str, object]:
        """Configuration safe to show in the UI/CLI. Never includes secrets."""
        return {
            "data_dir": str(self.data_dir),
            "network_policy": self.network_policy,
            "host": self.host,
            "port": self.port,
            "cpu_threads": self.cpu_threads,
            "max_import_rows": self.max_import_rows,
            "max_upload_mb": self.max_upload_mb,
            "llm_base_url": self.llm_base_url,
            "llm_model": self.llm_model,
            "llm_api_key": "configured" if self.llm_api_key else "missing",
            "remote_llm_enabled": self.remote_llm_enabled,
            "remote_llm_api_key": "configured" if self.remote_llm_api_key else "missing",
            "api_token": "configured" if self.api_token else "missing",
        }


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.ensure_dirs()
    return _settings


def reset_settings(cache: Settings | None = None) -> None:
    """Used by tests to swap the active configuration."""
    global _settings
    _settings = cache
