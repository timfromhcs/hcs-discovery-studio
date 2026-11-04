# Delaney ESOL fixture

`delaney-processed.csv` is the 1,128-molecule aqueous-solubility set distributed with
[MoleculeNet](https://moleculenet.org/) (DeepChem, MIT-licensed repository), derived
from:

> Delaney, J. S. (2004). ESOL: estimating aqueous solubility directly from molecular
> structure. *J. Chem. Inf. Comput. Sci.* 44(3), 1000–1005.

| Item | Value |
|---|---|
| Source URL | `https://raw.githubusercontent.com/deepchem/deepchem/master/datasets/delaney-processed.csv` |
| Retrieved | 2026-11-04 |
| SHA-256 | `8c06a76f0c6487d29ab0f903e6a7a7139f189ab3c1178f159c8be8964602f189` |
| Rows | 1,128 |
| Measured column | `measured log solubility in mols per litre` (log10 mol/L) |

The file is committed so the benchmark in
`docs/validation/esol-delaney.md` runs offline and deterministically.
`scripts/science/validate_esol_delaney.py` refuses to report on a file whose hash
differs from the pinned value above. The measurements are factual data; no model
weights or proprietary records are included.
