"""AutoDock Vina molecular docking engine adapter.

Provides CPU-based docking execution, input validation, pose extraction and
provenance tracking using the official AutoDock Vina binary distribution.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from ....core.config import Settings, get_settings
from ....core.errors import ValidationError
from ....core.hashing import sha256_file
from ....workflow.registry import NodeContext
from ....workflow.table import Column, Table
from .prep import (
    LigandPreparationError,
    parse_vina_poses,
    pose_pdbqt_to_sdf,
    prepare_ligand_pdbqt,
    validate_receptor_pdbqt,
)

ADAPTER_ID = "science:autodock-vina"
ENGINE_VERSION = "1.2.5"
SCIENTIFIC_CAVEAT = (
    "AutoDock Vina docking scores are computational approximations of binding free energy. "
    "They are prioritisation and hypothesis-generation signals, not experimental proof of "
    "affinity, binding kinetics, selectivity or pharmacological efficacy."
)


class VinaConfig(BaseModel):
    """Configuration for AutoDock Vina molecular docking node."""

    receptor_path: str = Field(
        ...,
        description="Path to receptor PDBQT file, or relative path within project/workspace.",
    )
    center_x: float = Field(..., description="Binding box center X coordinate in Angstroms.")
    center_y: float = Field(..., description="Binding box center Y coordinate in Angstroms.")
    center_z: float = Field(..., description="Binding box center Z coordinate in Angstroms.")
    size_x: float = Field(
        default=20.0,
        ge=4.0,
        le=100.0,
        description="Binding box X dimension in Angstroms.",
    )
    size_y: float = Field(
        default=20.0,
        ge=4.0,
        le=100.0,
        description="Binding box Y dimension in Angstroms.",
    )
    size_z: float = Field(
        default=20.0,
        ge=4.0,
        le=100.0,
        description="Binding box Z dimension in Angstroms.",
    )
    exhaustiveness: int = Field(
        default=8,
        ge=1,
        le=64,
        description="Exhaustiveness of global search (higher = more thorough, proportional runtime).",
    )
    num_modes: int = Field(
        default=9,
        ge=1,
        le=20,
        description="Maximum number of binding modes to generate.",
    )
    energy_range: float = Field(
        default=3.0,
        ge=0.5,
        le=10.0,
        description="Maximum energy difference (kcal/mol) between best and worst pose displayed.",
    )
    seed: int = Field(
        default=42,
        description="Explicit random seed for reproducible docking runs.",
    )
    cpu_threads: int | None = Field(
        default=None,
        ge=1,
        le=128,
        description="Number of CPU threads to use (default: automatic from system settings).",
    )
    timeout_per_ligand: float = Field(
        default=180.0,
        ge=5.0,
        le=3600.0,
        description="Timeout ceiling per ligand in seconds.",
    )
    output_prefix: str = Field(
        default="docking",
        pattern=r"^[a-z][a-z0-9_]{0,31}$",
        description="Column name prefix for docking results.",
    )

    @field_validator("receptor_path")
    @classmethod
    def _validate_path_non_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("receptor_path cannot be empty.")
        return cleaned


def resolve_vina_binary(settings: Settings | None = None) -> Path | None:
    """Find the AutoDock Vina binary on this host.

    Order of resolution:
    1. Settings.vina_binary_path if configured and exists.
    2. HCS_VINA_BINARY environment variable if set.
    3. Project `bin/vina.exe` or `bin/vina` relative to current working directory or package root.
    4. PATH lookup for `vina` or `vina.exe`.
    """
    cfg = settings or get_settings()

    # 1. Configured path
    if hasattr(cfg, "vina_binary_path") and cfg.vina_binary_path:
        cand = Path(cfg.vina_binary_path)
        if cand.is_file() and os.access(cand, os.X_OK):
            return cand.resolve()

    # 2. Environment variable
    env_vina = os.environ.get("HCS_VINA_BINARY")
    if env_vina:
        cand = Path(env_vina)
        if cand.is_file() and os.access(cand, os.X_OK):
            return cand.resolve()

    # 3. Local repository / application bin directory
    repo_root = Path.cwd()
    for bin_name in ("vina.exe", "vina", "vina_1.2.5_win.exe", "vina_1.2.5_linux_x86_64"):
        local_cand = repo_root / "bin" / bin_name
        if local_cand.is_file():
            return local_cand.resolve()

    # 4. PATH lookup
    which_vina = shutil.which("vina") or shutil.which("vina.exe")
    if which_vina:
        return Path(which_vina).resolve()

    return None


def probe_vina(settings: Settings | None = None) -> dict[str, Any]:
    """Probe host for AutoDock Vina executable and report verified capability."""
    binary = resolve_vina_binary(settings)
    if binary is None:
        return {
            "id": ADAPTER_ID,
            "status": "not_configured",
            "available": False,
            "version": None,
            "binary_path": None,
            "detail": "AutoDock Vina binary was not found on PATH or under bin/.",
            "remediation": (
                "Place the official Vina executable in the bin/ directory or set HCS_VINA_BINARY environment variable."
            ),
            "backend": "cpu",
            "caveat": SCIENTIFIC_CAVEAT,
        }

    try:
        proc = subprocess.run(
            [str(binary), "--version"],
            capture_output=True,
            text=True,
            timeout=10.0,
            check=False,
        )
        output = f"{proc.stdout}\n{proc.stderr}".strip()
        version_match = re.search(r"AutoDock\s+Vina\s+v?([\d.]+)", output, re.IGNORECASE)
        detected_version = version_match.group(1) if version_match else ENGINE_VERSION

        return {
            "id": ADAPTER_ID,
            "status": "available",
            "available": True,
            "version": detected_version,
            "binary_path": str(binary),
            "detail": f"AutoDock Vina executable operational at {binary}",
            "backend": "cpu",
            "caveat": SCIENTIFIC_CAVEAT,
        }
    except Exception as exc:
        return {
            "id": ADAPTER_ID,
            "status": "unavailable",
            "available": False,
            "version": None,
            "binary_path": str(binary),
            "detail": f"Execution test failed: {type(exc).__name__}: {exc}",
            "remediation": "Verify executable permissions and architecture compatibility.",
            "backend": "cpu",
            "caveat": SCIENTIFIC_CAVEAT,
        }


class VinaAdapter:
    """Scientific adapter encapsulating AutoDock Vina CPU execution."""

    def __init__(self, binary_path: Path | None = None) -> None:
        self.binary_path = binary_path or resolve_vina_binary()

    def is_available(self) -> bool:
        return self.binary_path is not None and self.binary_path.is_file()

    def dock_single(
        self,
        *,
        receptor_pdbqt_path: Path,
        ligand_pdbqt_content: str,
        config: VinaConfig,
        work_dir: Path,
        ligand_id: str = "ligand",
    ) -> tuple[float | None, float | None, float | None, str | None, str | None]:
        """Dock a single prepared ligand against the receptor.

        Returns:
            (affinity_kcal_mol, rmsd_lb, rmsd_ub, poses_pdbqt_content, poses_sdf_content)
        """
        if self.binary_path is None:
            raise ValidationError(
                "AutoDock Vina binary is not configured.",
                details={"remediation": "Set HCS_VINA_BINARY or place vina executable in bin/."},
            )

        ligand_file = work_dir / f"{ligand_id}.pdbqt"
        ligand_file.write_text(ligand_pdbqt_content, encoding="utf-8")
        out_file = work_dir / f"{ligand_id}_poses.pdbqt"

        cpus = config.cpu_threads or 0
        cmd = [
            str(self.binary_path),
            "--receptor",
            str(receptor_pdbqt_path),
            "--ligand",
            str(ligand_file),
            "--center_x",
            str(config.center_x),
            "--center_y",
            str(config.center_y),
            "--center_z",
            str(config.center_z),
            "--size_x",
            str(config.size_x),
            "--size_y",
            str(config.size_y),
            "--size_z",
            str(config.size_z),
            "--exhaustiveness",
            str(config.exhaustiveness),
            "--num_modes",
            str(config.num_modes),
            "--energy_range",
            str(config.energy_range),
            "--seed",
            str(config.seed),
            "--cpu",
            str(cpus),
            "--out",
            str(out_file),
        ]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=config.timeout_per_ligand,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ValidationError(f"Docking timed out for {ligand_id} after {config.timeout_per_ligand}s.") from exc

        if proc.returncode != 0:
            err_msg = (proc.stderr or proc.stdout).strip()
            raise ValidationError(f"AutoDock Vina returned exit code {proc.returncode}: {err_msg[:400]}")

        if not out_file.is_file():
            return (None, None, None, None, None)

        out_content = out_file.read_text(encoding="utf-8", errors="replace")
        poses = parse_vina_poses(out_content)
        if not poses:
            return (None, None, None, out_content, None)

        best_pose = poses[0]
        sdf_content = pose_pdbqt_to_sdf(best_pose.pdbqt)
        return (best_pose.affinity, best_pose.rmsd_lb, best_pose.rmsd_ub, out_content, sdf_content)


def vina_docking_columns(prefix: str = "docking") -> list[Column]:
    """Columns produced by the AutoDock Vina docking node."""
    return [
        Column(
            f"{prefix}_affinity_kcal_mol",
            "Binding affinity",
            "number",
            unit="kcal/mol",
            direction="lower",
            method="AutoDock Vina empirical scoring",
            description="Estimated binding free energy of best docking mode (lower = more favorable).",
        ),
        Column(
            f"{prefix}_rmsd_lb",
            "Pose RMSD l.b.",
            "number",
            unit="Å",
            direction="lower",
            method="RMSD lower bound to best mode",
        ),
        Column(
            f"{prefix}_rmsd_ub",
            "Pose RMSD u.b.",
            "number",
            unit="Å",
            direction="lower",
            method="RMSD upper bound to best mode",
        ),
        Column(
            f"{prefix}_pose_artifact",
            "Docked pose artifact",
            "string",
            method="AutoDock Vina pose PDBQT/SDF",
            description="Relative path to docked 3D pose artifact.",
        ),
    ]


def run_vina_docking(table: Table, config: VinaConfig, ctx: NodeContext) -> Table:
    """Execute AutoDock Vina docking workflow step across table ligands."""
    table.require(["smiles"])

    adapter = VinaAdapter()
    if not adapter.is_available():
        raise ValidationError(
            "AutoDock Vina binary is not available on this host.",
            details={
                "adapter": ADAPTER_ID,
                "remediation": "Place the official Vina executable in bin/ or set HCS_VINA_BINARY.",
            },
        )

    # Locate and validate receptor
    receptor_path = Path(config.receptor_path)
    if not receptor_path.is_absolute():
        # Try relative to cwd or work_dir
        if (Path.cwd() / receptor_path).is_file():
            receptor_path = (Path.cwd() / receptor_path).resolve()
        elif (ctx.work_dir / receptor_path).is_file():
            receptor_path = (ctx.work_dir / receptor_path).resolve()
        else:
            raise ValidationError(f"Receptor file does not exist: {config.receptor_path}")

    receptor_meta = validate_receptor_pdbqt(receptor_path)
    receptor_sha256 = sha256_file(receptor_path)

    ctx.log(
        f"Receptor validated: {receptor_meta['atom_count']} atoms (SHA-256: {receptor_sha256[:12]}...).",
        level="info",
        data={"receptor_summary": receptor_meta},
    )
    for warning in receptor_meta.get("warnings", []):
        ctx.log(f"Receptor caveat: {warning}", level="warning")

    ctx.log(SCIENTIFIC_CAVEAT, level="info")

    columns = vina_docking_columns(config.output_prefix)
    affinities: list[float | None] = []
    rmsds_lb: list[float | None] = []
    rmsds_ub: list[float | None] = []
    artifact_paths: list[str | None] = []

    total = len(table.rows)
    prep_failures = 0
    dock_failures = 0

    with tempfile.TemporaryDirectory(prefix="vina_run_") as temp_dir:
        temp_path = Path(temp_dir)

        for idx, row in enumerate(table.rows, start=1):
            ctx.check_cancel()
            smiles = row.get("smiles")
            row_id = str(row.get("id") or f"mol_{idx}")

            if not smiles or not isinstance(smiles, str):
                prep_failures += 1
                affinities.append(None)
                rmsds_lb.append(None)
                rmsds_ub.append(None)
                artifact_paths.append(None)
                continue

            # 1. Ligand preparation
            try:
                ligand_pdbqt = prepare_ligand_pdbqt(smiles, seed=config.seed + idx)
            except LigandPreparationError as exc:
                prep_failures += 1
                ctx.log(f"Row {idx} ({row_id}) prep failed: {exc.message}", level="warning")
                affinities.append(None)
                rmsds_lb.append(None)
                rmsds_ub.append(None)
                artifact_paths.append(None)
                continue

            # 2. Docking execution
            try:
                aff, r_lb, r_ub, pose_pdbqt, pose_sdf = adapter.dock_single(
                    receptor_pdbqt_path=receptor_path,
                    ligand_pdbqt_content=ligand_pdbqt,
                    config=config,
                    work_dir=temp_path,
                    ligand_id=f"lig_{idx}",
                )
                affinities.append(aff)
                rmsds_lb.append(r_lb)
                rmsds_ub.append(r_ub)

                if pose_pdbqt:
                    art = ctx.write_artifact(
                        f"docking/{row_id}_poses.pdbqt",
                        pose_pdbqt,
                        "chemical/x-pdbqt",
                    )
                    artifact_paths.append(art.get("rel_path") or str(art.get("path", "")))
                    if pose_sdf:
                        ctx.write_artifact(
                            f"docking/{row_id}_best_pose.sdf",
                            pose_sdf,
                            "chemical/x-mdl-sdfile",
                        )
                else:
                    artifact_paths.append(None)
            except Exception as exc:
                dock_failures += 1
                ctx.log(f"Row {idx} ({row_id}) docking failed: {exc}", level="warning")
                affinities.append(None)
                rmsds_lb.append(None)
                rmsds_ub.append(None)
                artifact_paths.append(None)

            if idx % 10 == 0 or idx == total:
                ctx.report_progress(idx / total if total else None)

    result = table.copy()
    result.add_values(columns[0], affinities)
    result.add_values(columns[1], rmsds_lb)
    result.add_values(columns[2], rmsds_ub)
    result.add_values(columns[3], artifact_paths)

    if prep_failures or dock_failures:
        ctx.log(
            f"Docking completed with {prep_failures} ligand prep error(s) and {dock_failures} engine error(s).",
            level="warning",
        )
    else:
        ctx.log(f"Docking completed successfully for {total} compound(s).", level="info")

    ctx.report_progress(1.0)
    return result
