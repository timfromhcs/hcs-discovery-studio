"""Fail if an installed Python distribution uses a license outside the policy.

The policy is deliberately narrow: every dependency of the core product must be
permissively licensed. Copyleft licenses are not accepted for distributed code
without a reviewed exception. Run with the project environment:

    uv run python scripts/ci/check_licenses.py

The check reads PEP 639 ``License-Expression`` metadata first, then the legacy
``License`` field, then Trove classifiers. Packages whose metadata does not
resolve to a known SPDX identifier fail closed instead of being ignored.
"""

from __future__ import annotations

import argparse
import importlib.metadata as metadata
import re
import sys

# Licenses accepted for dependencies bundled in the wheel or required at runtime.
ALLOWED_SPDX = {
    "0BSD",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "CC0-1.0",
    "ISC",
    "MIT",
    "MIT-CMU",
    "MPL-2.0",
    "PSF-2.0",
    "Python-2.0",
    "Unlicense",
    "Zlib",
}

# Legacy free-text values that map unambiguously to an SPDX identifier.
LEGACY_ALIASES = {
    "apache 2.0": "Apache-2.0",
    "apache-2.0": "Apache-2.0",
    "apache license 2.0": "Apache-2.0",
    "apache software license": "Apache-2.0",
    "bsd": "BSD-3-Clause",
    "bsd license": "BSD-3-Clause",
    "bsd-2-clause": "BSD-2-Clause",
    "bsd-3-clause": "BSD-3-Clause",
    "isc": "ISC",
    "isc license": "ISC",
    "mit": "MIT",
    "mit license": "MIT",
    "mozilla public license 2.0 (mpl 2.0)": "MPL-2.0",
    "mpl-2.0": "MPL-2.0",
    "psf-2.0": "PSF-2.0",
}

CLASSIFIER_ALIASES = {
    "License :: OSI Approved :: Apache Software License": "Apache-2.0",
    "License :: OSI Approved :: BSD License": "BSD-3-Clause",
    "License :: OSI Approved :: ISC License (ISCL)": "ISC",
    "License :: OSI Approved :: MIT License": "MIT",
    "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
    "License :: OSI Approved :: Python Software Foundation License": "PSF-2.0",
    "License :: OSI Approved :: The Unlicense (Unlicense)": "Unlicense",
    "License :: OSI Approved :: zlib/libpng License": "Zlib",
}

TOKEN_RE = re.compile(r"[A-Za-z0-9.+\-]+")


def _split_expression(expression: str) -> list[str]:
    """Return the identifiers in an SPDX expression, dropping AND/OR/WITH glue."""

    return [token for token in TOKEN_RE.findall(expression) if token not in {"AND", "OR", "WITH"}]


def _normalise(value: str) -> str | None:
    cleaned = value.strip().strip("()").strip()
    if not cleaned:
        return None
    alias = LEGACY_ALIASES.get(cleaned.lower())
    if alias:
        return alias
    if cleaned in ALLOWED_SPDX:
        return cleaned
    return None


def resolve_license(dist: metadata.Distribution) -> tuple[set[str], str]:
    """Return (identifiers, source) for a distribution."""

    expression = dist.metadata.get("License-Expression")
    if expression:
        identifiers = {token for token in _split_expression(expression)}
        return identifiers, f"License-Expression: {expression}"

    legacy = dist.metadata.get("License") or ""
    if legacy:
        # Some packages embed the full license text in this field. Only accept a
        # value that resolves as a whole; never guess from a substring.
        normalised = _normalise(legacy)
        if normalised:
            return {normalised}, f"License: {legacy[:80]}"

    classifiers = [item for item in (dist.metadata.get_all("Classifier") or []) if item.startswith("License ::")]
    identifiers: set[str] = set()
    for classifier in classifiers:
        mapped = CLASSIFIER_ALIASES.get(classifier)
        if mapped:
            identifiers.add(mapped)
    if identifiers:
        return identifiers, "Classifier: " + "; ".join(classifiers)

    return set(), "unresolved"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable report instead of a table.",
    )
    args = parser.parse_args()

    rows: list[dict[str, object]] = []
    failures: list[str] = []
    for dist in sorted(metadata.distributions(), key=lambda item: item.metadata["Name"].lower()):
        name = dist.metadata["Name"]
        if name.lower() == "hcs-discovery-studio":
            continue
        identifiers, source = resolve_license(dist)
        allowed = bool(identifiers) and identifiers <= ALLOWED_SPDX
        if not allowed:
            failures.append(f"{name} {dist.version}: {source}")
        rows.append(
            {
                "name": name,
                "version": dist.version,
                "license": " AND ".join(sorted(identifiers)) or "UNKNOWN",
                "source": source,
                "allowed": allowed,
            }
        )

    if args.json:
        import json

        print(json.dumps({"packages": rows, "failures": failures}, indent=2))
    else:
        for row in rows:
            status = "ok" if row["allowed"] else "FAIL"
            print(f"{status:4}  {row['name']:<28} {row['version']:<12} {row['license']}")
        print(f"\n{len(rows)} packages checked; {len(failures)} outside policy.")

    if failures:
        print("\nLicense policy failures:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        print(
            "\nAdd a reviewed exception only after checking the license text and the "
            "distribution obligations. See docs/research/COMPONENT_AND_LICENSE_AUDIT.md.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
