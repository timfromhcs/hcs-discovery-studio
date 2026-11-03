"""SMILES -> bit-packed Morgan fingerprints (2048 bit = 64 x uint32)."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from rdkit import Chem
from rdkit.Chem import rdFingerprintGenerator

BITS = 2048
WORDS = BITS // 32
RADIUS = 2

_generator = rdFingerprintGenerator.GetMorganGenerator(radius=RADIUS, fpSize=BITS)


def pack_smiles(smiles: Sequence[str]) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(packed[N, 64] uint32, valid[N] bool)``.

    Invalid SMILES keep their row (all zero, ``valid=False``) so indices never shift.
    """
    packed = np.zeros((len(smiles), WORDS), dtype=np.uint32)
    valid = np.zeros(len(smiles), dtype=bool)
    for i, smi in enumerate(smiles):
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            continue
        bits = np.zeros(BITS, dtype=np.uint8)
        bits[list(_generator.GetFingerprint(mol).GetOnBits())] = 1
        # bit k lives in word k // 32, position k % 32 (little endian)
        packed[i] = np.packbits(bits, bitorder="little").view("<u4")
        valid[i] = True
    return packed, valid
