"""Strict network policy validation for outbound connectors."""

from __future__ import annotations

from ...core.config import Settings, get_settings
from ...core.errors import ValidationError

ALLOWED_CONNECTOR_HOSTS = frozenset(
    [
        "pubchem.ncbi.nlm.nih.gov",
        "www.ebi.ac.uk",
    ]
)


class NetworkPolicyViolationError(ValidationError):
    code = "network_policy_violation"


def _normalize_host(host: str) -> str:
    """Canonicalise a URL host before allowlist comparison.

    Lower-cases, strips a trailing root dot, removes an optional port and converts
    internationalised names to their IDNA (punycode) form. Anything that cannot be
    canonicalised is rejected rather than guessed at.
    """
    cleaned = host.strip().lower().rstrip(".")
    if not cleaned:
        raise NetworkPolicyViolationError("Outbound request has an empty host.")
    if cleaned.startswith("["):
        cleaned = cleaned.split("]", 1)[0].lstrip("[")
    elif ":" in cleaned:
        cleaned = cleaned.split(":", 1)[0]
    if any(ord(char) > 127 for char in cleaned):
        try:
            cleaned = cleaned.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise NetworkPolicyViolationError(f"Host '{host}' cannot be canonicalised.") from exc
    return cleaned


def check_network_allowed(
    host: str,
    *,
    settings: Settings | None = None,
) -> None:
    """Validate that outbound network access is explicitly enabled and destination is allowlisted.

    Defaults to denying external requests under local-only policy.
    """
    cfg = settings or get_settings()

    if cfg.network_policy != "remote":
        raise NetworkPolicyViolationError(
            f"External network connection to '{host}' blocked by policy. "
            f"Current network policy is '{cfg.network_policy}'. "
            "To enable external connectors, set HCS_NETWORK_POLICY=remote."
        )

    clean_host = _normalize_host(host)
    if clean_host not in ALLOWED_CONNECTOR_HOSTS:
        raise NetworkPolicyViolationError(
            f"Host '{clean_host}' is not on the connector allowlist.",
            details={"allowed_hosts": sorted(ALLOWED_CONNECTOR_HOSTS)},
        )
