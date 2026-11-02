"""Keep the numbers in the documentation attached to a measurement.

Three documents quote the same two numbers (how many backend tests passed, and the branch
coverage). When those were typed by hand they drifted apart: the README said 421, the
release record said 421, and the branch measured 426 (PLAN.md finding F5). This module
owns the numbers instead:

* ``--write`` reads ``build/junit.xml`` and ``build/coverage.json`` (produced by the G4
  gate), writes ``docs/engineering/evidence.json`` and fills the marked blocks in the
  documents;
* without ``--write`` it only verifies: every marked block must equal the rendered value
  from ``evidence.json``, and the version in ``pyproject.toml`` must match the version in
  the evidence file and have a ``CHANGELOG.md`` section.

A marked block looks like this, on one line or several::

    <!-- gen:tests -->426 passed, 2 skipped<!-- /gen:tests -->

The checker is deliberately strict about a *missing* block: a document that quotes a
number outside a generated block cannot be verified, and the gate says so.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
import xml.etree.ElementTree as ElementTree
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = REPO_ROOT / "docs" / "engineering" / "evidence.json"
SCHEMA = "hcs.evidence.v1"

#: Documents that quote measured numbers, and the blocks each one must carry.
DOCUMENTS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "engineering" / "IMPLEMENTATION_STATUS.md",
    REPO_ROOT / "docs" / "engineering" / "RELEASE_EVIDENCE.md",
)
REQUIRED_KEYS = ("tests", "coverage")


def _block_pattern(key: str) -> re.Pattern[str]:
    return re.compile(rf"<!-- gen:{re.escape(key)} -->(.*?)<!-- /gen:{re.escape(key)} -->", re.DOTALL)


def render(evidence: dict[str, object], key: str) -> str:
    tests = evidence["tests"]
    coverage = evidence["coverage"]
    assert isinstance(tests, dict) and isinstance(coverage, dict)
    if key == "tests":
        parts = [f"{tests['passed']} passed", f"{tests['skipped']} skipped"]
        if tests.get("deselected"):
            parts.append(f"{tests['deselected']} deselected")
        return ", ".join(parts)
    if key == "coverage":
        return f"{coverage['branch_percent']:.0f} % branch coverage"
    if key == "version":
        return str(evidence["version"])
    raise KeyError(key)


def read_measurements(junit: Path, coverage: Path) -> dict[str, object]:
    """Count tests from JUnit XML and read branch coverage from the coverage JSON."""
    tree = ElementTree.parse(junit)
    cases = tree.getroot().iter("testcase")
    passed = skipped = failed = 0
    for case in cases:
        if case.find("skipped") is not None:
            skipped += 1
        elif case.find("failure") is not None or case.find("error") is not None:
            failed += 1
        else:
            passed += 1
    document = json.loads(coverage.read_text(encoding="utf-8"))
    percent = float(document["totals"]["percent_covered"])
    return {
        "tests": {"passed": passed, "skipped": skipped, "failed": failed},
        "coverage": {"branch_percent": round(percent, 1)},
    }


def _project_version(root: Path) -> str:
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def check(root: Path = REPO_ROOT, documents=None) -> list[str]:
    """Verify every generated block against ``root``; returns a list of problems."""
    root = Path(root)
    evidence_path = root / "docs" / "engineering" / "evidence.json"
    if documents is None:
        documents = tuple(root / path.relative_to(REPO_ROOT) for path in DOCUMENTS)
    errors: list[str] = []
    if not evidence_path.exists():
        return [f"{evidence_path} is missing; run this script with --write"]
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if evidence.get("schema") != SCHEMA:
        errors.append(f"evidence.json has schema {evidence.get('schema')!r}, expected {SCHEMA!r}")

    version = _project_version(root)
    if str(evidence.get("version")) != version:
        errors.append(f"evidence.json says version {evidence.get('version')!r}, pyproject.toml says {version!r}")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    if not re.search(rf"^##\s+\[?{re.escape(version)}\]?", changelog, re.MULTILINE):
        errors.append(f"CHANGELOG.md has no '## [{version}]' section")

    for document in documents:
        if not document.exists():
            errors.append(f"{document} is missing")
            continue
        text = document.read_text(encoding="utf-8")
        relative = document.relative_to(root)
        for key in REQUIRED_KEYS:
            matches = _block_pattern(key).findall(text)
            if not matches:
                errors.append(f"{relative}: no '<!-- gen:{key} -->' block, so the number there cannot be checked")
                continue
            expected = render(evidence, key)
            for found in matches:
                if found.strip() != expected:
                    errors.append(f"{relative}: gen:{key} says {found.strip()!r}, measured is {expected!r}")
    return errors


def write_from_build(junit: Path, coverage: Path) -> dict[str, object]:
    measurements = read_measurements(junit, coverage)
    evidence: dict[str, object] = {
        "schema": SCHEMA,
        "version": _project_version(REPO_ROOT),
        **measurements,
    }
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for document in DOCUMENTS:
        if not document.exists():
            continue
        text = document.read_text(encoding="utf-8")
        for key in REQUIRED_KEYS:
            pattern = _block_pattern(key)
            if pattern.search(text):
                text = pattern.sub(lambda match, k=key: f"<!-- gen:{k} -->{render(evidence, k)}<!-- /gen:{k} -->", text)
        document.write_text(text, encoding="utf-8")
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true", help="regenerate evidence.json and the marked blocks")
    parser.add_argument("--junit", default=str(REPO_ROOT / "build" / "junit.xml"))
    parser.add_argument("--coverage", default=str(REPO_ROOT / "build" / "coverage.json"))
    args = parser.parse_args(argv)

    if args.write:
        junit, coverage = Path(args.junit), Path(args.coverage)
        for path in (junit, coverage):
            if not path.exists():
                print(
                    f"{path} is missing; run the G4 gate first (python scripts/gates.py --level fast --only G4)",
                    file=sys.stderr,
                )
                return 2
        evidence = write_from_build(junit, coverage)
        print(f"wrote {EVIDENCE.relative_to(REPO_ROOT)}: {render(evidence, 'tests')}; {render(evidence, 'coverage')}")

    errors = check()
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
