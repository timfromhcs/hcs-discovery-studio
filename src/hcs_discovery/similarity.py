"""Tanimoto similarity search: a vendor-neutral GPU path with an exact CPU reference.

The heavy loop is the same WGSL kernel the browser runs (``gpu/kernels/tanimoto.wgsl``);
``wgpu-py`` executes it through Vulkan, D3D12 or Metal. Fingerprints are Morgan/ECFP
2048-bit packed into 64 little-endian ``uint32`` words, exactly as RDKit produces them.

Evidence discipline, in the order the code applies it:

1. Integer popcounts are exact, so a GPU result must equal the CPU result bit for bit.
   ``verify=True`` (the default) compares every count against ``gpu.cpu.cpu_counts``
   and raises instead of returning a number when they differ.
2. Similarity is ``intersection / union`` in float64, which is the same double
   division RDKit's ``TanimotoSimilarity`` performs; an accelerated search therefore
   reports the same values as the RDKit path, not merely values within a tolerance.
3. An empty union is 0.0, matching RDKit.
4. A software adapter is never used (see ``gpu.device.select_adapter``), and asking
   for ``gpu`` explicitly raises when no hardware adapter exists instead of silently
   falling back.

Only 2048-bit/radius-2 fingerprints have a kernel. Other widths are served by the
CPU reference, and the engine detail says so.
"""

from __future__ import annotations

import os
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from itertools import pairwise
from typing import Any, Literal

import numpy as np

from hcs_discovery.core.errors import ValidationError
from hcs_discovery.gpu.cpu import cpu_counts
from hcs_discovery.gpu.device import probe_gpu
from hcs_discovery.gpu.fingerprints import BITS, RADIUS, WORDS, pack_smiles

EnginePreference = Literal["auto", "cpu", "gpu"]
BoostPreference = Literal["auto", "gpu", "cpu", "hybrid"]
SUPPORTED_RADIUS = RADIUS
SUPPORTED_BITS = BITS
# Below this library size the coordination overhead of a hybrid split dominates.
HYBRID_MIN_ROWS = 20_000
_HYBRID_MAX_WORKERS = 4

__all__ = [
    "BITS",
    "RADIUS",
    "SUPPORTED_BITS",
    "SUPPORTED_RADIUS",
    "WORDS",
    "BoostPreference",
    "Engine",
    "GpuUnavailableError",
    "Hit",
    "ParityError",
    "SearchResult",
    "TanimotoIndex",
    "clear_device_cache",
    "device_probe",
    "resolve_engine",
    "similarity_runtime_fingerprint",
    "tanimoto_search",
]


class GpuUnavailableError(RuntimeError):
    """An explicit GPU request found no hardware adapter."""


class ParityError(RuntimeError):
    """The GPU counts differ from the CPU reference; no result is returned."""


@dataclass(frozen=True)
class Engine:
    """Which engine produced a result, and on what."""

    name: Literal["cpu", "gpu"]
    detail: str
    adapter: str | None = None
    backend: str | None = None
    adapter_type: str | None = None
    mode: Literal["gpu", "cpu", "hybrid"] = "gpu"
    workers: int = 1

    @property
    def label(self) -> str:
        if self.mode == "hybrid" and self.adapter:
            return f"hybrid ({self.backend or 'unknown backend'}, {self.adapter} + {self.workers} CPU threads)"
        if self.name == "gpu" and self.adapter:
            return f"gpu ({self.backend or 'unknown backend'}, {self.adapter})"
        return self.name


@dataclass(frozen=True)
class Hit:
    index: int
    similarity: float


@dataclass(frozen=True)
class SearchResult:
    scores: np.ndarray
    hits: tuple[Hit, ...]
    engine: Engine
    n: int
    parity_checked: bool
    timings_ms: dict[str, float]

    @property
    def n_hits(self) -> int:
        return len(self.hits)


def resolve_engine(prefer: EnginePreference = "auto", boost: BoostPreference = "auto") -> Engine:
    """Return the engine a search would use, without touching any data."""
    if prefer == "cpu" or boost == "cpu":
        return Engine("cpu", "CPU reference requested", mode="cpu")
    probe = device_probe()
    if probe.get("status") == "available":
        adapter_type = probe.get("adapter_type")
        return Engine(
            "gpu",
            "Hardware adapter selected",
            adapter=probe.get("adapter"),
            backend=probe.get("backend"),
            adapter_type=adapter_type,
            mode="gpu",
        )
    if prefer == "gpu":
        raise GpuUnavailableError(str(probe.get("detail") or "no hardware GPU adapter"))
    return Engine("cpu", str(probe.get("detail") or "no hardware GPU adapter"), mode="cpu")


@lru_cache(maxsize=1)
def device_probe() -> dict[str, Any]:
    """Cached adapter probe: enumerating adapters costs roughly 0.3 s per call."""
    return probe_gpu()


def clear_device_cache() -> None:
    """Forget the cached probe (used by tests and when a device appears at runtime)."""
    device_probe.cache_clear()


def _scores_from_counts(inter: np.ndarray, union: np.ndarray) -> np.ndarray:
    """float64 Tanimoto from exact integer popcounts (same double division as RDKit)."""
    out = np.zeros(inter.shape, dtype=np.float64)
    nonzero = union > 0
    out[nonzero] = inter[nonzero].astype(np.float64) / union[nonzero].astype(np.float64)
    return out


class TanimotoIndex:
    """Packed fingerprints scored against one query.

    ``prefer="auto"`` uses a hardware adapter when the host has one and the CPU
    reference otherwise. The instance owns a GPU device while it is open; use it as
    a context manager or call :meth:`close`.
    """

    def __init__(
        self,
        smiles: Sequence[str],
        *,
        prefer: EnginePreference = "auto",
        boost: BoostPreference = "auto",
        verify: bool = True,
        bits: int = SUPPORTED_BITS,
        radius: int = SUPPORTED_RADIUS,
        workers: int | None = None,
    ) -> None:
        packed, valid = pack_smiles(smiles)
        self._install(
            packed, valid, prefer=prefer, boost=boost, verify=verify, bits=bits, radius=radius, workers=workers
        )

    @classmethod
    def from_packed(
        cls,
        packed: np.ndarray,
        valid: np.ndarray | None = None,
        *,
        prefer: EnginePreference = "auto",
        boost: BoostPreference = "auto",
        verify: bool = True,
        workers: int | None = None,
    ) -> TanimotoIndex:
        """Build an index from already packed fingerprints (same kernel, no RDKit)."""
        library = np.ascontiguousarray(packed, dtype=np.uint32)
        if library.ndim != 2 or library.shape[1] != WORDS:
            raise ValidationError(
                "Packed fingerprints must have shape (n, 64) uint32.",
                details={"shape": list(library.shape)},
            )
        index = cls.__new__(cls)
        mask = np.ones(library.shape[0], dtype=bool) if valid is None else np.asarray(valid, dtype=bool)
        if mask.shape[0] != library.shape[0]:
            raise ValidationError("valid must have one entry per fingerprint.")
        index._install(
            library,
            mask,
            prefer=prefer,
            boost=boost,
            verify=verify,
            bits=SUPPORTED_BITS,
            radius=SUPPORTED_RADIUS,
            workers=workers,
        )
        return index

    def _install(
        self,
        packed: np.ndarray,
        valid: np.ndarray,
        *,
        prefer: EnginePreference,
        boost: BoostPreference,
        verify: bool,
        bits: int,
        radius: int,
        workers: int | None,
    ) -> None:
        self._packed = packed
        self._valid = valid
        self._n = int(packed.shape[0])
        self._verify = verify
        self._workers = workers
        self._engine = self._choose(prefer, bits, radius, boost)
        self._gpu = None
        if self._engine.name == "gpu":
            from hcs_discovery.gpu.engine import GpuEngine

            try:
                self._gpu = GpuEngine()
            except Exception as exc:
                if prefer == "gpu":
                    raise GpuUnavailableError(str(exc)) from exc
                self._engine = Engine("cpu", f"GPU initialisation failed: {exc}", mode="cpu")
        if self._engine.name == "gpu" and boost in {"auto", "hybrid"}:
            self._engine = self._maybe_hybrid(boost, prefer)

    def _cpu_workers(self) -> int:
        if self._workers is not None:
            return max(1, self._workers)
        return max(1, min(_HYBRID_MAX_WORKERS, (os.cpu_count() or 2) - 1))

    def _maybe_hybrid(self, boost: BoostPreference, prefer: EnginePreference) -> Engine:
        """Hybrid splits GPU and CPU work; auto only when a measurement says it pays off."""
        if boost == "gpu" or prefer != "auto":
            return self._engine
        if boost == "hybrid":
            return self._as_hybrid()
        if self._n < HYBRID_MIN_ROWS or self._engine.adapter_type != "IntegratedGPU":
            return self._engine
        if self._hybrid_helps():
            return self._as_hybrid()
        return Engine(
            "gpu",
            "GPU-only: the CPU share is more than four times slower than this adapter",
            adapter=self._engine.adapter,
            backend=self._engine.backend,
            adapter_type=self._engine.adapter_type,
            mode="gpu",
        )

    def _as_hybrid(self) -> Engine:
        return Engine(
            "gpu",
            "GPU and CPU score different slices of the library",
            adapter=self._engine.adapter,
            backend=self._engine.backend,
            adapter_type=self._engine.adapter_type,
            mode="hybrid",
            workers=self._cpu_workers(),
        )

    def _hybrid_helps(self) -> bool:
        """Measure one small GPU dispatch against the CPU reference and decide.

        The cost of a popcount scan is data-independent, so a fixed query and a
        capped sample are enough. A split can only help when the CPU share is
        within a small factor of the GPU; otherwise the CPU work is pure overhead.
        """
        assert self._gpu is not None
        sample = min(self._n, 8192)
        library = self._packed[:sample]
        query = np.zeros(WORDS, dtype=np.uint32)
        self._gpu.counts(query, library[: min(sample, 64)])  # warm-up
        started = time.perf_counter()
        self._gpu.counts(query, library)
        gpu_ms = (time.perf_counter() - started) * 1000.0
        started = time.perf_counter()
        cpu_counts(query, library)
        cpu_ms = (time.perf_counter() - started) * 1000.0
        return cpu_ms <= 4.0 * gpu_ms

    def _choose(self, prefer: EnginePreference, bits: int, radius: int, boost: BoostPreference) -> Engine:
        if (radius, bits) != (SUPPORTED_RADIUS, SUPPORTED_BITS):
            if prefer == "gpu":
                raise ValidationError(
                    "The GPU kernel is fixed at Morgan/ECFP radius=2, 2048 bits.",
                    details={"radius": radius, "bits": bits},
                )
            return Engine(
                "cpu",
                f"CPU reference: kernel is {SUPPORTED_RADIUS}/{SUPPORTED_BITS}, not {radius}/{bits}",
                mode="cpu",
            )
        return resolve_engine(prefer, boost)

    # -- properties -------------------------------------------------------
    @property
    def engine(self) -> Engine:
        return self._engine

    @property
    def n(self) -> int:
        return self._n

    @property
    def n_valid(self) -> int:
        return int(self._valid.sum())

    @property
    def packed(self) -> np.ndarray:
        return self._packed

    @property
    def valid(self) -> np.ndarray:
        return self._valid

    # -- scoring ----------------------------------------------------------
    def counts(self, query_smiles: str) -> tuple[np.ndarray, np.ndarray]:
        """Exact intersection/union popcounts for every row (GPU when available)."""
        return self.counts_for(self._query_fingerprint(query_smiles))

    def counts_for(self, query: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Same as :meth:`counts`, for an already packed query fingerprint."""
        fingerprint = np.ascontiguousarray(query, dtype=np.uint32).reshape(-1)
        if fingerprint.shape[0] != WORDS:
            raise ValidationError(
                "A query fingerprint must be 64 uint32 words.",
                details={"words": int(fingerprint.shape[0])},
            )
        if self._gpu is not None and self._engine.mode == "hybrid":
            inter, union = self._hybrid_counts(fingerprint)
        elif self._gpu is not None:
            result = self._gpu.counts(fingerprint, self._packed)
            inter, union = result.inter, result.union
        else:
            return cpu_counts(fingerprint, self._packed)
        if self._verify:
            reference_inter, reference_union = cpu_counts(fingerprint, self._packed)
            if not (np.array_equal(inter, reference_inter) and np.array_equal(union, reference_union)):
                raise ParityError(
                    "GPU Tanimoto counts differ from the CPU reference; no result was returned.",
                    # the counts themselves are not attached: they would be huge
                )
        return inter, union

    def _hybrid_counts(self, query: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Score the library with the GPU and the CPU at the same time, then merge in order."""
        assert self._gpu is not None
        n = self._n
        integrated = self._engine.adapter_type == "IntegratedGPU"
        # The GPU is the faster engine on every host measured so far, so it takes the
        # larger share; the CPU fills the rest without waiting for a dispatch.
        gpu_rows = min(n, max(64, int(n * (0.7 if integrated else 0.85))))
        workers = max(1, self._engine.workers)
        inter = np.empty(n, dtype=np.uint32)
        union = np.empty(n, dtype=np.uint32)
        bounds = np.linspace(gpu_rows, n, workers + 1, dtype=int)
        chunks = [(start, stop) for start, stop in pairwise(int(value) for value in bounds) if stop > start]
        with ThreadPoolExecutor(max_workers=max(1, len(chunks))) as pool:
            cpu_futures = [
                (pool.submit(cpu_counts, query, self._packed[start:stop]), start, stop) for start, stop in chunks
            ]
            # The GPU dispatch runs on this thread: it is a driver call, and keeping it
            # out of the pool means no worker is blocked while the device works.
            gpu_inter, gpu_union = self._gpu_counts_slice(query, gpu_rows, 0)
            inter[:gpu_rows] = gpu_inter
            union[:gpu_rows] = gpu_union
            for future, start, stop in cpu_futures:
                part_inter, part_union = future.result()
                inter[start:stop] = part_inter
                union[start:stop] = part_union
        return inter, union

    def _gpu_counts_slice(self, query: np.ndarray, count: int, offset: int) -> tuple[np.ndarray, np.ndarray]:
        assert self._gpu is not None
        result = self._gpu.counts(query, self._packed[offset : offset + count])
        return result.inter, result.union

    def scores(self, query_smiles: str) -> np.ndarray:
        return _scores_from_counts(*self.counts(query_smiles))

    def search(
        self,
        query_smiles: str,
        *,
        k: int | None = None,
        threshold: float | None = None,
    ) -> SearchResult:
        if k is not None and k < 1:
            raise ValidationError("k must be at least 1.")
        if threshold is not None and not 0.0 <= threshold <= 1.0:
            raise ValidationError("threshold must be within 0-1.")
        started = time.perf_counter()
        inter, union = self.counts(query_smiles)
        counted = time.perf_counter()
        scores = _scores_from_counts(inter, union)
        hits = _rank_scores(scores, self._valid, k=k, threshold=threshold)
        finished = time.perf_counter()
        return SearchResult(
            scores=scores,
            hits=hits,
            engine=self._engine,
            n=self._n,
            parity_checked=self._gpu is not None and self._verify,
            timings_ms={
                "score": (counted - started) * 1000.0,
                "rank": (finished - counted) * 1000.0,
                "total": (finished - started) * 1000.0,
            },
        )

    # -- lifecycle --------------------------------------------------------
    def close(self) -> None:
        if self._gpu is not None:
            self._gpu.release_library()
            self._gpu = None

    def __enter__(self) -> TanimotoIndex:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # -- internals --------------------------------------------------------
    def _query_fingerprint(self, query_smiles: str) -> np.ndarray:
        packed, valid = pack_smiles([query_smiles])
        if not bool(valid[0]):
            raise ValidationError("Query SMILES is invalid.", details={"smiles": query_smiles})
        return packed[0].copy()


def _rank_scores(scores: np.ndarray, valid: np.ndarray, *, k: int | None, threshold: float | None) -> tuple[Hit, ...]:
    candidates = np.flatnonzero(valid)
    if threshold is not None:
        candidates = candidates[scores[candidates] >= threshold]
    if candidates.size == 0:
        return ()
    # Descending similarity, ascending index for ties (deterministic, and the same
    # order a stable sort of the full array would produce).
    order = np.lexsort((candidates, -scores[candidates]))
    ranked = candidates[order]
    if k is not None:
        ranked = ranked[:k]
    return tuple(Hit(int(i), float(scores[i])) for i in ranked)


def tanimoto_search(
    smiles: Sequence[str],
    query_smiles: str,
    *,
    k: int | None = None,
    threshold: float | None = None,
    prefer: EnginePreference = "auto",
    boost: BoostPreference = "auto",
    verify: bool = True,
) -> SearchResult:
    """One-shot search; builds the index, scores and closes the device."""
    with TanimotoIndex(smiles, prefer=prefer, boost=boost, verify=verify) as index:
        return index.search(query_smiles, k=k, threshold=threshold)


def similarity_runtime_fingerprint(
    prefer: EnginePreference = "auto", boost: BoostPreference = "auto"
) -> dict[str, str]:
    """Cache-key input: which engine and adapter would produce the values."""
    try:
        engine = resolve_engine(prefer, boost)
    except GpuUnavailableError as exc:
        return {"similarity_engine": "unavailable", "similarity_detail": str(exc)}
    return {
        "similarity_engine": engine.name,
        "similarity_mode": engine.mode,
        "similarity_backend": engine.backend or "none",
        "similarity_adapter": engine.adapter or "none",
    }
