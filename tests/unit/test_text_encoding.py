"""The encoding gate must catch the mojibake that reached a product footer."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "check_text_encoding", REPO_ROOT / "scripts" / "ci" / "check_text_encoding.py"
)
encoding = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = encoding
SPEC.loader.exec_module(encoding)


def test_clean_tree_has_no_problems(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("# clean · 3.0.0\n", encoding="utf-8")
    (root / "app.ts").write_text('export const X = "Made with \\u2764\\ufe0f by hcsmedia";\n', encoding="utf-8")
    assert encoding.check(root) == []


def test_double_encoded_text_is_reported(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    # Exactly what the broken footer contained: UTF-8 bytes decoded as Latin-1 and
    # written back as UTF-8.
    (root / "constants.ts").write_bytes(b'export const CREDIT = "Made with \xc3\xa2\xc2\x9d\xc2\xa4 by hcsmedia";\n')
    problems = encoding.check(root)
    assert any(
        "constants.ts" in problem and ("mojibake" in problem or "double-encoded" in problem) for problem in problems
    )


def test_invalid_utf8_is_reported(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "notes.md").write_bytes(b"broken \xff byte\n")
    problems = encoding.check(root)
    assert any("not valid UTF-8" in problem for problem in problems)


def test_the_repair_log_is_exempt(tmp_path: Path):
    root = tmp_path / "repo"
    (root / "docs" / "engineering").mkdir(parents=True)
    (root / "docs" / "engineering" / "AGENT_LOG.md").write_text("it said â¤ï¸ once\n", encoding="utf-8")
    assert encoding.check(root) == []
