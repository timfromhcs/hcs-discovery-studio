from __future__ import annotations

import numpy as np
from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator

from hcs_discovery.gpu import cpu_tanimoto, pack_smiles, ratio

SMILES = [
    "CC(=O)Oc1ccccc1C(=O)O",
    "CN1CCC[C@H]1c1cccnc1",
    "c1ccccc1",
    "CCO",
    "CC(C)Cc1ccc(cc1)C(C)C(=O)O",
    "O=C(O)c1ccccc1O",
    "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
    "C1CCCCC1",
    "CCN(CC)CC",
    "OC(=O)CCCC(=O)O",
] * 20


def test_pack_matches_rdkit_bits():
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
    packed, valid = pack_smiles(SMILES)
    assert valid.all()
    for i in (0, 1, 5):
        expected = gen.GetFingerprint(Chem.MolFromSmiles(SMILES[i])).GetNumOnBits()
        assert int(np.unpackbits(packed[i].view(np.uint8)).sum()) == expected


def test_cpu_tanimoto_matches_rdkit_bulk():
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
    fps = [gen.GetFingerprint(Chem.MolFromSmiles(s)) for s in SMILES]
    expected = np.array(DataStructs.BulkTanimotoSimilarity(fps[0], fps), dtype=np.float32)
    packed, _ = pack_smiles(SMILES)
    got = cpu_tanimoto(packed[0], packed)
    assert np.max(np.abs(got - expected)) <= 1e-6


def test_zero_fingerprint_gives_zero_not_nan():
    zeros = np.zeros((3, 64), dtype=np.uint32)
    out = cpu_tanimoto(zeros[0], zeros)
    assert not np.isnan(out).any() and (out == 0).all()
    assert ratio(np.array([0], dtype=np.uint32), np.array([0], dtype=np.uint32))[0] == 0.0


def test_invalid_smiles_flagged_in_mask():
    packed, valid = pack_smiles(["CCO", "not-a-smiles", "c1ccccc1"])
    assert valid.tolist() == [True, False, True]
    assert packed[1].sum() == 0 and packed.shape == (3, 64)
