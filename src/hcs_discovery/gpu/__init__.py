"""Shared-kernel GPU similarity (WebGPU/Vulkan) with an exact CPU reference."""

from __future__ import annotations

from pathlib import Path

from hcs_discovery.gpu.cpu import cpu_counts, cpu_tanimoto, ratio
from hcs_discovery.gpu.fingerprints import BITS, WORDS, pack_smiles

KERNEL_PATH = Path(__file__).parent / "kernels" / "tanimoto.wgsl"

__all__ = ["BITS", "KERNEL_PATH", "WORDS", "cpu_counts", "cpu_tanimoto", "pack_smiles", "ratio"]
