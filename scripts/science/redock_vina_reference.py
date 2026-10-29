"""Redock imatinib into Abl kinase (PDB 1IEP) with AutoDock Vina and measure pose recovery.

    python scripts/science/redock_vina_reference.py --vina bin/vina.exe
    python scripts/science/redock_vina_reference.py --vina ./vina --out-dir "$RUNNER_TEMP/redock" --gate

The fixture under ``tests/fixtures/docking/1iep`` comes from the official AutoDock
Vina example (see its ``SOURCE.md``). Two ligand preparations are docked with the
same receptor, box and settings:

- ``hcs``: the product path. The ligand starts from the SMILES of the crystal
  ligand (no crystal coordinates), is prepared with HCS Discovery Studio's own
  ``prepare_ligand`` and docked through ``VinaAdapter``; the top pose goes
  through the same PDBQT-to-SDF conversion the workflow node writes.
- ``vina_example``: the Vina authors' own ligand PDBQT, a control for the
  receptor, box and binary.

Pose error is the symmetry-aware heavy-atom RMSD between a docked pose and the
crystal ligand, computed in place without superposition (RDKit ``CalcRMS``).

Acceptance criterion, fixed before the first run and not tuned afterwards: for
each arm, the top-ranked pose of every seed must be within 2.0 Å of the crystal
pose. 2.0 Å is the conventional pose-recovery cut-off used, for example, by the
CASF-2016 docking-power test (Su et al., J. Chem. Inf. Model. 2019, 59, 895–913).
One complex is a regression and sanity check for the docking path. It is not a
docking accuracy benchmark and says nothing about affinity ranking.

``--gate`` exits non-zero when the criterion fails. Without ``--gate`` the
script writes the report and always exits zero after a completed run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import rdkit
from rdkit import Chem
from rdkit.Chem import rdMolAlign

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from hcs_discovery.plugins.science.docking.prep import (  # noqa: E402
    PREPARATION_METHOD,
    parse_vina_poses,
    pose_pdbqt_to_sdf,
    prepare_ligand,
)
from hcs_discovery.plugins.science.docking.vina import VinaAdapter, VinaConfig, probe_vina  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "docking" / "1iep"
FIXTURE_SHA256 = {
    "receptor.pdbqt": "f13cf3b36f61d87c3b58983e0b8ecf1c3456a685eb86dfe9ccfb139c7bdc2586",
    "crystal_ligand.sdf": "051b8742c32adc05c07fb486a4e7c9327f84e131cee33ac4e6a568d07553eb38",
    "reference_ligand.pdbqt": "15fb35648d8c18c70317842f3a0631b73a19429c710a037ab07310084d579bb8",
    "box.txt": "3dff08200b5b9c2ca0932c832c9dffc5823b39caec6c92f76be5f7c5ea49d8de",
}
RMSD_THRESHOLD = 2.0
DEFAULT_SEEDS = (1, 2, 3, 4, 5)
EXHAUSTIVENESS = 8
NUM_MODES = 9
CPU_THREADS = 4
REPORT_STEM = "vina-redocking-1iep"


def _verify_fixture() -> None:
    for name, expected in FIXTURE_SHA256.items():
        actual = hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit(f"fixture {name} has SHA-256 {actual}, expected {expected}; refusing to run")


def _box() -> dict[str, float]:
    values: dict[str, float] = {}
    for line in (FIXTURE / "box.txt").read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        if value.strip():
            values[key.strip()] = float(value)
    return values


def _crystal() -> Chem.Mol:
    mol = Chem.MolFromMolFile(str(FIXTURE / "crystal_ligand.sdf"), removeHs=False)
    if mol is None:
        raise SystemExit("crystal ligand could not be parsed")
    return Chem.RemoveHs(mol)


def _pose_rmsds(poses_pdbqt: str, crystal: Chem.Mol) -> list[dict[str, float]]:
    """RMSD of every docked mode, read back through the SDF the workflow node writes."""
    results = []
    for pose in parse_vina_poses(poses_pdbqt):
        sdf = pose_pdbqt_to_sdf(pose.pdbqt)
        mol = Chem.MolFromMolBlock(sdf.split("$$$$")[0], removeHs=False)
        if mol is None:
            raise RuntimeError(f"mode {pose.mode}: docked pose SDF could not be parsed")
        probe = Chem.RemoveHs(mol)
        if probe.GetNumAtoms() != crystal.GetNumAtoms():
            raise RuntimeError(
                f"mode {pose.mode}: pose has {probe.GetNumAtoms()} heavy atoms, crystal has {crystal.GetNumAtoms()}"
            )
        rmsd = rdMolAlign.CalcRMS(probe, crystal)
        results.append({"mode": pose.mode, "affinity_kcal_mol": pose.affinity, "rmsd_angstrom": round(rmsd, 3)})
    return results


def _run(vina: Path, seeds: list[int], work: Path) -> dict[str, Any]:
    probe = probe_vina(binary=vina)
    if not probe["available"]:
        raise SystemExit(f"AutoDock Vina is not usable: {probe['detail']}")
    adapter = VinaAdapter(binary_path=vina)
    crystal = _crystal()
    smiles = Chem.MolToSmiles(crystal)
    box = _box()
    receptor = FIXTURE / "receptor.pdbqt"
    reference_pdbqt = (FIXTURE / "reference_ligand.pdbqt").read_text(encoding="utf-8")

    arms: dict[str, list[dict[str, Any]]] = {"hcs": [], "vina_example": []}
    for seed in seeds:
        config = VinaConfig(
            receptor_path=str(receptor),
            seed=seed,
            exhaustiveness=EXHAUSTIVENESS,
            num_modes=NUM_MODES,
            cpu_threads=CPU_THREADS,
            timeout_per_ligand=900.0,
            **box,
        )
        prepared = prepare_ligand(smiles, seed=seed)
        for arm, ligand in (("hcs", prepared.pdbqt), ("vina_example", reference_pdbqt)):
            started = time.perf_counter()
            _aff, _lb, _ub, poses, _sdf = adapter.dock_single(
                receptor_pdbqt_path=receptor,
                ligand_pdbqt_content=ligand,
                config=config,
                work_dir=work,
                ligand_id=f"{arm}_{seed}",
            )
            elapsed = time.perf_counter() - started
            modes = _pose_rmsds(poses or "", crystal)
            if not modes:
                raise RuntimeError(f"{arm} seed {seed}: Vina returned no pose")
            entry = {
                "seed": seed,
                "top_pose_rmsd_angstrom": modes[0]["rmsd_angstrom"],
                "top_pose_affinity_kcal_mol": modes[0]["affinity_kcal_mol"],
                "best_mode_rmsd_angstrom": min(m["rmsd_angstrom"] for m in modes),
                "seconds": round(elapsed, 1),
                "modes": modes,
            }
            if arm == "hcs":
                entry["preparation_warnings"] = prepared.warnings
                entry["torsions"] = prepared.torsions
            arms[arm].append(entry)
            print(
                f"{arm:13s} seed {seed}: top pose {entry['top_pose_rmsd_angstrom']:.2f} A, "
                f"{entry['top_pose_affinity_kcal_mol']:.2f} kcal/mol ({elapsed:.0f} s)",
                flush=True,
            )

    summary = {}
    for arm, entries in arms.items():
        passed = sum(e["top_pose_rmsd_angstrom"] <= RMSD_THRESHOLD for e in entries)
        summary[arm] = {
            "seeds": len(entries),
            "top_pose_within_threshold": passed,
            "max_top_pose_rmsd_angstrom": max(e["top_pose_rmsd_angstrom"] for e in entries),
            "passed": passed == len(entries),
        }

    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "complex": "PDB 1IEP, imatinib / Abl kinase",
        "fixture": {
            "source": "https://github.com/ccsb-scripps/AutoDock-Vina/tree/bb64e5e26b520569a86360d69248069b5e665b3f/example/basic_docking",
            "license": "Apache-2.0",
            "sha256": FIXTURE_SHA256,
        },
        "ligand_smiles": smiles,
        "box": box,
        "settings": {"exhaustiveness": EXHAUSTIVENESS, "num_modes": NUM_MODES, "cpu": CPU_THREADS, "seeds": seeds},
        "hcs_preparation_method": PREPARATION_METHOD,
        "rmsd": "symmetry-aware heavy-atom RMSD to the crystal ligand, in place, no superposition (RDKit CalcRMS)",
        "criterion": f"top-ranked pose RMSD <= {RMSD_THRESHOLD} Å for every seed, per arm",
        "environment": {
            "autodock_vina": probe["version"],
            "vina_binary_sha256": hashlib.sha256(vina.read_bytes()).hexdigest(),
            "rdkit": rdkit.__version__,
            "python": platform.python_version(),
            "platform": f"{platform.system()} {platform.release()} {platform.machine()}",
        },
        "summary": summary,
        "passed": all(s["passed"] for s in summary.values()),
        "arms": arms,
    }


def _render_markdown(report: dict[str, Any]) -> str:
    env = report["environment"]
    lines = [
        "# AutoDock Vina redocking check: 1IEP (imatinib / Abl)",
        "",
        "Generated by `scripts/science/redock_vina_reference.py`. This is a single-complex",
        "regression and sanity check of the docking path, not a docking accuracy benchmark.",
        "It says nothing about affinity ranking, other targets or prospective docking.",
        "",
        "## Setup",
        "",
        f"- Fixture: official AutoDock Vina example `basic_docking` ({report['fixture']['license']}), "
        "see `tests/fixtures/docking/1iep/SOURCE.md` for files and SHA-256 hashes.",
        f"- Box: centre ({report['box']['center_x']}, {report['box']['center_y']}, {report['box']['center_z']}) A, "
        f"size {report['box']['size_x']} × {report['box']['size_y']} × {report['box']['size_z']} Å.",
        f"- Vina settings: exhaustiveness {report['settings']['exhaustiveness']}, "
        f"{report['settings']['num_modes']} modes, {report['settings']['cpu']} CPU threads, "
        f"seeds {', '.join(str(s) for s in report['settings']['seeds'])}.",
        f"- `hcs` arm: ligand built from SMILES `{report['ligand_smiles']}` without crystal coordinates, "
        f"prepared with `{report['hcs_preparation_method']}`, docked through `VinaAdapter`; poses read back "
        "through the SDF the workflow node writes.",
        "- `vina_example` arm: the Vina authors' ligand PDBQT (control for receptor, box and binary).",
        f"- Pose error: {report['rmsd']}.",
        f"- Acceptance criterion, fixed before the first run: {report['criterion']}.",
        "",
        "## Environment",
        "",
        f"- AutoDock Vina {env['autodock_vina']} (binary SHA-256 `{env['vina_binary_sha256']}`)",
        f"- RDKit {env['rdkit']}, Python {env['python']}, {env['platform']}",
        f"- Generated {report['generated_at']}",
        "",
        "## Results",
        "",
        "| Arm | Seed | Top pose RMSD (Å) | Top pose score (kcal/mol) | Best of modes RMSD (Å) | Time (s) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for arm, entries in report["arms"].items():
        for e in entries:
            lines.append(
                f"| {arm} | {e['seed']} | {e['top_pose_rmsd_angstrom']:.2f} | "
                f"{e['top_pose_affinity_kcal_mol']:.2f} | {e['best_mode_rmsd_angstrom']:.2f} | {e['seconds']:.0f} |"
            )
    lines += ["", "| Arm | Seeds within 2.0 Å | Worst top pose (Å) | Verdict |", "|---|---:|---:|---|"]
    for arm, s in report["summary"].items():
        verdict = "pass" if s["passed"] else "**fail**"
        within = f"{s['top_pose_within_threshold']}/{s['seeds']}"
        lines.append(f"| {arm} | {within} | {s['max_top_pose_rmsd_angstrom']:.2f} | {verdict} |")
    lines += [
        "",
        f"Overall: **{'pass' if report['passed'] else 'fail'}**.",
        "",
        "## Limitations",
        "",
        "- One complex, one receptor conformation, redocking into the holo structure. Cross-docking",
        "  and apo structures are harder and are not tested.",
        "- The receptor was prepared by the Vina authors; HCS Discovery Studio does not prepare receptors.",
        "- Vina scores are empirical estimates, not binding free energies, and are not compared with",
        "  measured affinities here.",
        "- Results can differ slightly between Vina builds and operating systems; the CI job reruns",
        "  the check on Linux with the official Linux binary.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--vina", type=Path, required=True, help="AutoDock Vina executable")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "docs" / "validation", help="report directory")
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    parser.add_argument("--gate", action="store_true", help="exit non-zero if the acceptance criterion fails")
    args = parser.parse_args(argv)

    _verify_fixture()
    with tempfile.TemporaryDirectory(prefix="hcs_redock_") as work:
        report = _run(args.vina.resolve(), args.seeds, Path(work))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / f"{REPORT_STEM}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (args.out_dir / f"{REPORT_STEM}.md").write_text(_render_markdown(report), encoding="utf-8")
    print(f"overall: {'pass' if report['passed'] else 'FAIL'}; report written to {args.out_dir}")
    if args.gate and not report["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
