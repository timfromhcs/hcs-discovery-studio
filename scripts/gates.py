"""One local gate runner that mirrors ``.github/workflows/ci.yml``.

The CI file is the authority. This script exists so that "green locally" means the same
thing as "green in CI", and so that the numbers in the documentation come from a machine
readable report instead of being typed by hand (PLAN.md R0.3/R0.5).

    uv run python scripts/gates.py --level fast
    uv run python scripts/gates.py --level full
    uv run python scripts/gates.py --level science
    uv run python scripts/gates.py --level release
    uv run python scripts/gates.py --level full --only G1,G2,G4
    uv run python scripts/gates.py --level fast --json

Every run writes ``build/gate-report.json`` with the commit SHA, the dirty flag, the level,
and for each gate the command, the exit code, the duration and a one-line summary.

Rules this script keeps:

* A gate that did not run is reported as ``skipped`` with a reason, never as passed.
* ``--level fast`` is a subset of ``full``; ``science`` adds the live docking gate;
  ``release`` adds the fresh-venv artifact smoke test.
* The app is never pointed at ``./data``: any gate that starts it gets a throw-away
  ``HCS_DATA_DIR`` (see PLAN.md finding F6).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = REPO_ROOT / "build" / "gate-report.json"
SCHEMA = "hcs.gates.v1"
LEVELS = ("fast", "full", "science", "release")

#: Every CI job that carries a gate. ``ci`` (the summary job), ``dependency-review``
#: (pull-request only) and the release workflow are intentionally not gates here.
CI_GATE_JOBS = (
    "backend",
    "frontend",
    "e2e",
    "migrations",
    "wheel",
    "exe",
    "licenses",
    "dependency-audit",
    "docs",
    "science-vina",
    "secret-scan",
)


@dataclass(frozen=True)
class Step:
    """One shell step, mirroring one ``- name:`` block of the workflow."""

    name: str
    argv: tuple[str, ...]
    cwd: str | None = None
    env: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Gate:
    id: str
    name: str
    ci_jobs: tuple[str, ...]
    steps: tuple[Step, ...]
    levels: tuple[str, ...]
    description: str = ""
    #: A gate whose tool is optional locally (e.g. ``gitleaks``) can declare how to
    #: check for it. Missing tool means ``skipped`` with a reason, never ``passed``.
    requires: str | None = None
    #: A best-effort gate (the CI job itself is cloud-only). A missing tool makes it
    #: ``skipped``, which is still reported; it does not turn a local ``full`` run red,
    #: because CI runs it in the cloud. A skipped required gate does.
    optional: bool = False


@dataclass
class StepResult:
    name: str
    command: str
    exit_code: int
    duration_seconds: float
    summary: str


@dataclass
class GateResult:
    id: str
    name: str
    status: str  # "passed" | "failed" | "skipped"
    ci_jobs: list[str]
    duration_seconds: float = 0.0
    steps: list[StepResult] = field(default_factory=list)
    skip_reason: str | None = None
    optional: bool = False

    @property
    def exit_code(self) -> int:
        if self.status == "failed":
            return next((s.exit_code for s in self.steps if s.exit_code != 0), 1)
        return 0


@dataclass
class GateReport:
    schema: str
    sha: str
    branch: str
    dirty: bool
    level: str
    started_at: str
    duration_seconds: float
    gates: list[GateResult]
    ok: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "sha": self.sha,
            "branch": self.branch,
            "dirty": self.dirty,
            "level": self.level,
            "started_at": self.started_at,
            "duration_seconds": round(self.duration_seconds, 3),
            "ok": self.ok,
            "gates": [
                {
                    "id": gate.id,
                    "name": gate.name,
                    "status": gate.status,
                    "ci_jobs": gate.ci_jobs,
                    "duration_seconds": round(gate.duration_seconds, 3),
                    "skip_reason": gate.skip_reason,
                    "steps": [asdict(step) for step in gate.steps],
                }
                for gate in self.gates
            ],
        }


def _python() -> str:
    """The interpreter that is running this script (inside the project venv)."""
    return sys.executable


def _local_only_excludes() -> tuple[str, ...]:
    """Documents that live untracked in the working tree and never reach CI.

    ``PLAN.md`` and ``AGENTS.md`` are owner-gated documents kept out of the repository
    (PLAN.md §0.6). CI only ever sees tracked files, so a formatter complaint about their
    embedded examples is not a CI failure; excluding them keeps the local gate honest
    instead of silently green. Once one of them is committed the exclusion disappears.
    """
    excludes: list[str] = []
    for name in ("PLAN.md", "AGENTS.md"):
        if not (REPO_ROOT / name).exists():
            continue
        tracked = subprocess.run(
            ("git", "ls-files", "--error-unmatch", name),
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if tracked.returncode != 0:
            excludes.extend(("--exclude", name))
    return tuple(excludes)


RUFF_SCOPE: tuple[str, ...] = (".", *_local_only_excludes())


GATES: tuple[Gate, ...] = (
    Gate(
        id="G0",
        name="Lockfile is current",
        ci_jobs=("backend",),
        steps=(Step("uv lock --check", ("uv", "lock", "--check")),),
        levels=("full", "science", "release"),
        requires="uv",
    ),
    Gate(
        id="G1",
        name="Formatting",
        ci_jobs=("backend",),
        steps=(Step("ruff format --check", ("uv", "run", "ruff", "format", "--check", *RUFF_SCOPE)),),
        levels=("fast", "full", "science", "release"),
        requires="uv",
    ),
    Gate(
        id="G2",
        name="Lint",
        ci_jobs=("backend",),
        steps=(Step("ruff check", ("uv", "run", "ruff", "check", *RUFF_SCOPE)),),
        levels=("fast", "full", "science", "release"),
        requires="uv",
    ),
    Gate(
        id="G3",
        name="Types",
        ci_jobs=("backend",),
        steps=(
            Step("prepare_typecheck", ("uv", "run", _python(), "scripts/ci/prepare_typecheck.py")),
            Step("mypy", ("uv", "run", "mypy")),
        ),
        levels=("fast", "full", "science", "release"),
        requires="uv",
    ),
    Gate(
        id="G4",
        name="Tests with coverage",
        ci_jobs=("backend",),
        steps=(
            Step(
                "pytest",
                (
                    "uv",
                    "run",
                    "pytest",
                    "-q",
                    "--cov=hcs_discovery",
                    "--cov-branch",
                    "--cov-report=term-missing",
                    "--cov-fail-under=70",
                    # Machine readable outputs: scripts/ci/check_doc_claims.py reads these
                    # and the documentation numbers are generated from them (R0.5).
                    "--junitxml=build/junit.xml",
                    "--cov-report=json:build/coverage.json",
                ),
            ),
        ),
        levels=("fast", "full", "science", "release"),
        requires="uv",
    ),
    Gate(
        id="G5",
        name="Frontend typecheck and build",
        ci_jobs=("frontend",),
        steps=(
            Step("npm ci", ("npm", "ci"), cwd="apps/web"),
            Step("npm run typecheck", ("npm", "run", "typecheck"), cwd="apps/web"),
            Step("npm run build", ("npm", "run", "build"), cwd="apps/web"),
            Step("node scripts/ci/check_bundle_budget.mjs", ("node", "scripts/ci/check_bundle_budget.mjs")),
        ),
        levels=("full", "science", "release"),
        requires="npm",
    ),
    Gate(
        id="G6",
        name="Playwright end-to-end",
        ci_jobs=("e2e",),
        steps=(Step("npm run test:e2e", ("npm", "run", "test:e2e"), cwd="apps/web"),),
        levels=("full", "science", "release"),
        requires="npm",
    ),
    Gate(
        id="G7",
        name="Clean migration of an empty data directory",
        ci_jobs=("migrations",),
        steps=(
            Step("db upgrade", ("uv", "run", "hcs-discovery", "db", "upgrade"), env=(("HCS_TEMP_DATA", "1"),)),
            Step("db current", ("uv", "run", "hcs-discovery", "db", "current"), env=(("HCS_TEMP_DATA", "1"),)),
            Step("doctor", ("uv", "run", "hcs-discovery", "doctor"), env=(("HCS_TEMP_DATA", "1"),)),
        ),
        levels=("full", "science", "release"),
        requires="uv",
    ),
    Gate(
        id="G8",
        name="Wheel build and install smoke test",
        ci_jobs=("wheel",),
        steps=(
            Step("npm ci", ("npm", "ci"), cwd="apps/web"),
            Step("npm run build", ("npm", "run", "build"), cwd="apps/web"),
            Step("uv build --wheel", ("uv", "build", "--wheel")),
            Step("install into a fresh venv", ("__python__", "{gate_script}", "install")),
            Step("smoke test the installed application", ("__python__", "{gate_script}", "smoke")),
        ),
        levels=("full", "science", "release"),
        requires="uv",
    ),
    Gate(
        id="G9",
        name="License policy",
        ci_jobs=("licenses",),
        steps=(
            Step("check_licenses.py", ("uv", "run", _python(), "scripts/ci/check_licenses.py")),
            Step("check_licenses.mjs", ("node", "scripts/ci/check_licenses.mjs")),
        ),
        levels=("full", "science", "release"),
        requires="uv",
    ),
    Gate(
        id="G10",
        name="Dependency vulnerability audit",
        ci_jobs=("dependency-audit",),
        steps=(
            Step(
                "export requirements",
                (
                    "uv",
                    "export",
                    "--frozen",
                    "--no-dev",
                    "--no-emit-project",
                    "--format",
                    "requirements-txt",
                    "--output-file",
                    "build/requirements-audit.txt",
                ),
            ),
            Step(
                "pip-audit",
                (
                    "uvx",
                    "--from",
                    "pip-audit==2.10.1",
                    "pip-audit",
                    "--requirement",
                    "build/requirements-audit.txt",
                    "--progress-spinner",
                    "off",
                    "--strict",
                ),
            ),
            Step("npm audit", ("npm", "audit", "--omit=dev", "--audit-level=high"), cwd="apps/web"),
        ),
        levels=("full", "science", "release"),
        requires="uv",
    ),
    Gate(
        id="G11",
        name="Documentation links and generated claims",
        ci_jobs=("docs",),
        steps=(
            Step("check_links.py", ("uv", "run", "--no-project", _python(), "scripts/ci/check_links.py")),
            Step("check_doc_claims.py", ("uv", "run", "--no-project", _python(), "scripts/ci/check_doc_claims.py")),
        ),
        levels=("full", "science", "release"),
        requires="uv",
    ),
    Gate(
        id="G12",
        name="Docking science gate (live Vina)",
        ci_jobs=("science-vina",),
        steps=(
            Step(
                "live Vina tests",
                ("uv", "run", "pytest", "-q", "tests/scientific/test_vina_adapter.py", "-rs"),
                env=(("HCS_REQUIRE_VINA", "1"),),
            ),
            Step("redocking gate", ("uv", "run", _python(), "scripts/science/redock_vina_reference.py", "--gate")),
        ),
        levels=("science", "release"),
        requires="uv",
    ),
    Gate(
        id="G13",
        name="Secret scan",
        ci_jobs=("secret-scan",),
        steps=(Step("gitleaks detect", ("gitleaks", "detect", "--no-banner", "--redact")),),
        levels=("full", "science", "release"),
        requires="gitleaks",
        optional=True,
    ),
    Gate(
        id="G14",
        name="Release artifact probe",
        ci_jobs=("wheel",),
        steps=(
            Step("wheel metadata", ("__python__", "{gate_script}", "metadata")),
            Step("sbom probe", ("uv", "export", "--frozen", "--no-emit-project", "-o", "build/sbom-requirements.txt")),
        ),
        levels=("release",),
        requires="uv",
    ),
    Gate(
        id="G15",
        name="One-file executable build and smoke test",
        ci_jobs=("exe",),
        steps=(Step("build_executable", ("uv", "run", _python(), "scripts/release/build_executable.py")),),
        levels=("release",),
        requires="uv",
    ),
)


# --------------------------------------------------------------------------- helpers


def _git(*args: str) -> str:
    try:
        completed = subprocess.run(
            ("git", *args),
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return completed.stdout.strip()


def _which(token: str) -> str | None:
    if token in ("uv", "npm", "node", "git"):
        return shutil.which(token)
    return shutil.which(token)


def _summary(text: str, limit: int = 300) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    interesting = [
        line
        for line in lines
        if any(
            word in line.lower() for word in ("passed", "failed", "error", "error:", "success", "no issues", "found")
        )
    ]
    chosen = interesting[-1] if interesting else lines[-1]
    return chosen[:limit]


def _resolve_argv(step: Step) -> list[str]:
    gate_script = str(REPO_ROOT / "scripts" / "gates_wheel.py")
    argv = [
        sys.executable if token == "__python__" else gate_script if token == "{gate_script}" else token
        for token in step.argv
    ]
    if argv and argv[0] not in ("__python__",):
        resolved = _which(argv[0])
        if resolved:
            argv[0] = resolved
    return argv


def _run_step(step: Step, env: dict[str, str], timeout: float) -> StepResult:
    argv = _resolve_argv(step)
    cwd = REPO_ROOT / step.cwd if step.cwd else REPO_ROOT
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout or None,
        )
        code, out, err = completed.returncode, completed.stdout, completed.stderr
    except subprocess.TimeoutExpired as exc:
        code = 124
        out = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        err = f"timed out after {timeout:g} s"
    except OSError as exc:
        code, out, err = 127, "", f"{type(exc).__name__}: {exc}"
    duration = time.perf_counter() - started
    return StepResult(
        name=step.name,
        command=" ".join(step.argv),
        exit_code=code,
        duration_seconds=duration,
        summary=_summary(out or err),
    )


def _gate_env(extra: Iterable[tuple[str, str]], temp_data: Path | None) -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    if temp_data is not None:
        env["HCS_DATA_DIR"] = str(temp_data)
    for key, value in extra:
        if key == "HCS_TEMP_DATA" and temp_data is not None:
            env["HCS_DATA_DIR"] = str(temp_data)
        else:
            env[key] = value
    return env


def selected_gates(level: str, only: Sequence[str] | None = None) -> list[Gate]:
    if level not in LEVELS:
        raise ValueError(f"level must be one of {', '.join(LEVELS)}")
    gates = [gate for gate in GATES if level in gate.levels]
    if only:
        wanted = {item.strip().upper() for item in only if item.strip()}
        unknown = wanted - {gate.id for gate in GATES}
        if unknown:
            raise ValueError(f"unknown gate id(s): {', '.join(sorted(unknown))}")
        gates = [gate for gate in gates if gate.id in wanted]
    return gates


def run(
    level: str = "fast",
    *,
    keep_going: bool = False,
    only: Sequence[str] | None = None,
    timeout: float = 3600.0,
    report_path: Path | None = None,
) -> GateReport:
    """Run the gates for ``level`` and return the report (also written to disk)."""
    gates = selected_gates(level, only)
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    started = time.perf_counter()
    results: list[GateResult] = []
    temp_root = Path(tempfile.mkdtemp(prefix="hcs-gates-"))

    for gate in gates:
        if gate.requires and not _which(gate.requires):
            results.append(
                GateResult(
                    id=gate.id,
                    name=gate.name,
                    status="skipped",
                    ci_jobs=list(gate.ci_jobs),
                    skip_reason=f"{gate.requires} is not installed on this machine",
                    optional=gate.optional,
                )
            )
            continue
        gate_started = time.perf_counter()
        step_results: list[StepResult] = []
        status = "passed"
        for index, step in enumerate(gate.steps):
            data_dir = temp_root / f"{gate.id}-{index}"
            env = _gate_env(step.env, data_dir)
            print(f"[{gate.id}] {gate.name}: {step.name} ... ", end="", flush=True)
            result = _run_step(step, env, timeout)
            step_results.append(result)
            print("ok" if result.exit_code == 0 else f"FAILED (exit {result.exit_code})", flush=True)
            if result.exit_code != 0:
                status = "failed"
                if not keep_going:
                    break
        results.append(
            GateResult(
                id=gate.id,
                name=gate.name,
                status=status,
                ci_jobs=list(gate.ci_jobs),
                duration_seconds=time.perf_counter() - gate_started,
                steps=step_results,
                optional=gate.optional,
            )
        )
        if status == "failed" and not keep_going:
            break

    ok = all(gate.status == "passed" or (gate.status == "skipped" and gate.optional) for gate in results) and len(
        results
    ) == len(gates)
    report = GateReport(
        schema=SCHEMA,
        sha=_git("rev-parse", "HEAD"),
        branch=_git("rev-parse", "--abbrev-ref", "HEAD"),
        dirty=bool(_git("status", "--porcelain")),
        level=level,
        started_at=started_at,
        duration_seconds=time.perf_counter() - started,
        gates=results,
        ok=ok,
    )
    target = Path(report_path) if report_path else REPORT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--level", choices=LEVELS, default="fast")
    parser.add_argument("--only", default="", help="comma separated gate ids, e.g. G1,G4")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    parser.add_argument("--keep-going", action="store_true", help="run every gate even after a failure")
    parser.add_argument("--timeout", type=float, default=3600.0, help="per step, seconds (0 disables)")
    args = parser.parse_args(argv)

    try:
        report = run(
            args.level,
            keep_going=args.keep_going,
            only=[item for item in args.only.split(",") if item.strip()],
            timeout=args.timeout,
        )
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        for gate in report.gates:
            detail = f" ({gate.skip_reason})" if gate.skip_reason else ""
            print(f"{gate.id:>3} {gate.status:<7} {gate.name}{detail}  {gate.duration_seconds:.1f}s")
        print(f"\nreport: {REPORT_PATH}")
        print(f"result: {'PASS' if report.ok else 'FAIL'} on {report.sha[:7] or 'unknown'} ({report.level})")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
