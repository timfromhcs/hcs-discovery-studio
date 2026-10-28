"""Scientific tests, verification and benchmark protocols for learned property prediction."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest
from rdkit import Chem

from hcs_discovery.plugins.science.properties.adapter import (
    ADAPTER_ID,
    PropertyPredictorConfig,
    probe_property_predictor,
    run_property_prediction,
)
from hcs_discovery.plugins.science.properties.models import (
    CNSMPOModel,
    ESOLSolubilityModel,
)
from hcs_discovery.plugins.science.properties.scaffold import (
    bemis_murcko_scaffold,
    scaffold_split,
)
from hcs_discovery.workflow.table import Column, Table


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


def test_bemis_murcko_scaffold_extraction() -> None:
    # Acyclic molecule has no ring scaffold
    assert bemis_murcko_scaffold("CCCCCO") == ""

    # Benzene scaffold
    assert bemis_murcko_scaffold("c1ccccc1") == "c1ccccc1"

    # Aspirin: 2-(acetyloxy)benzoic acid -> benzene ring core
    scaf_aspirin = bemis_murcko_scaffold("CC(=O)Oc1ccccc1C(=O)O")
    assert scaf_aspirin == "c1ccccc1"

    # Generic scaffold converts all heteroatoms to C and bonds to single
    generic = bemis_murcko_scaffold("c1cnccn1", generic=True)
    assert generic != ""
    assert "n" not in generic.lower() or "C" in generic


def test_scaffold_split_no_leakage() -> None:
    # 10 compounds with 3 distinct scaffolds: benzene, pyridine, and naphthalene
    compounds = [
        {"smiles": "c1ccccc1C", "id": "tol"},
        {"smiles": "c1ccccc1O", "id": "ph"},
        {"smiles": "c1ccccc1Cl", "id": "cb"},
        {"smiles": "c1ccccc1F", "id": "fb"},
        {"smiles": "c1ccncc1C", "id": "pyr1"},
        {"smiles": "c1ccncc1N", "id": "pyr2"},
        {"smiles": "c1ccncc1O", "id": "pyr3"},
        {"smiles": "c1ccc2ccccc2c1C", "id": "naph1"},
        {"smiles": "c1ccc2ccccc2c1O", "id": "naph2"},
        {"smiles": "c1ccc2ccccc2c1Br", "id": "naph3"},
    ]

    train, test = scaffold_split(compounds, train_ratio=0.7, seed=42)
    assert len(train) > 0
    assert len(test) > 0
    assert len(train) + len(test) == len(compounds)

    # Prove zero scaffold overlap between train and test
    train_scaffolds = {bemis_murcko_scaffold(it["smiles"]) for it in train}
    test_scaffolds = {bemis_murcko_scaffold(it["smiles"]) for it in test}
    overlap = train_scaffolds.intersection(test_scaffolds)
    assert len(overlap) == 0, f"Scaffold leakage detected: {overlap}"


def test_esol_solubility_predictions_and_domain() -> None:
    model = ESOLSolubilityModel()
    assert model.metadata.endpoint == "logS"

    # 1. Benzene (c1ccccc1): literature logS ~ -1.5
    mol_benzene = Chem.MolFromSmiles("c1ccccc1")
    pred_b, unc_b, in_dom_b, warn_b = model.predict(mol_benzene)
    assert pred_b is not None
    assert -2.2 <= pred_b <= -1.0
    assert in_dom_b is True
    assert warn_b is None
    assert 0.7 <= unc_b <= 1.2

    # 2. Caffeine: moderate aqueous solubility
    mol_caff = Chem.MolFromSmiles("CN1C=NC2=C1C(=O)N(C(=O)N2C)C")
    pred_c, _unc_c, in_dom_c, _warn_c = model.predict(mol_caff)
    assert pred_c is not None
    assert -2.0 <= pred_c <= 0.0
    assert in_dom_c is True

    # 3. Outlier check: heavy atom out of domain (Mercury organometallic)
    mol_hg = Chem.MolFromSmiles("CC[Hg]CC")
    if mol_hg is not None:
        _, _, in_dom_hg, warn_hg = model.predict(mol_hg)
        assert in_dom_hg is False
        assert warn_hg is not None
        assert "Hg" in warn_hg


def test_cns_mpo_bbb_scoring() -> None:
    model = CNSMPOModel()
    assert model.metadata.endpoint == "cns_mpo_score"

    # Diazepam (Valium) - known CNS active drug
    mol_diaz = Chem.MolFromSmiles("CN1C(=O)CN=C(c2ccccc2)c3cc(Cl)ccc13")
    score_d, unc_d, in_dom_d, _ = model.predict(mol_diaz)
    assert score_d is not None
    assert score_d >= 4.0  # Favorable CNS penetration score
    assert in_dom_d is True
    assert unc_d == 0.25


def test_probe_property_predictor() -> None:
    probe = probe_property_predictor()
    assert probe["id"] == ADAPTER_ID
    assert probe["available"] is True
    assert probe["backend"] == "cpu"
    assert len(probe["models"]) >= 2


def test_property_prediction_workflow_node(tmp_path: Path) -> None:
    config = PropertyPredictorConfig(
        model_id="esol_solubility",
        output_prefix="solubility",
        include_uncertainty=True,
        check_applicability_domain=True,
    )

    table = Table(
        columns=[Column("smiles", "SMILES", "string"), Column("id", "ID", "string")],
        rows=[
            {"smiles": "CCO", "id": "ethanol"},
            {"smiles": "CC(=O)Oc1ccccc1C(=O)O", "id": "aspirin"},
            {"smiles": "INVALID_STRUCTURE", "id": "bad"},
        ],
    )

    ctx = DummyContext(tmp_path)
    result = run_property_prediction(table, config, ctx)  # type: ignore[arg-type]

    assert len(result.rows) == 3
    assert result.has_column("solubility_pred")
    assert result.has_column("solubility_uncertainty")
    assert result.has_column("solubility_in_domain")
    assert result.has_column("solubility_domain_warning")

    # Ethanol (soluble)
    assert result.rows[0]["solubility_pred"] is not None
    assert result.rows[0]["solubility_in_domain"] is True

    # Aspirin
    assert result.rows[1]["solubility_pred"] is not None

    # Invalid structure (None without exception)
    assert result.rows[2]["solubility_pred"] is None
    assert result.rows[2]["solubility_in_domain"] is False


@pytest.mark.scientific
def test_esol_benchmark_scaffold_evaluation() -> None:
    """Benchmark ESOL predictions on held-out scaffold split against trivial mean baseline."""
    # 14 benchmark small molecules with published experimental logS
    # Delaney (2004) reference values
    benchmark_dataset = [
        {"smiles": "c1ccccc1", "exp_logS": -1.54},  # benzene
        {"smiles": "c1ccc(cc1)Cl", "exp_logS": -2.39},  # chlorobenzene
        {"smiles": "c1ccc(cc1)O", "exp_logS": -0.05},  # phenol
        {"smiles": "c1ccc(cc1)N", "exp_logS": -0.40},  # aniline
        {"smiles": "c1ccc(cc1)C", "exp_logS": -2.25},  # toluene
        {"smiles": "c1ccc(cc1)CC", "exp_logS": -2.78},  # ethylbenzene
        {"smiles": "c1ccc2ccccc2c1", "exp_logS": -3.58},  # naphthalene
        {"smiles": "c1ccc2c(c1)ccc3ccccc23", "exp_logS": -4.89},  # phenanthrene
        {"smiles": "CCO", "exp_logS": 0.49},  # ethanol
        {"smiles": "CCCO", "exp_logS": 0.14},  # propanol
        {"smiles": "CCCCO", "exp_logS": -0.04},  # butanol
        {"smiles": "CCCCCO", "exp_logS": -0.60},  # pentanol
        {"smiles": "c1cncnc1", "exp_logS": 0.70},  # pyrimidine
        {"smiles": "c1ccncc1", "exp_logS": 0.65},  # pyridine
    ]

    train, test = scaffold_split(benchmark_dataset, train_ratio=0.6, seed=123)
    assert len(train) > 0
    assert len(test) > 0

    # Trivial baseline: mean of training set
    train_mean = sum(it["exp_logS"] for it in train) / len(train)
    trivial_mse = sum((it["exp_logS"] - train_mean) ** 2 for it in test) / len(test)
    trivial_rmse = math.sqrt(trivial_mse)

    # ESOL model predictions on held-out test split
    model = ESOLSolubilityModel()
    esol_errors = []
    for it in test:
        mol = Chem.MolFromSmiles(it["smiles"])
        pred, _, _, _ = model.predict(mol)
        assert pred is not None
        esol_errors.append((pred - it["exp_logS"]) ** 2)

    esol_rmse = math.sqrt(sum(esol_errors) / len(esol_errors))

    # ESOL model must outperform trivial mean baseline on held-out test split
    assert esol_rmse < trivial_rmse, (
        f"ESOL RMSE ({esol_rmse:.3f}) should be lower than trivial baseline RMSE ({trivial_rmse:.3f})"
    )
