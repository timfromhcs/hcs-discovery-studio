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


# --------------------------------------------------------------------------- BitBound
VARIED_LIBRARY = [
    "c1ccccc1",
    "Cc1ccccc1",
    "Clc1ccccc1",
    "Oc1ccccc1",
    "Nc1ccccc1",
    "CCO",
    "CCN",
    "CC(=O)Oc1ccccc1C(=O)O",
    "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
    "CN1CCC[C@H]1c1cccnc1",
    "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
    "c1ccc2c(c1)cc[nH]2",
    "COc1ccc2[nH]cc(CCNC(C)=O)c2c1",
    "CC1=CC=C(C=C1)S(=O)(=O)N",
    "O=C(O)c1ccccc1O",
    "CC(=O)Nc1ccc(O)cc1",
] * 2  # duplicates make the tie-breaking and the bound interesting


@pytest.mark.parametrize("threshold", [0.0, 0.05, 0.2, 0.4, 0.7, 0.9, 1.0])
def test_threshold_prefilter_returns_exactly_the_full_scan(threshold):
    with TanimotoIndex(VARIED_LIBRARY, prefer="cpu") as index:
        full = index.search(QUERY, threshold=threshold)
        pruned = index.threshold_hits(QUERY, threshold)
    assert [(hit.index, hit.similarity) for hit in pruned.hits] == [(hit.index, hit.similarity) for hit in full.hits]
    assert pruned.candidates <= len(VARIED_LIBRARY)
    assert pruned.prefiltered is (threshold > 0)


def test_threshold_prefilter_can_skip_the_whole_library():
    with TanimotoIndex(["CCO", "CCN", "CCC"], prefer="cpu") as index:
        result = index.threshold_hits("c1ccccc1", 0.9)
    assert result.hits == ()
    assert result.candidates == 0
    assert result.timings_ms["score"] == 0.0


def test_threshold_zero_does_not_pretend_to_prune():
    with TanimotoIndex(VARIED_LIBRARY, prefer="cpu") as index:
        result = index.threshold_hits(QUERY, 0.0)
    assert result.prefiltered is False
    assert result.candidates == len(VARIED_LIBRARY)


def test_the_bound_never_excludes_a_true_hit():
    rng = np.random.default_rng(11)
    for _ in range(15):
        library = rng.integers(0, 2**32, size=(40, 64), dtype=np.uint64).astype(np.uint32)
        index = TanimotoIndex.from_packed(library, prefer="cpu", verify=False)
        query = library[rng.integers(0, 40)]
        inter, union = index.counts_for(query)
        actual = np.divide(inter, union, out=np.zeros(len(library)), where=union > 0)
        a = int(np.unpackbits(query.view(np.uint8), bitorder="little").sum())
        b = np.unpackbits(library.view(np.uint8), axis=1, bitorder="little").sum(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            bound = np.where((a > 0) & (b > 0), np.minimum(a, b) / np.maximum(a, b), 0.0)
        assert np.all(actual <= bound + 1e-12), "the BitBound must be an upper bound"
        index.close()


@pytest.mark.gpu
def test_gpu_threshold_prefilter_matches_the_cpu_full_scan():
    if select_adapter() is None:
        pytest.skip("no hardware GPU adapter")
    with TanimotoIndex(VARIED_LIBRARY, prefer="auto") as index:
        gpu = index.threshold_hits(QUERY, 0.2)
    with TanimotoIndex(VARIED_LIBRARY, prefer="cpu") as reference:
        full = reference.search(QUERY, threshold=0.2)
    assert [(hit.index, hit.similarity) for hit in gpu.hits] == [(hit.index, hit.similarity) for hit in full.hits]
