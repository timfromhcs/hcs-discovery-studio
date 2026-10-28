"""Secret redaction for logs, API errors, reports and CLI output.

This module is deliberately conservative: it removes common credential shapes and
any explicitly registered secret values. It is a defence-in-depth measure, not a
license to log secrets.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

REDACTED = "[REDACTED]"

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), REDACTED),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), REDACTED),
    (re.compile(r"sk-[A-Za-z0-9_\-]{16,}"), REDACTED),
    (re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._\-]{10,}"), r"\1 " + REDACTED),
    (
        re.compile(
            r"(?i)\b(api[_-]?key|access[_-]?token|token|password|passwd|secret|client[_-]?secret)\b"
            r"['\"]?\s*[:=]\s*['\"]?[^\s'\"&,;]{6,}"
        ),
        r"\1=" + REDACTED,
    ),
    (re.compile(r"(?i)([?&](?:key|token|access_token|api_key)=)[^&\s]+"), r"\1" + REDACTED),
    (
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
        REDACTED,
    ),
)

_SENSITIVE_KEY = re.compile(
    r"(?i)^(api[_-]?key|access[_-]?token|refresh[_-]?token|token|password|passwd|secret|"
    r"client[_-]?secret|authorization|cookie|set-cookie)$"
)

_registered: set[str] = set()


def register_secret(value: str | None) -> None:
    """Register a runtime secret (for example a configured API key) for redaction."""
    if value and len(value) >= 6:
        _registered.add(value)


def redact_text(value: str) -> str:
    """Return ``value`` with credential shapes and registered secrets removed."""
    result = value
    for secret in _registered:
        result = result.replace(secret, REDACTED)
    for pattern, replacement in _PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def redact_value(value: Any) -> Any:
    """Recursively redact strings inside JSON-compatible containers."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {
            redact_text(str(key)): (REDACTED if _SENSITIVE_KEY.match(str(key)) else redact_value(item))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_value(item) for item in value]
    return value


def redact_headers(headers: Iterable[tuple[str, str]]) -> dict[str, str]:
    sensitive = {"authorization", "proxy-authorization", "x-api-key", "cookie", "set-cookie"}
    return {key: (REDACTED if key.lower() in sensitive else redact_text(value)) for key, value in headers}
