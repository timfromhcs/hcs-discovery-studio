"""NumPy reference for the GPU Tanimoto kernel (integer-exact)."""

from __future__ import annotations

import numpy as np

_POP8 = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint32)


def _popcount_rows(words: np.ndarray) -> np.ndarray:
    as_bytes = np.ascontiguousarray(words, dtype="<u4").view(np.uint8)
    return _POP8[as_bytes].reshape(words.shape[0], -1).sum(axis=1, dtype=np.uint32)


def cpu_counts(query: np.ndarray, library: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(intersection, union)`` popcounts for each library row."""
    q = np.asarray(query, dtype=np.uint32).reshape(1, -1)
    lib = np.asarray(library, dtype=np.uint32)
    return _popcount_rows(lib & q), _popcount_rows(lib | q)


def ratio(inter: np.ndarray, union: np.ndarray) -> np.ndarray:
    """float32 Tanimoto; an empty union is defined as 0.0 (matches RDKit)."""
    out = np.zeros(inter.shape, dtype=np.float32)
    nz = union > 0
    out[nz] = inter[nz].astype(np.float32) / union[nz].astype(np.float32)
    return out


def cpu_tanimoto(query: np.ndarray, library: np.ndarray) -> np.ndarray:
    return ratio(*cpu_counts(query, library))
