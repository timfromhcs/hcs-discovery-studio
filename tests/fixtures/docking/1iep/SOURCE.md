# 1IEP redocking fixture (imatinib / Abl kinase)

These files are copied unchanged from the official AutoDock Vina example
`example/basic_docking` at commit
[`bb64e5e26b520569a86360d69248069b5e665b3f`](https://github.com/ccsb-scripps/AutoDock-Vina/tree/bb64e5e26b520569a86360d69248069b5e665b3f/example/basic_docking)
of <https://github.com/ccsb-scripps/AutoDock-Vina>. That repository is licensed
under the Apache License 2.0; a copy is in `LICENSE-AutoDock-Vina.txt`. The
underlying structure is PDB entry [1IEP](https://www.rcsb.org/structure/1IEP)
(Nagar et al., Cancer Res. 2002, 62, 4236–4243). The Vina authors prepared the
files as described in the
[basic docking tutorial](https://autodock-vina.readthedocs.io/en/latest/docking_basic.html).

| File in this directory | Upstream path | SHA-256 |
|---|---|---|
| `receptor.pdbqt` | `solution/1iep_receptor.pdbqt` | `f13cf3b36f61d87c3b58983e0b8ecf1c3456a685eb86dfe9ccfb139c7bdc2586` |
| `crystal_ligand.sdf` | `data/1iep_ligand.sdf` | `051b8742c32adc05c07fb486a4e7c9327f84e131cee33ac4e6a568d07553eb38` |
| `reference_ligand.pdbqt` | `solution/1iep_ligand.pdbqt` | `15fb35648d8c18c70317842f3a0631b73a19429c710a037ab07310084d579bb8` |
| `box.txt` | `solution/1iep_receptor.box.txt` | `3dff08200b5b9c2ca0932c832c9dffc5823b39caec6c92f76be5f7c5ea49d8de` |

- `crystal_ligand.sdf` is the crystallographic imatinib pose with hydrogens
  added by the Vina authors; the piperazine nitrogen is protonated. It is the
  RMSD reference.
- `reference_ligand.pdbqt` is the Vina authors' own ligand preparation (Meeko),
  used as the control arm. It is built from the crystal coordinates.
- `receptor.pdbqt` is the Vina authors' prepared receptor. HCS Discovery Studio
  does not prepare receptors itself.
- `box.txt` is the search box from the tutorial.

`scripts/science/redock_vina_reference.py` checks these hashes before use and
refuses to run if any file differs.
