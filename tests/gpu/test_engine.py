from __future__ import annotations

import builtins

import numpy as np
import pytest

from hcs_discovery.gpu.cpu import cpu_counts
from hcs_discovery.gpu.device import probe_gpu, select_adapter

pytestmark = pytest.mark.gpu


def _library(n: int, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    a = rng.integers(0, 2**32, size=(n, 64), dtype=np.uint64).astype(np.uint32)
    b = rng.integers(0, 2**32, size=(n, 64), dtype=np.uint64).astype(np.uint32)
    return a & b  # sparser, like ECFP


@pytest.fixture(scope="module")
def engine():
    if select_adapter() is None:
        pytest.skip("no hardware GPU adapter")
    from hcs_discovery.gpu.engine import GpuEngine

    return GpuEngine()


@pytest.mark.parametrize("n", [1, 63, 64, 65, 100_001])
def test_gpu_counts_are_bit_exact(engine, n):
    lib = _library(n)
    q = lib[0].copy()
    res = engine.counts(q, lib)
    inter, union = cpu_counts(q, lib)
    assert np.array_equal(res.inter, inter) and np.array_equal(res.union, union)


def test_chunked_equals_unchunked(engine):
    lib = _library(5000)
    a = engine.counts(lib[3], lib)
    b = engine.counts(lib[3], lib, chunk=1000)
    assert np.array_equal(a.inter, b.inter) and np.array_equal(a.union, b.union)


def test_all_zero_union_zero(engine):
    z = np.zeros((70, 64), dtype=np.uint32)
    res = engine.counts(z[0], z)
    assert (res.union == 0).all()


def test_probe_unavailable_without_wgpu(monkeypatch):
    real = builtins.__import__

    def fake(name, *args, **kwargs):
        if name == "wgpu":
            raise ImportError("blocked")
        return real(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake)
    assert probe_gpu()["status"] == "unavailable"
