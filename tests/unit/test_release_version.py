"""Release tag to package version mapping used by the release workflow."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "release" / "verify_version.py"
_spec = importlib.util.spec_from_file_location("verify_version", SCRIPT)
assert _spec is not None and _spec.loader is not None
verify_version = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verify_version)


@pytest.mark.parametrize(
    ("tag", "package", "changelog"),
    [("v2.0.0", "2.0.0", "2.0.0"), ("v2.0.0-rc.1", "2.0.0rc1", "2.0.0"), ("v10.2.3-rc.12", "10.2.3rc12", "10.2.3")],
)
def test_tag_maps_to_pep440_version(tag: str, package: str, changelog: str) -> None:
    assert verify_version.expected_package_version(tag) == (package, changelog)


@pytest.mark.parametrize("tag", ["2.0.0", "v2.0", "v2.0.0rc1", "v2.0.0-rc.0", "v2.0.0-beta.1", "v2.0.0-rc.1-x"])
def test_unsupported_tag_shapes_are_rejected(tag: str) -> None:
    with pytest.raises(ValueError):
        verify_version.expected_package_version(tag)


def _project(tmp_path: Path, version: str, changelog_heading: str) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "pyproject.toml").write_text(f'[project]\nname = "x"\nversion = "{version}"\n', encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(f"# Changelog\n\n{changelog_heading}\n", encoding="utf-8")
    return tmp_path


def test_stable_tag_rejects_candidate_package_and_vice_versa(tmp_path: Path) -> None:
    candidate = _project(tmp_path / "rc", "2.0.0rc1", "## [2.0.0] - unreleased")
    assert verify_version.check("v2.0.0-rc.1", candidate) == []
    assert verify_version.check("v2.0.0", candidate)

    stable = _project(tmp_path / "stable", "2.0.0", "## [2.0.0] - 2026-10-29")
    assert verify_version.check("v2.0.0", stable) == []
    assert verify_version.check("v2.0.0-rc.1", stable)


def test_missing_changelog_section_is_reported(tmp_path: Path) -> None:
    project = _project(tmp_path, "2.0.0", "## [1.0.0] - 2026-10-28")
    assert any("CHANGELOG.md" in error for error in verify_version.check("v2.0.0", project))


def test_repository_version_is_releasable() -> None:
    import tomllib

    version = tomllib.loads((SCRIPT.parents[2] / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    tag = f"v{version}".replace("rc", "-rc.")
    assert verify_version.check(tag, SCRIPT.parents[2]) == []
