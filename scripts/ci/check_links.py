"""Check relative links in Markdown files so documentation cannot rot silently.

External URLs are not fetched (CI must not depend on third-party uptime), but
every local file link and image must resolve. Anchors, query strings, fenced code
blocks and inline code spans are ignored.

    uv run python scripts/ci/check_links.py
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    ".e2e-data",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "build",
    "data",
    "playwright-report",
    "test-results",
}

FENCE_RE = re.compile(r"```.*?```|~~~.*?~~~", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
LINK_RE = re.compile(r"!?\[[^\]\n]*\]\(\s*(<[^>\n]+>|[^)\s]+)(?:\s+[\"'][^\"'\n]*[\"'])?\s*\)")
SKIP_PREFIXES = ("http://", "https://", "mailto:", "tel:", "#", "data:")


def markdown_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*.md"):
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def check_file(path: Path, root: Path) -> list[str]:
    text = FENCE_RE.sub("", path.read_text(encoding="utf-8"))
    text = INLINE_CODE_RE.sub("", text)
    problems: list[str] = []
    for match in LINK_RE.finditer(text):
        target = match.group(1).strip().strip("<>")
        if not target or target.startswith(SKIP_PREFIXES):
            continue
        if any(char in target for char in "*{}"):
            continue
        target = target.split("#", 1)[0].split("?", 1)[0]
        if not target:
            continue
        decoded = unquote(target)
        resolved = root / decoded.lstrip("/") if decoded.startswith("/") else path.parent / decoded
        if not resolved.exists():
            problems.append(f"{path.relative_to(root)} -> {target}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()

    files = markdown_files(root)
    problems: list[str] = []
    for path in files:
        problems.extend(check_file(path, root))

    for problem in problems:
        print(f"missing: {problem}", file=sys.stderr)
    print(f"Checked {len(files)} Markdown files; {len(problems)} broken local links.")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
