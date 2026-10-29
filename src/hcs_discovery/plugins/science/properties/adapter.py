"""Adapter and workflow execution handler for learned property prediction."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from rdkit import Chem

from ....core.config import Settings
from ....workflow.registry import NodeContext
from ....workflow.table import Column, Table
from .models import AVAILABLE_MODELS, PropertyModel, get_property_model

ADAPTER_ID = "science:property-predict"


class PropertyPredictorConfig(BaseModel):
    """Configuration for learned property prediction node."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    model_id: str = Field(
        default="esol_solubility",
        description="Identifier of property prediction model to execute.",
    )
    output_prefix: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9_]{0,31}$",
        description="Optional custom prefix for result columns. Defaults to model_id.",
    )
    include_uncertainty: bool = Field(
        default=True,
        description="Include uncertainty standard error column in results.",
    )
    check_applicability_domain: bool = Field(
        default=True,
        description="Perform applicability domain checks and report warnings.",
    )

    @field_validator("model_id")
    @classmethod
    def _validate_model_id(cls, value: str) -> str:
        if value not in AVAILABLE_MODELS:
            raise ValueError(f"Unknown model_id '{value}'. Available: {', '.join(sorted(AVAILABLE_MODELS))}")
        return value


def probe_property_predictor(settings: Settings | None = None) -> dict[str, Any]:
    """Probe property predictor adapter capability on this host."""
    del settings
    models_info = [get_property_model(mid).metadata.as_dict() for mid in sorted(AVAILABLE_MODELS)]
    return {
        "id": ADAPTER_ID,
        "status": "available",
        "available": True,
        "backend": "cpu",
        "models": models_info,
        "detail": (
            f"{len(AVAILABLE_MODELS)} literature-derived CPU property prediction model(s) operational; "
            "measured accuracy is documented under docs/validation."
        ),
    }


def property_prediction_columns(
    model: PropertyModel,
    prefix: str,
    *,
    include_uncertainty: bool = True,
    check_domain: bool = True,
) -> list[Column]:
    """Columns produced by the property prediction node."""
    meta = model.metadata
    direction = "higher" if meta.endpoint == "cns_mpo_score" else None
    cols = [
        Column(
            f"{prefix}_pred",
            f"{meta.display_name} ({meta.endpoint})",
            "number",
            unit=meta.unit,
            direction=direction,  # type: ignore[arg-type]
            method=meta.architecture,
            description=meta.description,
        )
    ]
    if include_uncertainty:
        cols.append(
            Column(
                f"{prefix}_uncertainty",
                f"{meta.endpoint} uncertainty",
                "number",
                unit=f"±{meta.unit}",
                direction="lower",
                method="Heuristic descriptor-distance error scale",
                description=(
                    "Heuristic error scale based on descriptor distance; not a calibrated "
                    "confidence interval or prediction interval."
                ),
            )
        )
    if check_domain:
        cols.extend(
            [
                Column(
                    f"{prefix}_in_domain",
                    f"{meta.endpoint} in-domain",
                    "boolean",
                    description="Indicates whether molecule falls inside the model's tested applicability domain.",
                ),
                Column(
                    f"{prefix}_domain_warning",
                    f"{meta.endpoint} domain notes",
                    "string",
                    description="Applicability domain boundary notes or warnings.",
                ),
            ]
        )
    return cols


class PropertyPredictorAdapter:
    """Scientific adapter executing learned property prediction."""

    def __init__(self, model_id: str = "esol_solubility") -> None:
        self.model = get_property_model(model_id)

    def predict_single(self, smiles: str) -> tuple[float | None, float | None, bool, str | None]:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return (None, None, False, "Invalid SMILES structure")
        return self.model.predict(mol)


def run_property_prediction(table: Table, config: PropertyPredictorConfig, ctx: NodeContext) -> Table:
    """Execute property prediction step across table molecules."""
    table.require(["smiles"])

    model = get_property_model(config.model_id)
    meta = model.metadata
    prefix = config.output_prefix or config.model_id

    ctx.log(
        f"Executing property model '{meta.display_name}' ({meta.endpoint}) via {meta.architecture}.",
        level="info",
        data={"metadata": meta.as_dict()},
    )
    for caveat in meta.scientific_caveats:
        ctx.log(f"Scientific caveat: {caveat}", level="info")

    columns = property_prediction_columns(
        model,
        prefix,
        include_uncertainty=config.include_uncertainty,
        check_domain=config.check_applicability_domain,
    )

    preds: list[float | None] = []
    uncertainties: list[float | None] = []
    in_domains: list[bool] = []
    warnings: list[str | None] = []

    total = len(table.rows)
    domain_violations = 0
    parse_errors = 0

    for idx, row in enumerate(table.rows, start=1):
        if idx % 100 == 0 or idx == total:
            ctx.check_cancel()
            ctx.report_progress(idx / total if total else None)

        smiles = row.get("smiles")
        if not smiles or not isinstance(smiles, str):
            parse_errors += 1
            preds.append(None)
            if config.include_uncertainty:
                uncertainties.append(None)
            if config.check_applicability_domain:
                in_domains.append(False)
                warnings.append("Missing or non-string SMILES")
            continue

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            parse_errors += 1
            preds.append(None)
            if config.include_uncertainty:
                uncertainties.append(None)
            if config.check_applicability_domain:
                in_domains.append(False)
                warnings.append("Invalid SMILES structure")
            continue

        val, unc, in_dom, warn = model.predict(mol)
        preds.append(val)
        if config.include_uncertainty:
            uncertainties.append(unc)
        if config.check_applicability_domain:
            in_domains.append(in_dom)
            warnings.append(warn)
            if not in_dom:
                domain_violations += 1

    result = table.copy()
    col_idx = 0
    result.add_values(columns[col_idx], preds)
    col_idx += 1

    if config.include_uncertainty:
        result.add_values(columns[col_idx], uncertainties)
        col_idx += 1

    if config.check_applicability_domain:
        result.add_values(columns[col_idx], in_domains)
        col_idx += 1
        result.add_values(columns[col_idx], warnings)

    summary_msg = f"Completed prediction for {total} compounds with model '{config.model_id}'."
    if domain_violations:
        summary_msg += f" {domain_violations} compound(s) triggered applicability domain warnings."
    ctx.log(summary_msg, level="warning" if domain_violations else "info")

    ctx.report_progress(1.0)
    return result
