"""Reproduce the published Delaney ESOL equation on the Delaney set and report it.

    uv run python scripts/science/validate_esol_delaney.py
    uv run python scripts/science/validate_esol_delaney.py --check

The model ships fixed coefficients from Delaney (2004); nothing is fitted here. The
script therefore reports a *reproduction*, not a trained score: the same published
equation, the same dataset, with the descriptors RDKit actually computes. It also
reports a held-out scaffold split and a constant baseline, because a full-set number
alone hides how much of the fit is memorised by the coefficients.

`--check` re-computes the numbers and fails when they differ from the committed report,
so a dependency upgrade cannot silently change the published metrics.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path
from typing import Any

from rdkit import Chem

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET = REPO_ROOT / "tests" / "fixtures" / "esol" / "delaney-processed.csv"
REPORT_MD = REPO_ROOT / "docs" / "validation" / "esol-delaney.md"
REPORT_JSON = REPO_ROOT / "docs" / "validation" / "esol-delaney.json"
SCHEMA = "hcs.esol-delaney.v1"
EXPECTED_SHA256 = "8c06a76f0c6487d29ab0f903e6a7a7139f189ab3c1178f159c8be8964602f189"
MEASURED_COLUMN = "measured log solubility in mols per litre"


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            smiles = (row.get("smiles") or "").strip()
            measured = row.get(MEASURED_COLUMN)
            if not smiles or measured in (None, ""):
                continue
            rows.append(
                {
                    "id": row.get("Compound ID") or "",
                    "smiles": smiles,
                    "measured": float(str(measured)),
                }
            )
    return rows


def _metrics(predictions: list[float], measured: list[float]) -> dict[str, float]:
    errors = [prediction - truth for prediction, truth in zip(predictions, measured, strict=True)]
    mean_truth = statistics.fmean(measured)
    ss_res = sum(error**2 for error in errors)
    ss_tot = sum((truth - mean_truth) ** 2 for truth in measured)
    return {
        "n": float(len(errors)),
        "rmse": math.sqrt(ss_res / len(errors)),
        "mae": statistics.fmean(abs(error) for error in errors),
        "r2": 1.0 - ss_res / ss_tot if ss_tot else 0.0,
        "mean_error": statistics.fmean(errors),
        "baseline_rmse": math.sqrt(ss_tot / len(measured)),
        "within_0_5": sum(1 for error in errors if abs(error) <= 0.5) / len(errors),
        "within_1_0": sum(1 for error in errors if abs(error) <= 1.0) / len(errors),
        "within_10x": sum(1 for error in errors if abs(error) <= 1.0) / len(errors),
        "max_abs_error": max(abs(error) for error in errors),
    }


def _bootstrap_rmse_ci(
    predictions: list[float], measured: list[float], *, seed: int = 7, rounds: int = 2000
) -> list[float]:
    rng = random.Random(seed)
    n = len(predictions)
    values: list[float] = []
    for _ in range(rounds):
        indexes = [rng.randrange(n) for _ in range(n)]
        squared = [(predictions[i] - measured[i]) ** 2 for i in indexes]
        values.append(math.sqrt(statistics.fmean(squared)))
    values.sort()
    return [values[int(0.025 * rounds)], values[int(0.975 * rounds) - 1]]


def run(path: Path = DATASET) -> dict[str, Any]:
    from hcs_discovery.plugins.science.properties.models import ESOLSolubilityModel
    from hcs_discovery.plugins.science.properties.scaffold import scaffold_split

    digest = _sha256(path)
    if digest != EXPECTED_SHA256:
        raise SystemExit(
            f"Dataset SHA-256 is {digest}, expected {EXPECTED_SHA256}. Refusing to report on a changed file."
        )
    rows = _load_rows(path)
    model = ESOLSolubilityModel()
    predictions: list[float] = []
    measured: list[float] = []
    rejected: list[dict[str, str]] = []
    for row in rows:
        mol = Chem.MolFromSmiles(row["smiles"])
        if mol is None:
            rejected.append({"id": row["id"], "reason": "unparseable SMILES"})
            continue
        value, _uncertainty, _in_domain, _warning = model.predict(mol)
        if value is None:
            rejected.append({"id": row["id"], "reason": "model returned no value"})
            continue
        predictions.append(value)
        measured.append(row["measured"])

    full = _metrics(predictions, measured)
    full["rmse_ci95"] = _bootstrap_rmse_ci(predictions, measured)

    # Held-out scaffold split. The coefficients are not re-fitted, so this measures how
    # the published equation transfers to unseen scaffolds, not a trained model.
    train, test = scaffold_split(
        [{"smiles": row["smiles"], "measured": row["measured"], "id": row["id"]} for row in rows]
    )
    test_predictions: list[float] = []
    test_measured: list[float] = []
    for row in test:
        mol = Chem.MolFromSmiles(row["smiles"])
        if mol is None:
            continue
        value, _u, _d, _w = model.predict(mol)
        if value is None:
            continue
        test_predictions.append(value)
        test_measured.append(float(row["measured"]))
    held_out = _metrics(test_predictions, test_measured)
    held_out["rmse_ci95"] = _bootstrap_rmse_ci(test_predictions, test_measured)
    held_out["n_train"] = float(len(train))

    return {
        "schema": SCHEMA,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
        "dataset": {
            "path": "tests/fixtures/esol/delaney-processed.csv",
            "sha256": digest,
            "rows": len(rows),
            "used": len(predictions),
            "rejected": rejected,
            "citation": (
                "Delaney, J. S. (2004). ESOL: estimating aqueous solubility directly from molecular "
                "structure. J. Chem. Inf. Comput. Sci. 44(3), 1000-1005. Distribution: MoleculeNet "
                "(deepchem) delaney-processed.csv."
            ),
        },
        "model": {
            "id": "esol_solubility",
            "version": model.metadata.version,
            "coefficients": {
                "intercept": model.INTERCEPT,
                "clogp": model.COEF_CLOGP,
                "mw": model.COEF_MW,
                "rotatable_bonds": model.COEF_RB,
                "aromatic_proportion": model.COEF_AP,
            },
            "weights_sha256": model.metadata.weights_sha256,
        },
        "full_set": full,
        "held_out_scaffold_split": held_out,
        "split": {"train_ratio": 0.8, "seed": 42, "strategy": "Bemis-Murcko scaffolds"},
        "status": "reproduced",
    }


def render(report: dict[str, Any]) -> str:
    full = report["full_set"]
    held = report["held_out_scaffold_split"]
    rejected = report["dataset"]["rejected"]
    coefficients = report["model"]["coefficients"]
    equation = (
        f"logS = {coefficients['intercept']:.2f} "
        f"- {abs(coefficients['clogp']):.2f}·cLogP "
        f"- {abs(coefficients['mw']):.4f}·MW "
        f"+ {coefficients['rotatable_bonds']:.3f}·RB "
        f"- {abs(coefficients['aromatic_proportion']):.2f}·AP"
    )

    def row(label: str, data: dict[str, Any]) -> str:
        return (
            f"| {label} | {int(data['n'])} | {data['rmse']:.3f} | "
            f"[{data['rmse_ci95'][0]:.3f}, {data['rmse_ci95'][1]:.3f}] | {data['mae']:.3f} | "
            f"{data['r2']:.3f} | {data['baseline_rmse']:.3f} |"
        )

    return f"""# ESOL on the Delaney set — reproduction, not a new model

Generated by `uv run python scripts/science/{Path(__file__).name}`.
Do not edit by hand: re-run the script.

| Item | Value |
|---|---|
| Date | {report["generated_at"]} |
| Dataset | `{report["dataset"]["path"]}` |
| SHA-256 | `{report["dataset"]["sha256"]}` |
| Rows | {report["dataset"]["rows"]} (used {report["dataset"]["used"]}, rejected {len(rejected)}) |
| Equation | `{equation}` || Status | **{report["status"]}** |

## Metrics (log10 mol/L)

| Set | n | RMSE | RMSE 95 % bootstrap CI | MAE | R² | Constant-baseline RMSE |
|---|---|---|---|---|---|---|
{row("Full Delaney set", full)}
{row("Held-out scaffold split (20 %)", held)}

The constant baseline predicts the mean of the evaluated set. On the held-out split the
model is compared against the mean of that split, not of the full set.

## Error distribution (full set)

| Within | Share |
|---|---|
| ±0.5 log units (≈3×) | {full["within_0_5"] * 100:.1f} % |
| ±1.0 log unit (10×) | {full["within_1_0"] * 100:.1f} % |
| Mean signed error | {full["mean_error"]:+.3f} |
| Largest absolute error | {full["max_abs_error"]:.2f} |

## What this establishes, and what it does not

- **This is a reproduction of a published equation.** The coefficients are Delaney's,
  the descriptors are RDKit's implementation of the same four quantities, and the
  dataset is the 1,128-molecule set distributed with MoleculeNet. It is not a newly
  trained model and it does not beat the published baseline.
- **Descriptor substitution is a real caveat.** Delaney used CLogP; this
  implementation uses RDKit Crippen cLogP. The two are correlated but not identical,
  and that difference is part of the residual error.
- **The held-out split is honest about the coefficients.** Because nothing is fitted
  here, the split does not change the model; it checks transfer to unseen scaffolds.
  It is not a train/test protocol for a learned model.
- **The earlier 45-molecule challenge (R² 0.07) is a stress set, not this benchmark.**
  It is small, narrow and drug-like; the full Delaney set spans a much wider
  solubility range, which is why R² is far higher here. Both reports are kept so the
  weak case is not hidden.
- **No scientific claim beyond solubility.** ESOL predicts intrinsic solubility of the
  neutral form; it does not model polymorphism, formulation, pH-dependent solubility
  or kinetic effects, and it is not a safety or efficacy signal.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--check", action="store_true", help="Fail when the report would change.")
    args = parser.parse_args(argv)
    report = run(args.dataset)
    if args.check:
        if not REPORT_JSON.exists():
            print(f"Missing {REPORT_JSON}; run without --check to write it.", file=sys.stderr)
            return 1
        committed = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
        for key in ("full_set", "held_out_scaffold_split"):
            for metric in ("rmse", "mae", "r2", "n"):
                if abs(float(committed[key][metric]) - float(report[key][metric])) > 1e-9:
                    print(
                        f"{key}.{metric}: committed {committed[key][metric]} != measured {report[key][metric]}",
                        file=sys.stderr,
                    )
                    return 1
        print("ESOL report matches the committed measurements.")
        return 0
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.write_text(render(report), encoding="utf-8")
    print(json.dumps({"status": report["status"], "rmse": report["full_set"]["rmse"], "report": str(REPORT_MD)}))
    return 0


if __name__ == "__main__":  # pragma: no cover - measurement entry point
    raise SystemExit(main())
