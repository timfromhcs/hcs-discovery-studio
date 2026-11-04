"""Reject replacement characters and the classic UTF-8 mojibake in tracked text.

This repository has twice shipped double-encoded text ("FranÃ§ais", "â¤ï¸"): a
PowerShell write turned a UTF-8 byte stream into Latin-1-looking text, and the
result reached a product footer before anyone noticed. A test that only looks at
Python is not enough — the broken string lived in a TypeScript constant.

The check walks the files Git tracks (falling back to a source tree walk), decodes
strict UTF-8 and rejects:

* U+FFFD, the replacement character (a decode already failed somewhere);
* the common mojibake prefixes that survive a Latin-1 round trip.

Binary assets and generated directories are skipped by extension/path.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TEXT_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".css",
    ".html",
    ".json",
    ".md",
    ".yml",
    ".yaml",
    ".toml",
    ".cff",
    ".txt",
    ".svg",
    ".wgsl",
    ".ps1",
    ".sh",
    ".ini",
    ".cfg",
    ".example",
}
SKIP_PARTS = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".serena",
    "screenshots",
    "__pycache__",
}
#: Files that quote bad encoding on purpose (the log that documents the repair).
SKIP_FILES = {"docs/engineering/AGENT_LOG.md"}
#: Sequences that appear when UTF-8 is decoded as Latin-1/cp1252 and re-encoded.
MOJIBAKE = ("â€", "Ã¤", "Ã¶", "Ã¼", "ÃŸ", "Ã©", "Ã¨", "â¤ï¸", "Â ", "ï»¿")
#: Generic double-encoding shape: "â" or "Ã" followed by a C1 control byte. This is
#: what "❤" becomes (E2 9D A4 -> C3 A2 C2 9D C2 A4 -> "â\u009d¤"), and a literal list
#: cannot cover every code point.
DOUBLE_ENCODED = re.compile("[\u00e2\u00c3][\u0080-\u009f]")


def tracked_files(root: Path) -> list[Path]:
    try:
        output = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=root,
            capture_output=True,
            check=True,
            timeout=60,
        ).stdout
        names = [name for name in output.decode("utf-8", errors="replace").split("\0") if name]
        return [root / name for name in names]
    except (OSError, subprocess.SubprocessError):
        return [path for path in root.rglob("*") if path.is_file()]


def check(root: Path = REPO_ROOT) -> list[str]:
    problems: list[str] = []
    for path in tracked_files(root):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        relative = path.relative_to(root)
        if any(part in SKIP_PARTS for part in relative.parts):
            continue
        if relative.as_posix() in SKIP_FILES:
            continue
        data = path.read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            problems.append(f"{relative}: not valid UTF-8 ({exc})")
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if "\ufffd" in line:
                problems.append(f"{relative}:{number}: replacement character")
            for marker in MOJIBAKE:
                if marker in line:
                    problems.append(f"{relative}:{number}: mojibake {marker!r}")
            if DOUBLE_ENCODED.search(line):
                problems.append(f"{relative}:{number}: double-encoded UTF-8")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    parser.add_argument("--all", action="store_true", help="walk the tree instead of git ls-files")
    args = parser.parse_args(argv)
    root = args.root
    problems = check(root)
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        print(f"{len(problems)} encoding problem(s).", file=sys.stderr)
        return 1
    print("Text encoding is clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
