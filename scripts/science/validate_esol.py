"""Regenerate the ESOL validation report from the checked-in measured dataset.

    python scripts/science/validate_esol.py
    python scripts/science/validate_esol.py --check

``--check`` recomputes every prediction and metric and fails if the checked-in
report under ``docs/validation`` no longer matches the fixture and model code.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path
from typing import Any

import rdkit
from rdkit import Chem

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from hcs_discovery.plugins.science.properties.models import ESOLSolubilityModel  # noqa: E402
from hcs_discovery.plugins.science.properties.validation import (  # noqa: E402
    bootstrap_rmse_interval,
    dataset_sha256,
    evaluate_property_model,
    load_validation_dataset,
)

DEFAULT_DATASET = ROOT / "tests" / "fixtures" / "esol_solubility_challenge.json"
DEFAULT_OUT_DIR = ROOT / "docs" / "validation"
REPORT_STEM = "esol-solubility"


def _build_report(dataset_path: Path) -> tuple[dict[str, Any], list[float]]:
    dataset = load_validation_dataset(dataset_path)
    model = ESOLSolubilityModel()
    metrics = evaluate_property_model(model, dataset["records"])

    predictions = []
    errors = []
    for record in dataset["records"]:
        mol = Chem.MolFromSmiles(record["smiles"])
        pred, _uncertainty, _in_domain, _warning = model.predict(mol)
        assert pred is not None  # evaluate_property_model already failed closed
        error = float(pred) - float(record["measured_logS"])
        predictions.append({**record, "predicted_logS": float(pred), "error": error})
        errors.append(error)

    lower, upper = bootstrap_rmse_interval(errors)
    provenance = dataset["provenance"]
    report = {
        "schema_version": 1,
        "model": {
            "model_id": model.metadata.model_id,
            "version": model.metadata.version,
            "weights_sha256": model.metadata.weights_sha256,
            "citation": model.metadata.citation,
        },
        "dataset": {
            "name": dataset["dataset_name"],
            "path": dataset_path.relative_to(ROOT).as_posix(),
            "sha256": dataset_sha256(dataset_path),
            "n_records": metrics.n,
            "provenance": provenance,
        },
        "metrics": metrics.as_dict(),
        "rmse_95pct_bootstrap_ci": [lower, upper],
        "environment": {
            "python": platform.python_version(),
            "rdkit": rdkit.__version__,
        },
        "records": predictions,
    }
    return report, errors


def _render_markdown(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    provenance = report["dataset"]["provenance"]
    ci_low, ci_high = report["rmse_95pct_bootstrap_ci"]
    lines = [
        "# ESOL aqueous solubility validation",
        "",
        "Generated from the checked-in measured dataset by "
        "`scripts/science/validate_esol.py`. Re-run the script (or "
        "`python scripts/science/validate_esol.py --check` in CI) to verify "
        "these numbers still match the model code and fixture.",
        "",
        "## Dataset",
        "",
        f"- Dataset: {report['dataset']['name']}",
        f"- Records evaluated: {report['dataset']['n_records']}",
        f"- Fixture: `{report['dataset']['path']}` (SHA-256 `{report['dataset']['sha256']}`)",
        f"- Distribution: [{provenance['distribution']}]({provenance['url']}), "
        f"DOI {provenance['doi']}, license {provenance['license']}",
        f"- Original measurements: {provenance['original_source']} (DOI {provenance['original_source_doi']})",
        f"- Retrieved: {provenance['retrieved_utc']}",
        f"- Selection rule: {provenance['selection_rule']}",
    ]
    for excluded in provenance.get("excluded", []):
        lines.append(f"- Excluded `{excluded['id']}` ({excluded['name']}): {excluded['reason']}.")
    lines += [
        "",
        "## Results",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| n | {metrics['n']:.0f} |",
        f"| RMSE (log10 units) | {metrics['rmse']:.4f} |",
        f"| RMSE 95% bootstrap CI | [{ci_low:.4f}, {ci_high:.4f}] |",
        f"| MAE (log10 units) | {metrics['mae']:.4f} |",
        f"| R² | {metrics['r2']:.4f} |",
        f"| Mean error (prediction − measurement) | {metrics['mean_error']:+.4f} |",
        f"| Mean-baseline RMSE | {metrics['mean_baseline_rmse']:.4f} |",
        f"| Predictions within 10× of measurement | {metrics['within_10x_fraction'] * 100:.1f}% |",
        f"| Largest absolute error (log10 units) | {metrics['max_abs_error']:.4f} |",
        "",
        "The mean baseline predicts the dataset mean for every molecule; a model "
        "that does not beat it has no demonstrated ranking or absolute accuracy on "
        "this set.",
        "",
        "## Per-molecule predictions",
        "",
        "| ID | Name | Measured logS | Predicted logS | Error |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for record in report["records"]:
        name = str(record["name"]).replace("|", "\\|")
        lines.append(
            f"| {record['id']} | {name} | {record['measured_logS']:.3f} | "
            f"{record['predicted_logS']:.3f} | {record['error']:+.3f} |"
        )
    lines += [
        "",
        "## Interpretation and limitations",
        "",
        f"- This is a measured-value check of the Delaney (2004) four-descriptor "
        f"reduced ESOL equation, not a re-fit. On this {metrics['n']:.0f}-molecule "
        f"drug-like challenge set it achieves RMSE {metrics['rmse']:.3f} log10 units "
        f"and R² {metrics['r2']:.3f}. The near-zero R² means the model explains "
        "little of the variance in this set; absolute solubility predictions "
        "should not be treated as reliable for these compounds.",
        "- The set postdates Delaney (2004), but AqSolDB curation may still share "
        "source measurements with that training data; this report does not claim a "
        "fully leakage-audited benchmark.",
        "- ESOL estimates intrinsic solubility of the neutral form. It does not "
        "model ionization, salt form, pH, polymorphs, or kinetic dissolution, all of "
        "which matter for the ionizable and zwitterionic molecules here.",
        "- Applicability-domain flags only state that descriptors fall inside the "
        "fitted range. They do not certify accuracy, as the errors above show.",
        f"- The 95% bootstrap interval [{ci_low:.3f}, {ci_high:.3f}] reflects "
        f"sampling noise for n={metrics['n']:.0f}; it is wide and does not include "
        "model-form error.",
        "",
        f"Environment: Python {report['environment']['python']}, RDKit "
        f"{report['environment']['rdkit']}. Model weights hash "
        f"`{report['model']['weights_sha256']}`.",
        "",
    ]
    return "\n".join(lines)


def _check_existing(report: dict[str, Any], json_path: Path) -> int:
    if not json_path.is_file():
        print(f"missing checked-in report: {json_path}", file=sys.stderr)
        return 1
    existing = json.loads(json_path.read_text(encoding="utf-8"))
    problems = []
    if existing.get("metrics") != report["metrics"]:
        problems.append(f"metrics changed: {existing.get('metrics')} -> {report['metrics']}")
    if existing.get("rmse_95pct_bootstrap_ci") != report["rmse_95pct_bootstrap_ci"]:
        problems.append("bootstrap RMSE interval changed")
    if existing.get("dataset", {}).get("sha256") != report["dataset"]["sha256"]:
        problems.append("dataset SHA-256 changed")
    old_records = existing.get("records", [])
    new_records = report["records"]
    if len(old_records) != len(new_records):
        problems.append(f"record count changed: {len(old_records)} -> {len(new_records)}")
    else:
        for old, new in zip(old_records, new_records, strict=True):
            if old.get("id") != new.get("id"):
                problems.append(f"record order/id changed at {old.get('id')!r} -> {new.get('id')!r}")
                break
            if round(float(old.get("predicted_logS", "nan")), 6) != round(new["predicted_logS"], 6):
                problems.append(f"prediction for {new['id']} changed")
                break
    if problems:
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        print("re-run scripts/science/validate_esol.py to regenerate the report", file=sys.stderr)
        return 1
    print(f"validation report is current: {json_path}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="measured-solubility fixture")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="report output directory")
    parser.add_argument("--check", action="store_true", help="verify the checked-in report is current")
    args = parser.parse_args(argv[1:])

    report, _errors = _build_report(args.dataset)
    json_path = args.out_dir / f"{REPORT_STEM}.json"
    if args.check:
        return _check_existing(report, json_path)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown_path = args.out_dir / f"{REPORT_STEM}.md"
    markdown_path.write_text(_render_markdown(report), encoding="utf-8")
    print(f"wrote {json_path}")
    print(f"wrote {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
