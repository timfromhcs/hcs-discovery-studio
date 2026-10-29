"""Reproducible validation protocol for the ESOL aqueous solubility model.

The checked-in fixture ``tests/fixtures/esol_solubility_challenge.json`` records
measured logS values curated by AqSolDB (Sorkun et al. 2019) from the
independent Llinas, Glen & Goodman (2008) Solubility Challenge. This module
holds the evaluation code shared by the report-regeneration script and the
regression test, so published metrics cannot drift from the data and code that
produced them.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rdkit import Chem

from ....core.errors import ValidationError
from ....core.hashing import sha256_file
from .models import PropertyModel


@dataclass(frozen=True)
class ValidationMetrics:
    """Accuracy summary for a regression model evaluated on measured values."""

    n: int
    rmse: float
    mae: float
    r2: float
    mean_error: float
    mean_baseline_rmse: float
    within_10x_fraction: float
    max_abs_error: float

    def as_dict(self) -> dict[str, float]:
        return {
            "n": float(self.n),
            "rmse": self.rmse,
            "mae": self.mae,
            "r2": self.r2,
            "mean_error": self.mean_error,
            "mean_baseline_rmse": self.mean_baseline_rmse,
            "within_10x_fraction": self.within_10x_fraction,
            "max_abs_error": self.max_abs_error,
        }


def load_validation_dataset(path: Path) -> dict[str, Any]:
    """Load and structurally validate a measured-solubility fixture.

    Fails closed: malformed records, duplicate identifiers, non-finite or
    non-numeric measurements all raise :class:`ValidationError` rather than
    silently shrinking the evaluation set.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"Validation dataset not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Validation dataset is not valid JSON: {path}", details={"error": str(exc)}) from exc

    if not isinstance(payload, dict):
        raise ValidationError("Validation dataset must be a JSON object.")
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise ValidationError("Validation dataset must contain a non-empty 'records' list.")

    seen: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValidationError(f"Record {index} must be an object.")
        for key in ("id", "name", "smiles", "measured_logS"):
            if key not in record:
                raise ValidationError(f"Record {index} is missing required key '{key}'.")
        record_id = record["id"]
        if not isinstance(record_id, str) or not record_id:
            raise ValidationError(f"Record {index} has an invalid 'id'.")
        if record_id in seen:
            raise ValidationError(f"Duplicate validation record id '{record_id}'.")
        seen.add(record_id)
        if not isinstance(record["smiles"], str) or not record["smiles"]:
            raise ValidationError(f"Record '{record_id}' has an invalid 'smiles'.")
        measured = record["measured_logS"]
        if isinstance(measured, bool) or not isinstance(measured, int | float) or not math.isfinite(measured):
            raise ValidationError(f"Record '{record_id}' has a non-finite 'measured_logS'.")
    return payload


def evaluate_property_model(
    model: PropertyModel,
    records: list[dict[str, Any]],
) -> ValidationMetrics:
    """Predict every record and summarise error against the measured logS values.

    Any unparseable SMILES, missing prediction, or applicability-domain failure
    aborts the evaluation: a validation report must not quietly drop difficult
    molecules.
    """
    predictions: list[float] = []
    measured: list[float] = []
    for record in records:
        record_id = record["id"]
        mol = Chem.MolFromSmiles(record["smiles"])
        if mol is None:
            raise ValidationError(f"Validation record '{record_id}' is not parseable by RDKit.")
        pred, _uncertainty, in_domain, warning = model.predict(mol)
        if pred is None:
            raise ValidationError(f"Model returned no prediction for validation record '{record_id}'.")
        if not in_domain:
            raise ValidationError(
                f"Validation record '{record_id}' is outside the model applicability domain.",
                details={"warning": warning},
            )
        predictions.append(float(pred))
        measured.append(float(record["measured_logS"]))

    errors = [pred - obs for pred, obs in zip(predictions, measured, strict=True)]
    n = len(errors)
    if n < 2:
        raise ValidationError("Validation requires at least two records.")

    mean_error = math.fsum(errors) / n
    mse = math.fsum(error * error for error in errors) / n
    mean_measured = math.fsum(measured) / n
    ss_tot = math.fsum((obs - mean_measured) ** 2 for obs in measured)
    if ss_tot == 0.0:
        raise ValidationError("Measured values have zero variance; R^2 is undefined.")

    return ValidationMetrics(
        n=n,
        rmse=math.sqrt(mse),
        mae=math.fsum(abs(error) for error in errors) / n,
        r2=1.0 - math.fsum(error * error for error in errors) / ss_tot,
        mean_error=mean_error,
        mean_baseline_rmse=math.sqrt(ss_tot / n),
        within_10x_fraction=sum(1 for error in errors if abs(error) <= 1.0) / n,
        max_abs_error=max(abs(error) for error in errors),
    )


def bootstrap_rmse_interval(
    errors: list[float],
    *,
    resamples: int = 10_000,
    seed: int = 20_240_601,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Percentile bootstrap confidence interval for RMSE.

    Deterministic for a fixed ``seed`` so the generated report is reproducible.
    """
    if not errors:
        raise ValidationError("Cannot bootstrap an empty error list.")
    if resamples < 1:
        raise ValidationError("Bootstrap resamples must be positive.")
    if not 0.0 < confidence < 1.0:
        raise ValidationError("Bootstrap confidence must be between 0 and 1.")

    rng = random.Random(seed)
    n = len(errors)
    estimates = []
    for _ in range(resamples):
        total = 0.0
        for _ in range(n):
            error = errors[rng.randrange(n)]
            total += error * error
        estimates.append(math.sqrt(total / n))
    estimates.sort()
    lower_index = int((1.0 - confidence) / 2.0 * (resamples - 1))
    upper_index = int((1.0 + confidence) / 2.0 * (resamples - 1))
    return estimates[lower_index], estimates[upper_index]


def dataset_sha256(path: Path) -> str:
    """SHA-256 of the validation fixture, recorded in the report."""
    return sha256_file(path)
