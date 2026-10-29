"""Validated molecular property prediction models with metadata and uncertainty."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal

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
            version="1.2.0",
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
                "formal_charges": "none (neutral form only)",
                "components": 1,
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

        # ESOL describes the intrinsic solubility of a single neutral species.
        charged = sum(1 for atom in mol.GetAtoms() if atom.GetFormalCharge() != 0)
        if charged:
            domain_ok = False
            warnings.append(f"{charged} charged atom(s); ESOL describes the neutral form")
        fragments = len(Chem.GetMolFrags(mol))
        if fragments > 1:
            domain_ok = False
            warnings.append(f"{fragments} disconnected components; ESOL describes a single species")

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
    """Approximation of the CNS MPO desirability score (Wager et al., 2010).

    Uses Wager's six desirability functions on a 0-6 scale. Two inputs cannot be
    computed from RDKit alone and are approximated, which is why the output is
    labelled an approximation:

    - ClogD (pH 7.4) is replaced by Crippen cLogP. This is exact for non-ionisable
      molecules and overestimates logD for ionisable ones, which lowers the score.
    - The most basic pKa is not computed. Molecules without a detected basic centre
      get the pKa term's full desirability (a pKa <= 8 is assumed); detected basic
      centres use the class-typical pKa values in ``ASSUMED_PKA`` and say so in the
      row's warning.

    The score describes physicochemical alignment with marketed CNS drugs. It is
    not a probability of blood-brain barrier penetration or brain exposure.
    """

    # Assumed most-basic pKa by detected group; typical values, not predictions.
    ASSUMED_PKA: ClassVar[dict[str, float]] = {"amidine_or_guanidine": 11.0, "aliphatic_amine": 9.0}
    _AMIDINE = Chem.MolFromSmarts("[CX3;!$(C=O);!a](=[NX2;!a;!$(N-[O,S])])[NX3;!a;!$(N-C=O)]")
    _ALIPHATIC_AMINE = Chem.MolFromSmarts(
        "[NX3;+0;!a;!$(N-a);!$(N-[#6]=[#7,#8,#16]);!$(N-[#6]#*);!$(N-[#6]=[#6]);!$(N-[!#6;!#1]);!$(N=*)]"
    )

    def __init__(self) -> None:
        weights_str = "CNS_MPO:v2.0:wager2010_functions;clogd=clogp;pka_assumed=" + ",".join(
            f"{k}:{v}" for k, v in sorted(self.ASSUMED_PKA.items())
        )
        self._metadata = ModelMetadata(
            model_id="cns_mpo_bbb",
            display_name="CNS MPO approximation (Wager 2010)",
            task="scoring",
            endpoint="cns_mpo_score",
            unit="0-6 desirability score",
            architecture="Wager2010 desirability functions; ClogD approximated by cLogP; class-based assumed pKa",
            version="2.0.0",
            weights_sha256=sha256_text(weights_str),
            citation="Wager, T. T. et al. (2010). ACS Chem. Neurosci. 1(6), 435-449.",
            description=(
                "Approximate CNS MPO desirability score (0-6) using Wager's six functions with cLogP in place "
                "of ClogD and an assumed pKa for detected basic centres."
            ),
            applicability_domain={
                "max_mw": 700.0,
                "allowed_elements": ["H", "C", "N", "O", "P", "S", "F", "Cl", "Br"],
            },
            benchmark_metrics={},
            validation={
                "status": "approximation",
                "dataset": None,
                "caveat": (
                    "Desirability functions follow Wager et al. (2010). ClogD and pKa are approximated, so "
                    "scores can differ from the published method; no local benchmark has been run."
                ),
            },
            scientific_caveats=[
                "Approximation: ClogD is replaced by cLogP and the most basic pKa is assumed, not computed.",
                "A physicochemical desirability score, not a probability of BBB penetration or brain exposure.",
                "Does not account for active efflux (e.g. P-gp/BCRP) or carrier-mediated transport.",
                "No uncertainty is reported: there is no calibration evidence for one.",
            ],
        )

    @property
    def metadata(self) -> ModelMetadata:
        return self._metadata

    @staticmethod
    def _decreasing(val: float, full: float, zero: float) -> float:
        """Wager monotonic decreasing desirability: 1 at or below ``full``, 0 at or above ``zero``."""
        if val <= full:
            return 1.0
        if val >= zero:
            return 0.0
        return (zero - val) / (zero - full)

    @staticmethod
    def _tpsa_hump(tpsa: float) -> float:
        """Wager TPSA desirability: 0 at <= 20, rising to 1 at 40, 1 to 90, falling to 0 at 120 A^2."""
        if tpsa <= 20.0 or tpsa >= 120.0:
            return 0.0
        if tpsa < 40.0:
            return (tpsa - 20.0) / 20.0
        if tpsa <= 90.0:
            return 1.0
        return (120.0 - tpsa) / 30.0

    def basic_centre(self, mol: Chem.Mol) -> str | None:
        if mol.HasSubstructMatch(self._AMIDINE):
            return "amidine_or_guanidine"
        if mol.HasSubstructMatch(self._ALIPHATIC_AMINE):
            return "aliphatic_amine"
        return None

    def predict(self, mol: Chem.Mol) -> tuple[float | None, float | None, bool, str | None]:
        if mol is None or mol.GetNumHeavyAtoms() == 0:
            return (None, None, False, "Invalid or empty molecule")

        mw = Descriptors.MolWt(mol)
        notes: list[str] = []
        domain_ok = mw <= 700.0
        if not domain_ok:
            notes.append(f"MW {mw:.1f} > 700 Da exceeds typical CNS MPO domain")

        clogp = Crippen.MolLogP(mol)
        tpsa = rdMolDescriptors.CalcTPSA(mol)
        hbd = Lipinski.NumHDonors(mol)
        centre = self.basic_centre(mol)
        if centre is None:
            pka_term = 1.0
        else:
            assumed = self.ASSUMED_PKA[centre]
            pka_term = self._decreasing(assumed, 8.0, 10.0)
            notes.append(f"pKa not computed; assumed {assumed:.1f} for detected {centre.replace('_', ' ')}")

        score = (
            self._decreasing(clogp, 3.0, 5.0)
            + self._decreasing(clogp, 2.0, 4.0)  # ClogD approximated by cLogP
            + self._decreasing(mw, 360.0, 500.0)
            + self._tpsa_hump(tpsa)
            + self._decreasing(float(hbd), 0.5, 3.5)
            + pka_term
        )
        return (round(score, 2), None, domain_ok, "; ".join(notes) or None)


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
