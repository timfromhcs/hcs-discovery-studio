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

import time
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

import numpy as np

from hcs_discovery.core.errors import ValidationError
from hcs_discovery.gpu.cpu import cpu_counts
from hcs_discovery.gpu.device import probe_gpu
from hcs_discovery.gpu.fingerprints import BITS, RADIUS, WORDS, pack_smiles

EnginePreference = Literal["auto", "cpu", "gpu"]
SUPPORTED_RADIUS = RADIUS
SUPPORTED_BITS = BITS

__all__ = [
    "BITS",
    "RADIUS",
    "SUPPORTED_BITS",
    "SUPPORTED_RADIUS",
    "WORDS",
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

    @property
    def label(self) -> str:
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


def resolve_engine(prefer: EnginePreference = "auto") -> Engine:
    """Return the engine a search would use, without touching any data."""
    if prefer == "cpu":
        return Engine("cpu", "CPU reference requested")
    probe = device_probe()
    if probe.get("status") == "available":
        return Engine(
            "gpu",
            "Hardware adapter selected",
            adapter=probe.get("adapter"),
            backend=probe.get("backend"),
        )
    if prefer == "gpu":
        raise GpuUnavailableError(str(probe.get("detail") or "no hardware GPU adapter"))
    return Engine("cpu", str(probe.get("detail") or "no hardware GPU adapter"))


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
        verify: bool = True,
        bits: int = SUPPORTED_BITS,
        radius: int = SUPPORTED_RADIUS,
    ) -> None:
        self._packed, self._valid = pack_smiles(smiles)
        self._n = len(smiles)
        self._verify = verify
        self._engine = self._choose(prefer, bits, radius)
        self._gpu = None
        if self._engine.name == "gpu":
            from hcs_discovery.gpu.engine import GpuEngine

            try:
                self._gpu = GpuEngine()
            except Exception as exc:
                if prefer == "gpu":
                    raise GpuUnavailableError(str(exc)) from exc
                self._engine = Engine("cpu", f"GPU initialisation failed: {exc}")

    def _choose(self, prefer: EnginePreference, bits: int, radius: int) -> Engine:
        if (radius, bits) != (SUPPORTED_RADIUS, SUPPORTED_BITS):
            if prefer == "gpu":
                raise ValidationError(
                    "The GPU kernel is fixed at Morgan/ECFP radius=2, 2048 bits.",
                    details={"radius": radius, "bits": bits},
                )
            return Engine("cpu", f"CPU reference: kernel is {SUPPORTED_RADIUS}/{SUPPORTED_BITS}, not {radius}/{bits}")
        return resolve_engine(prefer)

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
        query = self._query_fingerprint(query_smiles)
        if self._gpu is not None:
            result = self._gpu.counts(query, self._packed)
            inter, union = result.inter, result.union
            if self._verify:
                reference_inter, reference_union = cpu_counts(query, self._packed)
                if not (np.array_equal(inter, reference_inter) and np.array_equal(union, reference_union)):
                    raise ParityError(
                        "GPU Tanimoto counts differ from the CPU reference; no result was returned.",
                        # the counts themselves are not attached: they would be huge
                    )
            return inter, union
        return cpu_counts(query, self._packed)

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
    verify: bool = True,
) -> SearchResult:
    """One-shot search; builds the index, scores and closes the device."""
    with TanimotoIndex(smiles, prefer=prefer, verify=verify) as index:
        return index.search(query_smiles, k=k, threshold=threshold)


def similarity_runtime_fingerprint(prefer: EnginePreference = "auto") -> dict[str, str]:
    """Cache-key input: which engine and adapter would produce the values."""
    try:
        engine = resolve_engine(prefer)
    except GpuUnavailableError as exc:
        return {"similarity_engine": "unavailable", "similarity_detail": str(exc)}
    return {
        "similarity_engine": engine.name,
        "similarity_backend": engine.backend or "none",
        "similarity_adapter": engine.adapter or "none",
    }
