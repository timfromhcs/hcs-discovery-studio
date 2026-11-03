"""Parity + speed benchmark for the shared Tanimoto kernel (schema ``hcs.gpu-bench.v1``).

Order of claims: **parity first** (integer counts bit-exact against numpy, float32 within
1e-6 of RDKit ``BulkTanimotoSimilarity``), speed second. Speed is a measured number on the
named adapter, never a promise. Without a hardware adapter the status is ``skipped``.
"""

from __future__ import annotations

import statistics
import subprocess
import time
from pathlib import Path
from typing import Any

import numpy as np
from rdkit import DataStructs

from hcs_discovery.gpu.cpu import cpu_counts, ratio
from hcs_discovery.gpu.device import probe_gpu
from hcs_discovery.gpu.fingerprints import WORDS, pack_smiles

SCHEMA = "hcs.gpu-bench.v1"
BASE_SMILES = [
    "CC(=O)Oc1ccccc1C(=O)O",
    "CN1CCC[C@H]1c1cccnc1",
    "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
    "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
    "O=C(O)c1ccccc1O",
    "CC(=O)Nc1ccc(O)cc1",
    "CCN(CC)CCNC(=O)c1ccc(N)cc1",
    "c1ccc2c(c1)cc[nH]2",
    "COc1ccc2[nH]cc(CCNC(C)=O)c2c1",
    "CC1=CC=C(C=C1)S(=O)(=O)N",
]
PARITY_TOLERANCE = 1e-6


def synthetic_library(n: int, seed: int) -> np.ndarray:
    """Deterministic ECFP-like library: real base fingerprints plus sparse random bit flips."""
    base, _ = pack_smiles(BASE_SMILES)
    rng = np.random.default_rng(seed)
    lib = base[rng.integers(0, len(base), size=n)].copy()
    for _ in range(3):  # AND of three random words ~ 12.5 % density flips
        lib ^= (
            rng.integers(0, 2**32, size=(n, WORDS), dtype=np.uint64).astype(np.uint32)
            & rng.integers(0, 2**32, size=(n, WORDS), dtype=np.uint64).astype(np.uint32)
            & rng.integers(0, 2**32, size=(n, WORDS), dtype=np.uint64).astype(np.uint32)
        )
    return lib


def _to_rdkit(packed: np.ndarray) -> list[Any]:
    bits = np.unpackbits(packed.view(np.uint8), axis=1, bitorder="little")
    table = bytes.maketrans(b"\x00\x01", b"01")
    return [DataStructs.CreateFromBitString(row.tobytes().translate(table).decode("ascii")) for row in bits]


def _git_commit() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def run_bench(n_library: int = 100_000, repeats: int = 5, seed: int = 0) -> dict[str, Any]:
    probe = probe_gpu()
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "skipped",
        "detail": probe["detail"],
        "adapter": probe.get("adapter"),
        "backend": probe.get("backend"),
        "n_library": n_library,
        "repeats": repeats,
        "commit": _git_commit(),
        "parity": None,
        "numpy_ms": None,
        "rdkit_ms": None,
        "gpu_ms": None,
        "speedup_vs_rdkit": None,
        "speedup_vs_numpy": None,
    }
    if probe["status"] != "available":
        return report

    from hcs_discovery.gpu.engine import GpuEngine

    lib = synthetic_library(n_library, seed)
    query = lib[0].copy()

    started = time.perf_counter()
    inter_ref, union_ref = cpu_counts(query, lib)
    numpy_ms = (time.perf_counter() - started) * 1000.0

    fps = _to_rdkit(lib)
    started = time.perf_counter()
    rdkit_sim = np.asarray(DataStructs.BulkTanimotoSimilarity(fps[0], fps), dtype=np.float32)
    rdkit_ms = (time.perf_counter() - started) * 1000.0

    engine = GpuEngine()
    engine.counts(query, lib[:64])  # warm-up: pipeline and driver caches
    timings: list[float] = []
    result = None
    for _ in range(repeats):
        result = engine.counts(query, lib)
        timings.append(result.total_ms)
    assert result is not None
    gpu_ms = statistics.median(timings)

    # Resident mode: the library stays on the GPU, only the 256-byte query moves (screening use case).
    resident_ms: float | None = None
    resident_exact = True
    if n_library <= engine.max_chunk:
        engine.load_library(lib)
        engine.query_resident(query)  # warm-up
        r_timings = []
        for k in range(repeats):
            probe_q = lib[k]
            res = engine.query_resident(probe_q)
            r_timings.append(res.total_ms)
            ri, ru = cpu_counts(probe_q, lib) if k == 0 else (res.inter, res.union)
            resident_exact = resident_exact and bool(np.array_equal(res.inter, ri) and np.array_equal(res.union, ru))
        resident_ms = statistics.median(r_timings)
        engine.release_library()

    exact = bool(np.array_equal(result.inter, inter_ref) and np.array_equal(result.union, union_ref))
    max_err = float(np.max(np.abs(ratio(result.inter, result.union) - rdkit_sim)))
    exact = exact and resident_exact
    ok = exact and max_err <= PARITY_TOLERANCE
    report.update(
        status="passed" if ok else "failed",
        detail="GPU counts are bit-exact and agree with RDKit." if ok else "Parity violated.",
        adapter=result.adapter,
        backend=result.backend,
        parity={"exact_counts": exact, "max_abs_err_vs_rdkit": max_err, "tolerance": PARITY_TOLERANCE},
        numpy_ms=round(numpy_ms, 3),
        rdkit_ms=round(rdkit_ms, 3),
        gpu_ms=round(gpu_ms, 3),
        gpu_ms_all=[round(t, 3) for t in timings],
        speedup_vs_rdkit=round(rdkit_ms / gpu_ms, 2),
        speedup_vs_numpy=round(numpy_ms / gpu_ms, 2),
        gpu_resident_ms=None if resident_ms is None else round(resident_ms, 3),
        speedup_resident_vs_rdkit=None if resident_ms is None else round(rdkit_ms / resident_ms, 2),
        timing_note=(
            "gpu_ms = median wall time of upload + dispatch + readback (end-to-end, includes transfers). "
            "gpu_resident_ms = same with the library already resident on the GPU (query upload + dispatch + "
            "readback). rdkit_ms = RDKit BulkTanimotoSimilarity (SIMD, single thread)."
        ),
    )
    return report


def write_report(report: dict[str, Any], path: Path) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
