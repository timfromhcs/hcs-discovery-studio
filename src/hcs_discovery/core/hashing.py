"""Identifier and hashing helpers."""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from pathlib import Path
from typing import Any

_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"


def new_id(prefix: str) -> str:
    """Return a short, sortable-ish, collision-resistant identifier.

    Format: ``<prefix>_<20 chars base32>``. Uses uuid4 entropy, so it is safe for
    concurrent workers without a database round trip.
    """
    raw = uuid.uuid4().int
    out = []
    for _ in range(20):
        out.append(_ALPHABET[raw & 31])
        raw >>= 5
    return f"{prefix}_{''.join(out)}"


def token(nbytes: int = 24) -> str:
    return secrets.token_urlsafe(nbytes)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def stable_json_hash(payload: Any) -> str:
    """Deterministic hash of a JSON-compatible payload (sorted keys, no whitespace)."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256_text(encoded)
