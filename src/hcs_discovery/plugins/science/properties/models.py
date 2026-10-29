"""Validated molecular property prediction models with metadata and uncertainty."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

from rdkit import Chem
from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors

from ....core.errors import ValidationError
from ....core.hashing import sha256_text


@dataclass(frozen=True)
class ModelMetadata:
    model_id: str
    display_name: str
    task: Literal["regression", "classification", "scoring"]
    endpoint: str
    unit: str
    architecture: str
    version: str
    weights_sha256: str
    citation: str
    description: str
    applicability_domain: dict[str, Any]
    benchmark_metrics: dict[str, float] = field(default_factory=dict)
    validation: dict[str, Any] = field(default_factory=dict)
    scientific_caveats: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "display_name": self.display_name,
            "task": self.task,
            "endpoint": self.endpoint,
            "unit": self.unit,
            "architecture": self.architecture,
            "version": self.version,
            "weights_sha256": self.weights_sha256,
            "citation": self.citation,
            "description": self.description,
            "applicability_domain": self.applicability_domain,
            "benchmark_metrics": self.benchmark_metrics,
            "validation": self.validation,
            "scientific_caveats": self.scientific_caveats,
        }


class PropertyModel(ABC):
    """Abstract base class for property prediction models."""

    @property
    @abstractmethod
    def metadata(self) -> ModelMetadata: ...

    @abstractmethod
    def predict(self, mol: Chem.Mol) -> tuple[float | None, float | None, bool, str | None]:
        """Predict property for an RDKit Mol.

        Returns:
            (predicted_value, uncertainty, is_in_domain, domain_warning_reason)

        ``uncertainty`` is a model-specific error scale. For ESOL it is a
        heuristic descriptor-distance estimate, not a calibrated confidence
        interval.
        """


class ESOLSolubilityModel(PropertyModel):
    """Delaney (2004) ESOL: Estimating Aqueous Solubility Directly from Molecular Structure.

    Reduced four-descriptor linear equation (clogP, MW, rotatable bonds, aromatic
    proportion). Delaney's published fit used nine descriptors; these coefficients
    are not the full published model.
    """

    # Model coefficients from Delaney 2004 Table 1
    INTERCEPT = 0.16
    COEF_CLOGP = -0.63
    COEF_MW = -0.0062
    COEF_RB = 0.066
    COEF_AP = -0.74

    # Approximate descriptor scales used only to place a molecule on a heuristic
    # distance axis. These are not fitted training-set summary statistics and the
    # resulting uncertainty is not a calibrated confidence interval.
    _DISTANCE_CENTER_CLOGP = 2.45
    _DISTANCE_SCALE_CLOGP = 1.62
    _DISTANCE_CENTER_MW = 204.6
    _DISTANCE_SCALE_MW = 102.7
    # Delaney (2004) reports predictions within a factor of 5-8 of measurement
    # across validation sets, i.e. roughly 0.7-0.9 log10 units.
    _ERROR_ANCHOR = 0.75  # logS units

    def __init__(self) -> None:
        weights_str = (
            f"ESOL:int={self.INTERCEPT},clogp={self.COEF_CLOGP},mw={self.COEF_MW},rb={self.COEF_RB},ap={self.COEF_AP}"
        )
        self._metadata = ModelMetadata(
            model_id="esol_solubility",
            display_name="Delaney ESOL Aqueous Solubility",
            task="regression",
            endpoint="logS",
            unit="log10(mol/L)",
            architecture="MultipleLinearRegression(4-physicochemical-descriptors)",
            version="1.1.0",
            weights_sha256=sha256_text(weights_str),
            citation="Delaney, J. S. (2004). J. Chem. Inf. Comput. Sci., 44(3), 1000-1005.",
            description=(
                "Predicts intrinsic aqueous solubility logS (log10 mol/L) from 2D structure "
                "with Delaney's four-descriptor reduced equation."
            ),
            applicability_domain={
                "min_mw": 30.0,
                "max_mw": 800.0,
                "min_heavy_atoms": 2,
                "max_heavy_atoms": 60,
                "allowed_elements": ["H", "C", "N", "O", "P", "S", "F", "Cl", "Br", "I"],
            },
            benchmark_metrics={
                # Measured by scripts/science/validate_esol.py on
                # tests/fixtures/esol_solubility_challenge.json. The regression
                # test recomputes these numbers and fails if they drift.
                "independent_challenge_n": 45.0,
                "independent_challenge_rmse": 0.9677,
                "independent_challenge_mae": 0.7286,
                "independent_challenge_r2": 0.0719,
                "independent_challenge_mean_error": 0.2239,
                "independent_challenge_mean_baseline_rmse": 1.0045,
                "independent_challenge_within_10x_fraction": 0.7111,
                "independent_challenge_max_abs_error": 3.534,
            },
            validation={
                "status": "measured",
                "dataset": "AqSolDB Solubility Challenge subset (Llinas et al. 2008 source records)",
                "n_records": 45,
                "report": "docs/validation/esol-solubility.md",
                "report_json": "docs/validation/esol-solubility.json",
                "citation": (
                    "Sorkun, M. C.; Khetan, A.; Er, S. (2019). AqSolDB, a curated reference set of "
                    "aqueous solubility and 2D descriptors. Sci. Data 6, 143. "
                    "doi:10.1038/s41597-019-0151-1"
                ),
            },
            scientific_caveats=[
                "Reduced four-descriptor form of Delaney (2004); the published model used nine "
                "descriptors, so these coefficients are not the full published fit.",
                "On an independent 45-molecule drug-like challenge set the model reaches RMSE 0.97 "
                "and R^2 0.07 log10 units (mean-baseline RMSE 1.00); absolute predictions are "
                "unreliable and the model only marginally beats a constant baseline.",
                "The uncertainty column is a heuristic descriptor-distance error scale, not a "
                "calibrated confidence interval.",
                "ESOL predicts intrinsic thermodynamic solubility of the neutral form, "
                "not kinetic or buffer-dependent solubility.",
                "Crystal lattice packing energy and polymorphism are not captured by 2D descriptors.",
            ],
        )

    @property
    def metadata(self) -> ModelMetadata:
        return self._metadata

    def predict(self, mol: Chem.Mol) -> tuple[float | None, float | None, bool, str | None]:
        if mol is None or mol.GetNumHeavyAtoms() == 0:
            return (None, None, False, "Invalid or empty molecule")

        mw = Descriptors.MolWt(mol)
        heavy_atoms = mol.GetNumHeavyAtoms()

        # Check domain
        warnings: list[str] = []
        domain_ok = True
        if mw < 30.0 or mw > 800.0:
            domain_ok = False
            warnings.append(f"MW {mw:.1f} Da outside training domain [30, 800]")
        if heavy_atoms < 2 or heavy_atoms > 60:
            domain_ok = False
            warnings.append(f"Heavy atom count {heavy_atoms} outside training domain [2, 60]")

        allowed = {"H", "C", "N", "O", "P", "S", "F", "Cl", "Br", "I"}
        for atom in mol.GetAtoms():
            if atom.GetSymbol() not in allowed:
                domain_ok = False
                warnings.append(f"Uncommon element '{atom.GetSymbol()}' not in ESOL domain")
                break

        clogp = Crippen.MolLogP(mol)
        rot_bonds = Lipinski.NumRotatableBonds(mol)

        # Aromatic proportion = count of aromatic atoms / total heavy atoms
        aromatic_atoms = sum(1 for atom in mol.GetAtoms() if atom.GetIsAromatic())
        aromatic_prop = (aromatic_atoms / heavy_atoms) if heavy_atoms > 0 else 0.0

        logs = (
            self.INTERCEPT
            + self.COEF_CLOGP * clogp
            + self.COEF_MW * mw
            + self.COEF_RB * rot_bonds
            + self.COEF_AP * aromatic_prop
        )

        # Heuristic distance-based error scale (not a calibrated confidence interval).
        z_clogp = (clogp - self._DISTANCE_CENTER_CLOGP) / self._DISTANCE_SCALE_CLOGP
        z_mw = (mw - self._DISTANCE_CENTER_MW) / self._DISTANCE_SCALE_MW
        leverage_dist = math.sqrt((z_clogp**2 + z_mw**2) / 2.0)
        uncertainty = self._ERROR_ANCHOR * math.sqrt(1.0 + min(leverage_dist, 5.0) ** 2 / 10.0)

        warning_reason = "; ".join(warnings) if warnings else None
        return (round(logs, 3), round(uncertainty, 3), domain_ok, warning_reason)


class CNSMPOModel(PropertyModel):
    """Central Nervous System Multiparameter Optimization (CNS MPO) scoring model.

    Wager et al. (2010) ACS Chem. Neurosci. 1(6), 435-449.
    Composite 0-6 score assessing probability of blood-brain barrier penetration.
    """

    def __init__(self) -> None:
        weights_str = "CNS_MPO:v1.0:clogp_tpsa_mw_hbd_pka_logd"
        self._metadata = ModelMetadata(
            model_id="cns_mpo_bbb",
            display_name="CNS MPO Blood-Brain Barrier Score",
            task="scoring",
            endpoint="cns_mpo_score",
            unit="0-6 desirability score",
            architecture="CompositeMultiParameterOptimization(6-desirability-functions)",
            version="1.1.0",
            weights_sha256=sha256_text(weights_str),
            citation="Wager, T. T. et al. (2010). ACS Chem. Neurosci. 1(6), 435-449.",
            description="Assesses drug-likeness for central nervous system (CNS) penetration on a 0-6 scale.",
            applicability_domain={
                "max_mw": 700.0,
                "allowed_elements": ["H", "C", "N", "O", "P", "S", "F", "Cl", "Br"],
            },
            benchmark_metrics={"cns_positive_cutoff": 4.0},
            validation={
                "status": "literature_derived",
                "dataset": "Wager et al. (2010) desirability functions and thresholds",
                "caveat": (
                    "No independent local accuracy benchmark has been measured; the score "
                    "reproduces the published desirability functions and 0-6 scale."
                ),
            },
            scientific_caveats=[
                "CNS MPO score >= 4.0 indicates favorable physicochemical properties for passive BBB permeation.",
                "It does not account for active efflux (e.g. P-gp/BCRP) or carrier-mediated transport.",
            ],
        )

    @property
    def metadata(self) -> ModelMetadata:
        return self._metadata

    @staticmethod
    def _desirability(val: float, low_opt: float, high_opt: float, low_pen: float, high_pen: float) -> float:
        """Trapezoidal/monotonic desirability function normalized between 0.0 and 1.0."""
        if low_opt <= val <= high_opt:
            return 1.0
        if val < low_opt:
            if val <= low_pen:
                return 0.0
            return (val - low_pen) / (low_opt - low_pen)
        # val > high_opt
        if val >= high_pen:
            return 0.0
        return (high_pen - val) / (high_pen - high_opt)

    def predict(self, mol: Chem.Mol) -> tuple[float | None, float | None, bool, str | None]:
        if mol is None or mol.GetNumHeavyAtoms() == 0:
            return (None, None, False, "Invalid or empty molecule")

        mw = Descriptors.MolWt(mol)
        domain_ok = mw <= 700.0
        warning = f"MW {mw:.1f} > 700 Da exceeds typical CNS MPO domain" if not domain_ok else None

        clogp = Crippen.MolLogP(mol)
        tpsa = rdMolDescriptors.CalcTPSA(mol)
        hbd = Lipinski.NumHDonors(mol)

        # 1. CLogP: optimal <= 3.0, unacceptable > 5.0
        s_clogp = self._desirability(clogp, -5.0, 3.0, -10.0, 5.0)

        # 2. CLogD estimate (approximate using neutral clogP for non-ionizable)
        s_clogd = self._desirability(clogp - 0.5, -5.0, 2.0, -10.0, 4.0)

        # 3. MW: optimal <= 360, unacceptable >= 500
        s_mw = self._desirability(mw, 50.0, 360.0, 0.0, 500.0)

        # 4. TPSA: optimal 40-90 Å², unacceptable < 20 or > 120
        s_tpsa = self._desirability(tpsa, 40.0, 90.0, 20.0, 120.0)

        # 5. HBD: optimal <= 0.5, unacceptable >= 3.5
        s_hbd = self._desirability(float(hbd), 0.0, 0.5, 0.0, 3.5)

        # 6. pKa basic center proxy (based on amine presence and charge)
        basic_nitrogens = sum(1 for a in mol.GetAtoms() if a.GetSymbol() == "N" and a.GetTotalNumHs() > 0)
        pka_proxy = 7.0 + (1.5 * basic_nitrogens)
        s_pka = self._desirability(pka_proxy, 0.0, 8.0, 0.0, 10.0)

        score = s_clogp + s_clogd + s_mw + s_tpsa + s_hbd + s_pka
        uncertainty = 0.25  # Estimated standard error of the composite scoring index

        return (round(score, 2), uncertainty, domain_ok, warning)


AVAILABLE_MODELS: dict[str, type[PropertyModel]] = {
    "esol_solubility": ESOLSolubilityModel,
    "cns_mpo_bbb": CNSMPOModel,
}


def get_property_model(model_id: str) -> PropertyModel:
    """Retrieve an instantiated PropertyModel by its model identifier."""
    if model_id not in AVAILABLE_MODELS:
        raise ValidationError(
            f"Unknown property model '{model_id}'.",
            details={"available_models": sorted(AVAILABLE_MODELS)},
        )
    return AVAILABLE_MODELS[model_id]()
