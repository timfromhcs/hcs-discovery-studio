"""Base class, data contracts, and client infrastructure for external data connectors."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from ...core.config import Settings, get_settings
from ...core.errors import ValidationError
from ...core.hashing import sha256_text
from .policy import check_network_allowed

MAX_PAYLOAD_BYTES = 10 * 1024 * 1024  # 10 MB payload ceiling


@dataclass(frozen=True)
class ConnectorRecord:
    source: str
    external_id: str
    source_url: str
    retrieval_time: str
    license: str
    data: dict[str, Any]
    content_hash: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "external_id": self.external_id,
            "source_url": self.source_url,
            "retrieval_time": self.retrieval_time,
            "license": self.license,
            "data": self.data,
            "content_hash": self.content_hash,
        }


class BaseConnector:
    """Outbound HTTP client with rate-limiting, retries, and strict policy gating."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        mock_transport: httpx.BaseTransport | None = None,
        timeout: float = 15.0,
        rate_limit_delay: float = 0.2,
    ) -> None:
        self.settings = settings or get_settings()
        self.mock_transport = mock_transport
        self.timeout = timeout
        self.rate_limit_delay = rate_limit_delay
        self._last_request_time = 0.0

    def _wait_rate_limit(self) -> None:
        if self.mock_transport is not None:
            return
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time = time.monotonic()

    def get_json(self, url: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Perform a policy-checked HTTP GET request and parse JSON."""
        # 1. Enforce network policy unless mock transport is active
        parsed = httpx.URL(url)
        if self.mock_transport is None:
            check_network_allowed(parsed.host, settings=self.settings)

        self._wait_rate_limit()

        client_kwargs: dict[str, Any] = {
            "timeout": self.timeout,
            "headers": {"User-Agent": "HCS-Discovery-Studio/1.0 (+https://github.com/timfromhcs/hcs-discovery-studio)"},
        }
        if self.mock_transport is not None:
            client_kwargs["transport"] = self.mock_transport

        attempts = 3
        last_exc: Exception | None = None

        with httpx.Client(**client_kwargs) as client:
            for attempt in range(1, attempts + 1):
                try:
                    response = client.get(url, params=params)
                    if response.status_code == 404:
                        return {}
                    if response.status_code in (429, 503) and attempt < attempts:
                        time.sleep(1.0 * attempt)
                        continue
                    response.raise_for_status()

                    # Guard payload size
                    if len(response.content) > MAX_PAYLOAD_BYTES:
                        raise ValidationError(
                            f"Connector response payload ({len(response.content)} bytes) "
                            f"exceeds ceiling ({MAX_PAYLOAD_BYTES} bytes)."
                        )

                    return response.json()
                except httpx.HTTPStatusError as exc:
                    last_exc = exc
                    if exc.response.status_code in (429, 502, 503, 504) and attempt < attempts:
                        time.sleep(1.0 * attempt)
                        continue
                    raise ValidationError(
                        f"Connector request failed with status {exc.response.status_code}: {exc.response.text[:200]}"
                    ) from exc
                except httpx.RequestError as exc:
                    last_exc = exc
                    if attempt < attempts:
                        time.sleep(1.0 * attempt)
                        continue
                    raise ValidationError(f"Network error connecting to {parsed.host}: {exc}") from exc

        raise ValidationError(f"Connector failed after {attempts} attempts: {last_exc}")

    @staticmethod
    def now_iso() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def hash_payload(data: dict[str, Any]) -> str:
        return sha256_text(json.dumps(data, sort_keys=True))
