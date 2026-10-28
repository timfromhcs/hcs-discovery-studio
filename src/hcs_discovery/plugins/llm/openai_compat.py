"""OpenAI-compatible local LLM provider.

Local-first by design: the default endpoint is a loopback OpenAI-compatible server
(llama.cpp, LM Studio, ...). Non-loopback endpoints require an explicit remote
network policy and are never contacted silently.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from ...core.config import Settings
from ...core.errors import MissingDependencyError, PolicyError, ValidationError
from ...core.redaction import redact_text

PROVIDER_ID = "llm:openai-compatible"


@dataclass
class ProviderHealth:
    status: str
    detail: str
    models: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "detail": self.detail, "models": self.models}


def _is_loopback(url: str) -> bool:
    host = urlparse(url).hostname or ""
    if host in {"localhost", "::1"}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class OpenAICompatibleProvider:
    """Minimal, deliberately small client used for research assistance only."""

    id = PROVIDER_ID

    def __init__(self, settings: Settings, *, transport: Any | None = None) -> None:
        self.settings = settings
        self.base_url = (settings.llm_base_url or "").rstrip("/")
        self.model = settings.llm_model or ""
        self.api_key = settings.llm_api_key
        self._transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    def metadata(self) -> dict[str, Any]:
        loopback = _is_loopback(self.base_url) if self.base_url else True
        return {
            "id": self.id,
            "display_name": "Local OpenAI-compatible provider",
            "kind": "local" if loopback else "remote",
            "base_url": self.base_url or None,
            "model": self.model or None,
            "api_key": "configured" if self.api_key else "missing",
            "network_required": not loopback,
            "capabilities": ["chat"],
            "status": "configured" if self.configured else "not_configured",
            "license": {"code": "n/a", "weights": "provider-specific", "data": "provider-specific"},
        }

    def _client(self) -> Any:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - dependency is installed in normal builds
            raise MissingDependencyError("httpx is required for LLM providers.") from exc
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return httpx.Client(base_url=self.base_url, timeout=20.0, headers=headers, transport=self._transport)

    def _assert_allowed(self) -> None:
        if not self.configured:
            raise ValidationError("No LLM base URL is configured (HCS_LLM_BASE_URL).")
        if not _is_loopback(self.base_url) and self.settings.network_policy == "local":
            raise PolicyError(
                "Local-only mode blocks non-loopback LLM endpoints.",
                details={"host": urlparse(self.base_url).hostname},
            )
        if not _is_loopback(self.base_url) and not self.settings.remote_llm_enabled:
            raise PolicyError(
                "Remote LLM use requires HCS_REMOTE_LLM_ENABLED=true and an explicit data-sharing decision."
            )

    def probe(self) -> ProviderHealth:
        if not self.configured:
            return ProviderHealth("not_configured", "No base URL configured.", [])
        try:
            self._assert_allowed()
        except PolicyError as exc:
            return ProviderHealth("blocked_by_policy", exc.message, [])
        try:
            with self._client() as client:
                response = client.get("/models")
                response.raise_for_status()
                payload = response.json()
            models = [item.get("id", "") for item in payload.get("data", []) if isinstance(item, dict)]
            return ProviderHealth("available", f"{len(models)} model(s) reported.", models)
        except Exception as exc:
            return ProviderHealth("unreachable", redact_text(f"{type(exc).__name__}: {exc}"), [])

    def chat(self, messages: list[dict[str, str]], *, max_tokens: int = 512) -> str:
        self._assert_allowed()
        payload: dict[str, Any] = {
            "model": self.model or "local-model",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        with self._client() as client:
            response = client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
        try:
            return str(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ValidationError("Provider returned an unexpected response shape.") from exc


def build_provider(settings: Settings) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(settings)
