"""Scientific tests, verification and benchmark protocols for learned property prediction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from rdkit import Chem

from hcs_discovery.core.errors import ValidationError
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
from hcs_discovery.plugins.science.properties.validation import (
    bootstrap_rmse_interval,
    dataset_sha256,
    evaluate_property_model,
    load_validation_dataset,
)
from hcs_discovery.workflow.table import Column, Table

ROOT = Path(__file__).resolve().parents[2]
VALIDATION_FIXTURE = ROOT / "tests" / "fixtures" / "esol_solubility_challenge.json"
VALIDATION_REPORT = ROOT / "docs" / "validation" / "esol-solubility.json"


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


def test_esol_validation_fixture_is_complete_and_in_domain() -> None:
    """The measured dataset must be provenance-complete and inside the stated domain."""
    dataset = load_validation_dataset(VALIDATION_FIXTURE)
    records = dataset["records"]
    assert len(records) == 45
    assert len({record["id"] for record in records}) == len(records)

    provenance = dataset["provenance"]
    assert provenance["license"] == "MIT"
    assert provenance["original_source_doi"] == "10.1021/ci800058v"
    assert len(provenance["sha256"]) == 64
    assert provenance["excluded"] == [
        {
            "id": "I-75",
            "name": "ranitidine",
            "reason": "contains a formally charged atom",
        }
    ]

    model = ESOLSolubilityModel()
    for record in records:
        mol = Chem.MolFromSmiles(record["smiles"])
        pred, _uncertainty, in_domain, warning = model.predict(mol)
        assert pred is not None, record["id"]
        assert in_domain is True, record["id"]
        assert warning is None, record["id"]


def test_esol_validation_protocol_rejects_out_of_domain_records() -> None:
    """A difficult molecule must abort the evaluation, not be silently dropped."""
    dataset = load_validation_dataset(VALIDATION_FIXTURE)
    bad = [dict(dataset["records"][0], id="Hg-outside-domain", smiles="CC[Hg]CC")]
    with pytest.raises(ValidationError, match="outside the model applicability domain"):
        evaluate_property_model(ESOLSolubilityModel(), bad)


def test_esol_validation_protocol_rejects_malformed_fixture(tmp_path: Path) -> None:
    path = tmp_path / "malformed.json"
    path.write_text(
        json.dumps(
            {
                "records": [
                    {"id": "x", "name": "x", "smiles": "CCO", "measured_logS": True},
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="non-finite"):
        load_validation_dataset(path)


@pytest.mark.scientific
def test_esol_independent_challenge_metrics_are_measured_and_published() -> None:
    """Recompute every published metric from the fixture; fabricated values cannot pass."""
    dataset = load_validation_dataset(VALIDATION_FIXTURE)
    model = ESOLSolubilityModel()
    metrics = evaluate_property_model(model, dataset["records"])
    assert metrics.n == 45

    published = model.metadata.benchmark_metrics
    assert published["independent_challenge_n"] == 45.0
    for key, value in metrics.as_dict().items():
        if key == "n":
            continue
        assert published[f"independent_challenge_{key}"] == pytest.approx(round(value, 4), abs=1e-9), key

    report = json.loads(VALIDATION_REPORT.read_text(encoding="utf-8"))
    assert report["dataset"]["sha256"] == dataset_sha256(VALIDATION_FIXTURE)
    assert report["model"]["weights_sha256"] == model.metadata.weights_sha256
    for key, value in metrics.as_dict().items():
        assert report["metrics"][key] == pytest.approx(value, abs=1e-12), key

    report_records = report["records"]
    assert len(report_records) == metrics.n
    for record, report_record in zip(dataset["records"], report_records, strict=True):
        assert report_record["id"] == record["id"]
        pred, _uncertainty, _in_domain, _warning = model.predict(Chem.MolFromSmiles(record["smiles"]))
        assert report_record["predicted_logS"] == pytest.approx(pred, abs=1e-12), record["id"]

    errors = [record["error"] for record in report_records]
    assert bootstrap_rmse_interval(errors) == pytest.approx(tuple(report["rmse_95pct_bootstrap_ci"]), abs=1e-12)

    assert model.metadata.validation["status"] == "measured"
    assert model.metadata.validation["report_json"] == "docs/validation/esol-solubility.json"
