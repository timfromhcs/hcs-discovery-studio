"""Guard the release workflow against tagging a commit with the wrong version.

Checks that the git tag (``vX.Y.Z``) matches ``project.version`` in
``pyproject.toml`` and that ``CHANGELOG.md`` has a matching section. The release
workflow runs this before building artifacts.

    python scripts/release/verify_version.py v0.1.0
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: verify_version.py <tag>", file=sys.stderr)
        return 2

    tag = argv[1]
    root = Path(__file__).resolve().parents[2]
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]

    expected = f"v{version}"
    if tag != expected:
        print(f"tag {tag!r} does not match project version {version!r} (expected {expected!r})", file=sys.stderr)
        return 1

    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    if not re.search(rf"^##\s+\[?{re.escape(version)}\]?", changelog, re.MULTILINE):
        print(f"CHANGELOG.md has no section for version {version}", file=sys.stderr)
        return 1

    print(f"release tag {tag} matches pyproject version {version} and CHANGELOG.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
