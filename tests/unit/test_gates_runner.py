"""The gate runner is the thing that decides whether "green" means anything.

These tests protect three properties that matter more than the gate list itself:

* the report identifies exactly which commit it was produced on and whether the tree was
  dirty, because a green report for some other commit is not evidence;
* a failing gate makes the process exit non-zero and marks the report ``ok: false``;
* the gate ids and their CI job names are read from ``ci.yml``, so the runner and the
  workflow cannot drift apart silently.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

SPEC = importlib.util.spec_from_file_location("gates_runner", REPO_ROOT / "scripts" / "gates.py")
gates = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
# dataclasses resolve their own module by name, so it has to be registered first.
sys.modules[SPEC.name] = gates
SPEC.loader.exec_module(gates)


def _workflow() -> dict:
    return yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8"))


def _fake_step(exit_code: int):
    def fake(step, env, timeout):
        return gates.StepResult(
            name=step.name,
            command=" ".join(step.argv),
            exit_code=exit_code,
            duration_seconds=0.001,
            summary="stub",
        )

    return fake


def test_report_contains_sha_and_dirty_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gates, "_run_step", _fake_step(0))
    report = gates.run("fast", only=["G1"], report_path=tmp_path / "gate-report.json")

    expected_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    expected_dirty = bool(
        subprocess.run(["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()
    )

    assert report.sha == expected_sha
    assert report.dirty is expected_dirty
    assert report.schema == gates.SCHEMA
    assert report.level == "fast"
    assert [gate.id for gate in report.gates] == ["G1"]
    assert report.ok is True

    written = json.loads((tmp_path / "gate-report.json").read_text("utf-8"))
    assert written["sha"] == expected_sha
    assert written["gates"][0]["steps"][0]["exit_code"] == 0


def test_failed_gate_sets_nonzero_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gates, "_run_step", _fake_step(1))
    monkeypatch.setattr(gates, "REPORT_PATH", tmp_path / "gate-report.json")
    assert gates.main(["--level", "fast", "--only", "G2", "--json"]) == 1

    report = json.loads((tmp_path / "gate-report.json").read_text("utf-8"))
    assert report["ok"] is False
    assert report["gates"][0]["status"] == "failed"
    assert report["gates"][0]["steps"][0]["exit_code"] == 1


def test_gate_ids_match_ci_job_names() -> None:
    workflow = _workflow()
    job_ids = set(workflow["jobs"])

    for gate in gates.GATES:
        for job in gate.ci_jobs:
            assert job in job_ids, f"{gate.id} names the unknown CI job {job!r}"

    referenced = {job for gate in gates.GATES for job in gate.ci_jobs}
    for job in gates.CI_GATE_JOBS:
        assert job in job_ids, f"CI_GATE_JOBS lists {job!r}, which ci.yml does not define"
        assert job in referenced, f"the CI job {job!r} has no gate in scripts/gates.py"

    # The summary job and the pull-request-only dependency review carry no local gate.
    assert job_ids - referenced == {"ci", "dependency-review"}


def test_gate_ids_are_unique_and_levels_nest() -> None:
    ids = [gate.id for gate in gates.GATES]
    assert len(ids) == len(set(ids))

    fast = {gate.id for gate in gates.selected_gates("fast")}
    full = {gate.id for gate in gates.selected_gates("full")}
    science = {gate.id for gate in gates.selected_gates("science")}
    release = {gate.id for gate in gates.selected_gates("release")}
    assert fast < full < science < release


def test_only_filter_rejects_unknown_ids() -> None:
    with pytest.raises(ValueError, match="unknown gate"):
        gates.selected_gates("fast", ["G99"])


def test_a_missing_optional_tool_is_skipped_not_passed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gates, "_which", lambda token: None)
    report = gates.run("full", only=["G13"], report_path=tmp_path / "gate-report.json")
    gate = report.gates[0]
    assert gate.status == "skipped", "a missing tool is never reported as passed"
    assert "gitleaks" in (gate.skip_reason or "")
    # G13 is best effort locally: CI runs it in the cloud, so it does not turn a local
    # full run red - but the status stays "skipped" and is printed.
    assert report.ok is True


def test_a_missing_tool_for_a_required_gate_fails_the_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gates, "_which", lambda token: None)
    report = gates.run("science", only=["G12"], report_path=tmp_path / "gate-report.json")
    assert report.gates[0].status == "skipped"
    assert report.ok is False, "the science gate is required, so a skip is not green"
