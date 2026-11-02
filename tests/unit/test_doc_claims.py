"""The documentation numbers are generated, and a stale one must be caught.

R0.5 of the plan: three documents quoted the same two numbers, typed by hand, and they
had already drifted from the branch. The mechanism that replaces the hand-editing is only
worth having if a wrong number actually turns the gate red, so that is what these tests
exercise - against a throw-away tree, not against the real documents.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("check_doc_claims", REPO_ROOT / "scripts" / "ci" / "check_doc_claims.py")
claims = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = claims
SPEC.loader.exec_module(claims)


def _tree(tmp_path: Path, block: str) -> Path:
    root = tmp_path / "repo"
    (root / "docs" / "engineering").mkdir(parents=True)
    (root / "pyproject.toml").write_text('[project]\nname = "demo"\nversion = "2.0.0"\n', encoding="utf-8")
    (root / "CHANGELOG.md").write_text("# Changelog\n\n## [2.0.0]\n\n- demo\n", encoding="utf-8")
    (root / "docs" / "engineering" / "evidence.json").write_text(
        json.dumps(
            {
                "schema": "hcs.evidence.v1",
                "version": "2.0.0",
                "tests": {"passed": 432, "skipped": 2, "failed": 0},
                "coverage": {"branch_percent": 81.4},
            }
        ),
        encoding="utf-8",
    )
    (root / "README.md").write_text(f"# demo\n\n{block}\n", encoding="utf-8")
    return root


def test_doc_claim_checker_detects_stale_number(tmp_path: Path) -> None:
    stale = _tree(
        tmp_path,
        "<!-- gen:tests -->426 passed, 2 skipped<!-- /gen:tests -->\n"
        "<!-- gen:coverage -->81 % branch coverage<!-- /gen:coverage -->",
    )
    errors = claims.check(root=stale, documents=[stale / "README.md"])
    assert len(errors) == 1, errors
    assert "gen:tests" in errors[0]
    assert "432 passed" in errors[0]


def test_doc_claim_checker_accepts_the_generated_numbers(tmp_path: Path) -> None:
    fresh = _tree(
        tmp_path,
        "<!-- gen:tests -->432 passed, 2 skipped<!-- /gen:tests -->\n"
        "<!-- gen:coverage -->81 % branch coverage<!-- /gen:coverage -->",
    )
    assert claims.check(root=fresh, documents=[fresh / "README.md"]) == []


def test_doc_claim_checker_reports_a_missing_block(tmp_path: Path) -> None:
    bare = _tree(tmp_path, "432 passed, 2 skipped, typed by hand")
    errors = claims.check(root=bare)
    assert any("no '<!-- gen:tests -->' block" in error for error in errors)
    assert any("no '<!-- gen:coverage -->' block" in error for error in errors)


def test_doc_claim_checker_reports_a_version_mismatch(tmp_path: Path) -> None:
    root = _tree(
        tmp_path,
        "<!-- gen:tests -->432 passed, 2 skipped<!-- /gen:tests -->\n"
        "<!-- gen:coverage -->81 % branch coverage<!-- /gen:coverage -->",
    )
    (root / "pyproject.toml").write_text('[project]\nname = "demo"\nversion = "2.1.0"\n', encoding="utf-8")
    errors = claims.check(root=root)
    assert any("pyproject.toml says '2.1.0'" in error for error in errors)


def test_render_is_stable_for_the_same_evidence() -> None:
    evidence = {
        "tests": {"passed": 432, "skipped": 2, "failed": 0},
        "coverage": {"branch_percent": 81.4},
        "version": "2.0.0",
    }
    assert claims.render(evidence, "tests") == "432 passed, 2 skipped"
    assert claims.render(evidence, "coverage") == "81 % branch coverage"
    assert claims.render(evidence, "version") == "2.0.0"
