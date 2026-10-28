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

    clean_host = host.lower().split(":")[0].strip()
    if clean_host not in ALLOWED_CONNECTOR_HOSTS:
        raise NetworkPolicyViolationError(
            f"Host '{clean_host}' is not on the connector allowlist.",
            details={"allowed_hosts": sorted(ALLOWED_CONNECTOR_HOSTS)},
        )
