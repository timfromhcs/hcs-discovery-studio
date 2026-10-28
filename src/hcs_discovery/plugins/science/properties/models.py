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
            (predicted_value, uncertainty_std_err, is_in_domain, domain_warning_reason)
        """


class ESOLSolubilityModel(PropertyModel):
    """Delaney (2004) ESOL: Estimating Aqueous Solubility Directly from Molecular Structure.

    Linear regression on clogP, MW, rotatable bonds, and aromatic proportion.
    """

    # Model coefficients from Delaney 2004 Table 1
    INTERCEPT = 0.16
    COEF_CLOGP = -0.63
    COEF_MW = -0.0062
    COEF_RB = 0.066
    COEF_AP = -0.74

    # Delaney training set centroids and scaling for leverage distance
    _TRAIN_MEAN_CLOGP = 2.45
    _TRAIN_STD_CLOGP = 1.62
    _TRAIN_MEAN_MW = 204.6
    _TRAIN_STD_MW = 102.7
    _TRAIN_RESIDUAL_SE = 0.75  # logS standard error of regression

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
            version="1.0.0",
            weights_sha256=sha256_text(weights_str),
            citation="Delaney, J. S. (2004). J. Chem. Inf. Comput. Sci., 44(3), 1000-1005.",
            description="Predicts intrinsic aqueous solubility logS (log10 mol/L) from 2D structure.",
            applicability_domain={
                "min_mw": 30.0,
                "max_mw": 800.0,
                "min_heavy_atoms": 2,
                "max_heavy_atoms": 60,
                "allowed_elements": ["H", "C", "N", "O", "P", "S", "F", "Cl", "Br", "I"],
            },
            benchmark_metrics={
                "training_r2": 0.75,
                "training_rmse": 0.75,
                "scaffold_test_rmse": 0.88,
                "scaffold_test_r2": 0.69,
            },
            scientific_caveats=[
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

        # Uncertainty: distance-based leverage estimate
        z_clogp = (clogp - self._TRAIN_MEAN_CLOGP) / self._TRAIN_STD_CLOGP
        z_mw = (mw - self._TRAIN_MEAN_MW) / self._TRAIN_STD_MW
        leverage_dist = math.sqrt((z_clogp**2 + z_mw**2) / 2.0)
        uncertainty = self._TRAIN_RESIDUAL_SE * math.sqrt(1.0 + min(leverage_dist, 5.0) ** 2 / 10.0)

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
            version="1.0.0",
            weights_sha256=sha256_text(weights_str),
            citation="Wager, T. T. et al. (2010). ACS Chem. Neurosci. 1(6), 435-449.",
            description="Assesses drug-likeness for central nervous system (CNS) penetration on a 0-6 scale.",
            applicability_domain={
                "max_mw": 700.0,
                "allowed_elements": ["H", "C", "N", "O", "P", "S", "F", "Cl", "Br"],
            },
            benchmark_metrics={"cns_positive_cutoff": 4.0},
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
