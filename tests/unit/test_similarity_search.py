"""Tanimoto search: CPU/GPU parity, ranking semantics and honest engine selection."""

from __future__ import annotations

import numpy as np
import pytest
from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator

from hcs_discovery.core.errors import ValidationError
from hcs_discovery.gpu.device import probe_gpu, select_adapter
from hcs_discovery.similarity import (
    GpuUnavailableError,
    ParityError,
    TanimotoIndex,
    clear_device_cache,
    resolve_engine,
    similarity_runtime_fingerprint,
    tanimoto_search,
)

SMILES = [
    "CC(=O)Oc1ccccc1C(=O)O",  # aspirin
    "CN1CCC[C@H]1c1cccnc1",  # nicotine
    "c1ccccc1",  # benzene
    "CC(C)Cc1ccc(cc1)C(C)C(=O)O",  # ibuprofen
    "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",  # caffeine
    "not_a_smiles",
]
QUERY = SMILES[0]

_generator = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)


@pytest.fixture(autouse=True)
def _fresh_probe_cache():
    clear_device_cache()
    yield
    clear_device_cache()


def rdkit_scores(query: str, smiles: list[str]) -> list[float]:
    q = Chem.MolFromSmiles(query)
    assert q is not None
    query_fp = _generator.GetFingerprint(q)
    out: list[float] = []
    for smi in smiles:
        mol = Chem.MolFromSmiles(smi)
        out.append(
            0.0 if mol is None else float(DataStructs.TanimotoSimilarity(query_fp, _generator.GetFingerprint(mol)))
        )
    return out


def test_cpu_scores_are_bit_identical_to_rdkit():
    with TanimotoIndex(SMILES, prefer="cpu") as index:
        assert index.engine.name == "cpu"
        scores = index.scores(QUERY)
    reference = rdkit_scores(QUERY, SMILES)
    # Exact double equality, not a tolerance: the score is the same integer division.
    assert list(scores) == reference


def test_invalid_smiles_keeps_its_row_and_is_never_a_hit():
    with TanimotoIndex(SMILES, prefer="cpu") as index:
        assert index.n == len(SMILES)
        assert index.n_valid == len(SMILES) - 1
        result = index.search(QUERY, threshold=0.0)
    assert result.scores[-1] == 0.0
    assert all(hit.index != len(SMILES) - 1 for hit in result.hits)


def test_hits_are_ranked_descending_and_ties_break_on_lower_index():
    duplicated = ["c1ccccc1", "CCO", "c1ccccc1"]
    with TanimotoIndex(duplicated, prefer="cpu") as index:
        result = index.search("c1ccccc1", threshold=0.0)
    similarities = [hit.similarity for hit in result.hits]
    assert similarities == sorted(similarities, reverse=True)
    assert [hit.index for hit in result.hits] == [0, 2, 1]


def test_k_and_threshold_semantics():
    with TanimotoIndex(SMILES, prefer="cpu") as index:
        top2 = index.search(QUERY, k=2)
        assert [hit.index for hit in top2.hits] == [0, 3]
        exclusive = index.search(QUERY, threshold=1.0)
        assert [hit.index for hit in exclusive.hits] == [0]  # threshold is inclusive
        above = index.search(QUERY, threshold=0.126)
        assert [hit.index for hit in above.hits] == [0, 3]  # 0.125 is below, 0.195 is above
        with pytest.raises(ValidationError):
            index.search(QUERY, k=0)
        with pytest.raises(ValidationError):
            index.search(QUERY, threshold=1.5)


def test_invalid_query_is_a_validation_error():
    with TanimotoIndex(SMILES, prefer="cpu") as index, pytest.raises(ValidationError):
        index.scores("not_a_smiles")


def test_explicit_gpu_without_hardware_raises_instead_of_falling_back(monkeypatch):
    monkeypatch.setattr(
        "hcs_discovery.similarity.probe_gpu",
        lambda: {"status": "software_only", "detail": "No hardware GPU adapter was found."},
    )
    with pytest.raises(GpuUnavailableError):
        resolve_engine("gpu")
    assert resolve_engine("cpu").name == "cpu"
    auto = resolve_engine("auto")
    assert auto.name == "cpu" and "No hardware GPU adapter" in auto.detail


def test_non_default_fingerprint_uses_the_cpu_reference(monkeypatch):
    monkeypatch.setattr(
        "hcs_discovery.similarity.probe_gpu",
        lambda: {"status": "available", "adapter": "Fake", "backend": "Vulkan"},
    )
    with TanimotoIndex(SMILES, prefer="auto", bits=1024) as index:
        assert index.engine.name == "cpu"
        assert "1024" in index.engine.detail
    with pytest.raises(ValidationError):
        TanimotoIndex(SMILES, prefer="gpu", radius=3)


def test_runtime_fingerprint_names_engine_and_adapter(monkeypatch):
    fake = {"status": "available", "adapter": "AMD Radeon(TM) Graphics", "backend": "Vulkan"}
    monkeypatch.setattr("hcs_discovery.similarity.probe_gpu", lambda: fake)
    assert similarity_runtime_fingerprint("auto") == {
        "similarity_engine": "gpu",
        "similarity_mode": "gpu",
        "similarity_backend": "Vulkan",
        "similarity_adapter": "AMD Radeon(TM) Graphics",
    }
    assert similarity_runtime_fingerprint("cpu")["similarity_engine"] == "cpu"
    assert similarity_runtime_fingerprint("auto", "cpu")["similarity_mode"] == "cpu"


def test_one_shot_search_result_is_self_describing():
    result = tanimoto_search(SMILES, QUERY, k=1, prefer="cpu")
    assert result.n == len(SMILES)
    assert result.n_hits == 1
    assert result.parity_checked is False
    assert result.engine.label == "cpu"
    assert set(result.timings_ms) == {"score", "rank", "total"}


# --------------------------------------------------------------------------- GPU


@pytest.mark.gpu
def test_gpu_counts_and_scores_are_bit_exact_against_the_cpu_reference():
    if select_adapter() is None:
        pytest.skip("no hardware GPU adapter")
    with TanimotoIndex(SMILES, prefer="gpu", verify=True) as index:
        assert index.engine.name == "gpu"
        assert index.engine.backend in {"Vulkan", "D3D12", "Metal"}
        reference = rdkit_scores(QUERY, SMILES)
        assert list(index.scores(QUERY)) == reference
        result = index.search(QUERY, k=3)
        assert result.parity_checked is True


@pytest.mark.gpu
def test_gpu_parity_failure_raises_instead_of_returning_numbers(monkeypatch):
    if select_adapter() is None:
        pytest.skip("no hardware GPU adapter")
    from hcs_discovery.gpu.engine import GpuResult

    with TanimotoIndex(SMILES, prefer="gpu", verify=True) as index:
        engine = index._gpu
        assert engine is not None
        real = engine.counts

        def corrupt(query, library, **kwargs):
            result = real(query, library, **kwargs)
            return GpuResult(result.inter + np.uint32(1), result.union, result.total_ms, result.adapter, result.backend)

        monkeypatch.setattr(engine, "counts", corrupt)
        with pytest.raises(ParityError):
            index.scores(QUERY)


@pytest.mark.gpu
def test_probe_reports_hardware_only():
    probe = probe_gpu()
    assert probe["status"] in {"available", "software_only", "unavailable"}
    if probe["status"] == "available":
        assert probe["backend"] in {"Vulkan", "D3D12", "Metal"}


# --------------------------------------------------------------------------- hybrid
HYBRID_SMILES = [
    "CC(=O)Oc1ccccc1C(=O)O",
    "CN1CCC[C@H]1c1cccnc1",
    "c1ccccc1",
    "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
    "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
]


@pytest.mark.gpu
def test_hybrid_split_is_bit_exact_and_merges_in_order():
    if select_adapter() is None:
        pytest.skip("no hardware GPU adapter")
    library = [HYBRID_SMILES[index % len(HYBRID_SMILES)] for index in range(120)]
    with TanimotoIndex(library, prefer="auto", boost="hybrid", workers=2) as hybrid:
        assert hybrid.engine.mode == "hybrid"
        assert hybrid.engine.workers == 2
        hybrid_scores = hybrid.scores(QUERY)
    with TanimotoIndex(library, prefer="cpu") as reference:
        cpu_scores = reference.scores(QUERY)
    assert list(hybrid_scores) == list(cpu_scores)


def test_boost_cpu_never_touches_the_gpu(monkeypatch):
    monkeypatch.setattr(
        "hcs_discovery.similarity.probe_gpu",
        lambda: {"status": "available", "adapter": "Fake", "backend": "Vulkan", "adapter_type": "IntegratedGPU"},
    )
    with TanimotoIndex(SMILES, prefer="auto", boost="cpu") as index:
        assert index.engine.name == "cpu" and index.engine.mode == "cpu"


def test_hybrid_without_hardware_falls_back_to_cpu(monkeypatch):
    monkeypatch.setattr(
        "hcs_discovery.similarity.probe_gpu",
        lambda: {"status": "software_only", "detail": "No hardware GPU adapter was found."},
    )
    with TanimotoIndex(SMILES, prefer="auto", boost="hybrid") as index:
        assert index.engine.name == "cpu"
        assert "No hardware GPU adapter" in index.engine.detail
