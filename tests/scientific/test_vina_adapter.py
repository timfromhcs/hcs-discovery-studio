"""Scientific tests and verification for AutoDock Vina docking adapter."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

import hcs_discovery.plugins.science.docking.vina as vina_module
from hcs_discovery.core.config import Settings
from hcs_discovery.core.errors import ValidationError
from hcs_discovery.plugins.science.docking.prep import (
    LigandPreparationError,
    ReceptorValidationError,
    parse_vina_poses,
    pose_pdbqt_to_sdf,
    prepare_ligand_pdbqt,
    validate_receptor_pdbqt,
)
from hcs_discovery.plugins.science.docking.vina import (
    ADAPTER_ID,
    SCIENTIFIC_CAVEAT,
    VinaAdapter,
    VinaConfig,
    probe_vina,
    resolve_receptor_path,
    run_vina_docking,
    vina_runtime_fingerprint,
)
from hcs_discovery.workflow.table import Column, Table

SAMPLE_RECEPTOR_PDBQT = """ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00 20.00    -0.350 N 
ATOM      2  CA  ALA A   1       1.458   0.000   0.000  1.00 20.00     0.100 C 
ATOM      3  C   ALA A   1       2.009   1.428   0.000  1.00 20.00     0.550 C 
ATOM      4  O   ALA A   1       1.246   2.392   0.000  1.00 20.00    -0.550 OA
ATOM      5  CB  ALA A   1       1.993  -0.758  -1.218  1.00 20.00     0.000 C 
ATOM      6  N   GLY A   2       3.328   1.545   0.000  1.00 20.00    -0.350 N 
ATOM      7  CA  GLY A   2       3.985   2.848   0.000  1.00 20.00     0.000 C 
ATOM      8  C   GLY A   2       5.495   2.730   0.000  1.00 20.00     0.550 C 
ATOM      9  O   GLY A   2       6.155   3.766   0.000  1.00 20.00    -0.550 OA
ATOM     10  HD1 ALA A   1      -0.450  -0.850   0.000  1.00 20.00     0.200 HD
TER      11      GLY A   2                                                      
"""

SAMPLE_VINA_OUTPUT = """MODEL 1
REMARK VINA RESULT:    -5.420      0.000      0.000
REMARK INTER + INTRA:          -5.420
REMARK INTER:                  -5.420
REMARK INTRA:                   0.000
REMARK UNBOUND:                 0.000
ROOT
ATOM      1  C1  LIG     1       2.100   1.200   0.100  1.00  0.00    +0.050 C 
ATOM      2  O2  LIG     1       3.100   1.800   0.200  1.00  0.00    -0.400 OA
ENDROOT
TORSDOF 0
ENDMDL
MODEL 2
REMARK VINA RESULT:    -4.810      1.250      2.100
ROOT
ATOM      1  C1  LIG     1       2.300   1.400   0.300  1.00  0.00    +0.050 C 
ATOM      2  O2  LIG     1       3.300   2.000   0.400  1.00  0.00    -0.400 OA
ENDROOT
TORSDOF 0
ENDMDL
"""


class DummyContext:
    def __init__(self, work_dir: Path) -> None:
        self.work_dir = work_dir
        self.run_id = "test_run"
        self.node_id = "test_node"
        self.engine_versions = {}
        self.logs: list[tuple[str, str]] = []
        self.progress: list[float | None] = []
        self.artifacts: dict[str, str] = {}

    def emit(self, level: str, message: str, data: dict[str, Any] | None, kind: str) -> None:
        self.logs.append((level, message))

    def log(self, message: str, *, level: str = "info", data: dict[str, Any] | None = None) -> None:
        self.logs.append((level, message))

    def report_progress(self, frac: float | None) -> None:
        self.progress.append(frac)

    def check_cancel(self) -> None:
        pass

    def write_artifact(self, rel_path: str, content: str | bytes, media_type: str) -> dict[str, Any]:
        text = content if isinstance(content, str) else content.decode("utf-8", errors="replace")
        self.artifacts[rel_path] = text
        return {"rel_path": rel_path, "bytes": len(text)}


def test_prepare_ligand_pdbqt_valid() -> None:
    # Test with ethanol
    pdbqt = prepare_ligand_pdbqt("CCO", seed=42)
    assert "ROOT" in pdbqt
    assert "ENDROOT" in pdbqt
    assert "TORSDOF" in pdbqt
    assert "ATOM" in pdbqt
    assert "OA" in pdbqt  # oxygen acceptor
    assert "HD" in pdbqt  # polar H on hydroxyl


def test_prepare_ligand_pdbqt_invalid() -> None:
    with pytest.raises(LigandPreparationError, match="Cannot parse"):
        prepare_ligand_pdbqt("INVALID_NOT_A_SMILES")


def test_validate_receptor_pdbqt() -> None:
    meta = validate_receptor_pdbqt(SAMPLE_RECEPTOR_PDBQT)
    assert meta["atom_count"] == 10
    assert meta["has_polar_h"] is True
    assert "bounding_box" in meta
    center = meta["bounding_box"]["center"]
    assert isinstance(center[0], float)

    # Empty receptor should raise
    with pytest.raises(ReceptorValidationError, match="contains no ATOM"):
        validate_receptor_pdbqt("REMARK empty file\n")


def test_parse_vina_poses() -> None:
    poses = parse_vina_poses(SAMPLE_VINA_OUTPUT)
    assert len(poses) == 2
    assert poses[0].mode == 1
    assert poses[0].affinity == -5.420
    assert poses[0].rmsd_lb == 0.0
    assert poses[1].mode == 2
    assert poses[1].affinity == -4.810
    assert poses[1].rmsd_lb == 1.250


def test_pose_pdbqt_to_sdf() -> None:
    poses = parse_vina_poses(SAMPLE_VINA_OUTPUT)
    sdf = pose_pdbqt_to_sdf(poses[0].pdbqt)
    assert "$$$$" in sdf
    assert "VINA_AFFINITY_KCAL_MOL" in sdf
    assert "-5.420" in sdf


def test_probe_vina() -> None:
    probe = probe_vina()
    assert probe["id"] == ADAPTER_ID
    assert probe["backend"] == "cpu"
    assert SCIENTIFIC_CAVEAT in probe["caveat"]
    # If binary exists, status is available
    if probe["available"]:
        assert probe["status"] == "available"
        assert probe["version"] is not None


def _skip_or_fail(reason: str) -> None:
    """Skip a live test without Vina, except in the CI science gate, where a skip would hide a broken setup."""
    if os.environ.get("HCS_REQUIRE_VINA") == "1":
        pytest.fail(f"HCS_REQUIRE_VINA=1 but {reason}")
    pytest.skip(reason)


@pytest.mark.scientific
def test_vina_real_docking_smoke(tmp_path: Path) -> None:
    adapter = VinaAdapter()
    if not adapter.is_available():
        _skip_or_fail("Vina binary not found on host; skipping live docking execution test.")

    receptor_file = tmp_path / "receptor.pdbqt"
    receptor_file.write_text(SAMPLE_RECEPTOR_PDBQT, encoding="utf-8")

    ligand_pdbqt = prepare_ligand_pdbqt("CCO", seed=42)

    config = VinaConfig(
        receptor_path=str(receptor_file),
        center_x=2.5,
        center_y=1.5,
        center_z=0.0,
        size_x=15.0,
        size_y=15.0,
        size_z=15.0,
        exhaustiveness=1,
        num_modes=2,
        seed=42,
    )

    affinity, r_lb, _r_ub, pose_pdbqt, pose_sdf = adapter.dock_single(
        receptor_pdbqt_path=receptor_file,
        ligand_pdbqt_content=ligand_pdbqt,
        config=config,
        work_dir=tmp_path,
        ligand_id="test_ethanol",
    )

    assert affinity is not None
    assert isinstance(affinity, float)
    assert affinity < 0.0  # Favorable or negative binding score
    assert r_lb == 0.0
    assert pose_pdbqt is not None
    assert "REMARK VINA RESULT" in pose_pdbqt
    assert pose_sdf is not None
    assert "$$$$" in pose_sdf


def _fake_vina(tmp_path: Path, *, output: str, exit_code: int = 0) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        path = tmp_path / "fake_vina.bat"
        lines = ["@echo off", f"echo {output}"]
        if exit_code:
            lines.append(f"exit /b {exit_code}")
        path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    else:
        path = tmp_path / "fake_vina"
        path.write_text(f"#!/bin/sh\necho '{output}'\nexit {exit_code}\n", encoding="utf-8")
        path.chmod(0o755)
    return path


def test_probe_vina_requires_successful_version_output(tmp_path: Path) -> None:
    good = _fake_vina(tmp_path, output="AutoDock Vina v9.9.9")
    probe = probe_vina(binary=good)
    assert probe["available"] is True
    assert probe["status"] == "available"
    assert probe["version"] == "9.9.9"

    failing = _fake_vina(tmp_path / "failing", output="boom", exit_code=7)
    failed = probe_vina(binary=failing)
    assert failed["available"] is False
    assert failed["status"] == "unavailable"
    assert failed["version"] is None
    assert "code 7" in failed["detail"]


def test_probe_vina_rejects_unrecognised_output(tmp_path: Path) -> None:
    fake = _fake_vina(tmp_path, output="not actually vina")
    probe = probe_vina(binary=fake)
    assert probe["available"] is False
    assert probe["version"] is None
    assert "did not report" in probe["detail"]
    assert VinaAdapter(fake).is_available() is False


def test_vina_node_records_per_ligand_status_and_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    class FakeAdapter:
        def is_available(self) -> bool:
            return True

        def dock_single(self, *, ligand_id: str, **_kwargs: Any):
            if ligand_id == "lig_3":
                raise ValidationError("engine crashed for this ligand")
            return (-5.0, 0.0, 0.0, SAMPLE_VINA_OUTPUT, None)

    monkeypatch.setattr(vina_module, "VinaAdapter", lambda *_args, **_kwargs: FakeAdapter())

    (settings.receptors_dir / "receptor.pdbqt").write_text(SAMPLE_RECEPTOR_PDBQT, encoding="utf-8")
    config = VinaConfig(
        receptor_path="receptor.pdbqt",
        center_x=2.5,
        center_y=1.5,
        center_z=0.0,
        size_x=12.0,
        size_y=12.0,
        size_z=12.0,
        exhaustiveness=1,
        num_modes=1,
        seed=42,
        output_prefix="dock",
    )
    table = Table(
        columns=[Column("smiles", "SMILES", "string"), Column("id", "ID", "string")],
        rows=[
            {"smiles": "CCO", "id": "ethanol"},
            {"smiles": "INVALID_SMILES", "id": "bad_mol"},
            {"smiles": "CC", "id": "ethane"},
        ],
    )
    result = run_vina_docking(table, config, DummyContext(tmp_path))  # type: ignore[arg-type]

    assert [row["dock_status"] for row in result.rows] == [
        "docked",
        "ligand_preparation_failed",
        "docking_failed",
    ]
    assert result.rows[0]["dock_error"] is None
    assert "Cannot parse" in result.rows[1]["dock_error"]
    assert result.rows[2]["dock_error"] == "engine crashed for this ligand"


def test_vina_workflow_node(tmp_path: Path, settings: Settings) -> None:
    adapter = VinaAdapter()
    if not adapter.is_available():
        _skip_or_fail("Vina binary not found on host; skipping workflow node live test.")

    (settings.receptors_dir / "receptor.pdbqt").write_text(SAMPLE_RECEPTOR_PDBQT, encoding="utf-8")

    config = VinaConfig(
        receptor_path="receptor.pdbqt",
        center_x=2.5,
        center_y=1.5,
        center_z=0.0,
        size_x=12.0,
        size_y=12.0,
        size_z=12.0,
        exhaustiveness=1,
        num_modes=1,
        seed=42,
        output_prefix="dock",
    )

    table = Table(
        columns=[Column("smiles", "SMILES", "string"), Column("id", "ID", "string")],
        rows=[
            {"smiles": "CCO", "id": "ethanol"},
            {"smiles": "INVALID_SMILES", "id": "bad_mol"},
        ],
    )

    ctx = DummyContext(tmp_path)
    # Cast to NodeContext protocol
    result = run_vina_docking(table, config, ctx)  # type: ignore[arg-type]

    assert len(result.rows) == 2
    assert result.has_column("dock_affinity_kcal_mol")
    # Row 1 (ethanol) docked successfully
    assert result.rows[0]["dock_affinity_kcal_mol"] is not None
    assert result.rows[0]["dock_pose_artifact"] is not None
    # Row 2 (invalid) recorded None without throwing unhandled exception
    assert result.rows[1]["dock_affinity_kcal_mol"] is None
    # Pose artifact saved
    assert any("docking/ethanol_poses.pdbqt" in k for k in ctx.artifacts)


def _receptor_config(path: str) -> VinaConfig:
    return VinaConfig(
        receptor_path=path,
        center_x=0.0,
        center_y=0.0,
        center_z=0.0,
        size_x=10.0,
        size_y=10.0,
        size_z=10.0,
    )


def test_receptor_paths_are_confined_to_the_receptor_directory(tmp_path: Path, settings: Settings) -> None:
    inside = settings.receptors_dir / "target.pdbqt"
    inside.write_text(SAMPLE_RECEPTOR_PDBQT, encoding="utf-8")
    outside = tmp_path / "elsewhere.pdbqt"
    outside.write_text(SAMPLE_RECEPTOR_PDBQT, encoding="utf-8")

    assert resolve_receptor_path("target.pdbqt") == inside.resolve()
    assert resolve_receptor_path(str(inside)) == inside.resolve()
    for rejected in (str(outside), "../elsewhere.pdbqt", "missing.pdbqt"):
        with pytest.raises(ValidationError):
            resolve_receptor_path(rejected)

    trusted = settings.model_copy(update={"allow_external_receptor_paths": True})
    assert resolve_receptor_path(str(outside), trusted) == outside.resolve()
    with pytest.raises(ValidationError):
        resolve_receptor_path("../elsewhere.pdbqt", trusted)


def test_runtime_fingerprint_tracks_receptor_content_and_vina_version(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    receptor = settings.receptors_dir / "target.pdbqt"
    receptor.write_text(SAMPLE_RECEPTOR_PDBQT, encoding="utf-8")
    config = _receptor_config("target.pdbqt")
    version = {"value": "1.2.5"}
    monkeypatch.setattr(vina_module, "probe_vina", lambda *_a, **_k: {"version": version["value"]})

    baseline = vina_runtime_fingerprint(config)
    assert baseline["autodock_vina"] == "1.2.5"
    assert vina_runtime_fingerprint(config) == baseline

    receptor.write_text(SAMPLE_RECEPTOR_PDBQT + "REMARK changed\n", encoding="utf-8")
    changed_receptor = vina_runtime_fingerprint(config)
    assert changed_receptor["receptor_sha256"] != baseline["receptor_sha256"]

    version["value"] = "1.2.6"
    assert vina_runtime_fingerprint(config)["autodock_vina"] == "1.2.6"

    version["value"] = None
    missing = vina_runtime_fingerprint(_receptor_config("absent.pdbqt"))
    assert missing == {"autodock_vina": "unavailable", "receptor_sha256": "unresolved"}
