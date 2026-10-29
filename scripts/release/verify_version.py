"""Guard the release workflow against tagging a commit with the wrong version.

Tags map to PEP 440 package versions as follows:

- ``vX.Y.Z``      -> ``X.Y.Z``      (Stable)
- ``vX.Y.Z-rc.N`` -> ``X.Y.ZrcN``   (release candidate, published as a pre-release)

The script checks that the tag matches ``project.version`` in ``pyproject.toml``
under that mapping and that ``CHANGELOG.md`` has a section for ``X.Y.Z``. Any
other tag shape is rejected. The release workflow runs this before building.

    python scripts/release/verify_version.py v2.0.0
    python scripts/release/verify_version.py v2.0.0-rc.1
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

TAG_PATTERN = re.compile(r"^v(?P<base>\d+\.\d+\.\d+)(?:-rc\.(?P<rc>[1-9]\d*))?$")


def expected_package_version(tag: str) -> tuple[str, str]:
    """Return ``(package_version, changelog_version)`` for a release tag."""
    match = TAG_PATTERN.match(tag)
    if match is None:
        raise ValueError(f"tag {tag!r} is not of the form vX.Y.Z or vX.Y.Z-rc.N")
    base = match.group("base")
    rc = match.group("rc")
    return (f"{base}rc{rc}" if rc else base, base)


def check(tag: str, root: Path) -> list[str]:
    try:
        expected, changelog_version = expected_package_version(tag)
    except ValueError as exc:
        return [str(exc)]
    errors: list[str] = []
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    if version != expected:
        errors.append(f"tag {tag!r} requires project version {expected!r}, but pyproject.toml has {version!r}")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    if not re.search(rf"^##\s+\[?{re.escape(changelog_version)}\]?", changelog, re.MULTILINE):
        errors.append(f"CHANGELOG.md has no section for version {changelog_version}")
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: verify_version.py <tag>", file=sys.stderr)
        return 2
    tag = argv[1]
    errors = check(tag, Path(__file__).resolve().parents[2])
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        return 1
    print(f"release tag {tag} matches pyproject.toml and CHANGELOG.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
