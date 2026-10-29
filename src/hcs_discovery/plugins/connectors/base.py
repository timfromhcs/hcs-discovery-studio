"""Base class, data contracts, and client infrastructure for external data connectors."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from rdkit import Chem

from ...core.config import Settings, get_settings
from ...core.errors import ValidationError
from ...core.hashing import sha256_text
from .policy import check_network_allowed

MAX_PAYLOAD_BYTES = 10 * 1024 * 1024  # 10 MB payload ceiling
MAX_RETRY_AFTER_SECONDS = 10.0
RETRYABLE_STATUS = frozenset({429, 502, 503, 504})


def _too_large(size: int) -> str:
    return f"Connector response payload ({size} bytes) exceeds ceiling ({MAX_PAYLOAD_BYTES} bytes)."


def structure_check(smiles: str | None, reported_inchikey: str | None) -> str:
    """Check that a provider's structure and its reported InChIKey describe the same molecule.

    Returns ``consistent``, ``inchikey_mismatch``, ``unparseable_smiles``,
    ``missing_smiles`` or ``no_inchikey_reported``. A mismatch is reported, not
    corrected: the provider record is kept as delivered.
    """
    if not smiles:
        return "missing_smiles"
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return "unparseable_smiles"
    if not reported_inchikey:
        return "no_inchikey_reported"
    return "consistent" if Chem.MolToInchiKey(mol) == reported_inchikey.strip() else "inchikey_mismatch"


def _retry_delay(response: httpx.Response | None, attempt: int) -> float:
    """Honour a numeric Retry-After header, capped; otherwise back off linearly."""
    header = response.headers.get("retry-after") if response is not None else None
    if header is not None:
        try:
            return min(max(float(header), 0.0), MAX_RETRY_AFTER_SECONDS)
        except ValueError:
            pass
    return 1.0 * attempt


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

    def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        allow_not_found: bool = False,
    ) -> dict[str, Any] | None:
        """Perform a policy-checked HTTP GET request and parse a JSON object.

        Redirects are never followed automatically: a 3xx response is reported as an
        explicit failure so an allowlisted host cannot silently bounce the request to
        an unvetted destination. A 404 is only treated as "no result" when the caller
        opts in with ``allow_not_found``; otherwise it is a visible error.
        """
        # The policy applies to every request; a mock transport only replaces the wire.
        parsed = httpx.URL(url)
        if parsed.scheme != "https":
            raise ValidationError(f"Connector URLs must use HTTPS, got '{parsed.scheme}'.")
        check_network_allowed(parsed.host, settings=self.settings)

        client_kwargs: dict[str, Any] = {
            "timeout": self.timeout,
            "follow_redirects": False,
            "headers": {
                "User-Agent": "HCS-Discovery-Studio/2.0 (+https://github.com/timfromhcs/hcs-discovery-studio)",
                "Accept": "application/json",
            },
        }
        if self.mock_transport is not None:
            client_kwargs["transport"] = self.mock_transport

        attempts = 3
        last_exc: Exception | None = None

        with httpx.Client(**client_kwargs) as client:
            for attempt in range(1, attempts + 1):
                self._wait_rate_limit()
                try:
                    with client.stream("GET", url, params=params) as response:
                        status = response.status_code
                        if status == 404:
                            if allow_not_found:
                                return None
                            raise ValidationError(
                                f"Connector resource was not found (HTTP 404) at {parsed.host}.",
                                details={"status": 404, "host": parsed.host},
                            )
                        if 300 <= status < 400:
                            location = response.headers.get("location", "")
                            raise ValidationError(
                                f"Connector redirect blocked (HTTP {status}) from {parsed.host} "
                                f"to '{location[:200]}'. Redirects are not followed by policy.",
                                details={"status": status, "location": location[:500]},
                            )
                        if status in RETRYABLE_STATUS and attempt < attempts:
                            last_exc = ValidationError(f"HTTP {status} from {parsed.host}")
                            time.sleep(_retry_delay(response, attempt))
                            continue
                        if status >= 400:
                            body = response.read()[:200].decode("utf-8", errors="replace")
                            raise ValidationError(
                                f"Connector request failed with status {status}: {body}",
                                details={"status": status, "host": parsed.host},
                            )
                        content_type = response.headers.get("content-type", "")
                        if "json" not in content_type.lower():
                            raise ValidationError(
                                f"Connector expected JSON from {parsed.host}, received '{content_type[:100]}'.",
                                details={"host": parsed.host, "content_type": content_type[:200]},
                            )
                        declared = response.headers.get("content-length")
                        if declared is not None and declared.isdigit() and int(declared) > MAX_PAYLOAD_BYTES:
                            raise ValidationError(_too_large(int(declared)))
                        body_bytes = bytearray()
                        for chunk in response.iter_bytes():
                            body_bytes.extend(chunk)
                            if len(body_bytes) > MAX_PAYLOAD_BYTES:
                                raise ValidationError(_too_large(len(body_bytes)))
                    try:
                        payload = json.loads(bytes(body_bytes))
                    except ValueError as exc:
                        raise ValidationError(
                            f"Connector returned malformed JSON from {parsed.host}: {exc}",
                            details={"host": parsed.host, "content_type": content_type[:200]},
                        ) from exc
                    if not isinstance(payload, dict):
                        raise ValidationError(
                            f"Connector expected a JSON object from {parsed.host}, received {type(payload).__name__}.",
                            details={"host": parsed.host},
                        )
                    return payload
                except httpx.RequestError as exc:
                    last_exc = exc
                    if attempt < attempts:
                        time.sleep(_retry_delay(None, attempt))
                        continue
                    raise ValidationError(f"Network error connecting to {parsed.host}: {exc}") from exc

        raise ValidationError(f"Connector failed after {attempts} attempts: {last_exc}")

    @staticmethod
    def now_iso() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def hash_payload(data: dict[str, Any]) -> str:
        return sha256_text(json.dumps(data, sort_keys=True))
