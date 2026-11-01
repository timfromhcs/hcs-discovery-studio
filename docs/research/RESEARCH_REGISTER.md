# Research register

One row per open or answered research question. "Outcome" records what was
observed, including negative results; a row is not a claim of validation.

| # | Question | Status | Closest prior work | Data / setup | Planned or completed test | Outcome |
|---|---|---|---|---|---|---|
| R1 | Does ligand preparation reproduce an independent implementation? | Answered (narrow) | Meeko 0.8.0 | 51 fixture ligands | Torsion tree, atom types, charges compared | 48/51 identical; 3 macrocycle cases kept rigid on purpose → [`docs/validation/ligand-prep-meeko.md`](../validation/ligand-prep-meeko.md) |
| R2 | Can the docking path reproduce a known crystal pose? | Answered (one complex) | AutoDock Vina `basic_docking` example | 1IEP imatinib / Abl, 5 seeds | Symmetry-aware heavy-atom RMSD, ≤ 2.0 Å gate in CI | Top pose 0.42–0.94 Å (HCS) vs 0.29–0.37 Å (Vina control) → [`docs/validation/vina-redocking-1iep.md`](../validation/vina-redocking-1iep.md) |
| R3 | Are the property estimates better than a constant baseline? | Answered (weak) | ESOL (Delaney 2004); Llinas 2008 challenge | 45 measured compounds from AqSolDB curation | RMSE, R², bootstrap CI vs mean baseline | RMSE 0.968 vs 1.004 baseline, R² 0.072, CI [0.708, 1.260] — barely better → [`docs/validation/esol-solubility.md`](../validation/esol-solubility.md) |
| R4 | Is the CNS MPO estimate a probability? | Answered (no) | Wager et al. 2010 CNS MPO | N/A | Inspect inputs and outputs | It is a 0–6 desirability heuristic with an assumed pKa and no uncertainty. Relabelled → `CHANGELOG` 2.0.0 |
| R5 | Does HAEL beat simpler selection policies at matched budget? | Open — synthetic only | Multi-fidelity BO (2025); EHVI; conformal calibration (2026) | Synthetic 1-D search, 20 seeds, 90 s budget | Regret of selected candidate vs true best | HAEL best mean regret (−0.285) but small margin over cheap baselines; remains `experimental` → [`HAEL.md`](HAEL.md) |
| R6 | Is HAEL beneficial on a real docking or ADMET task? | Open — not started | Same as R5 | Needs a licensed, split-frozen dataset | Pre-registered multi-target evaluation with calibration split | Not run. Requires WP1 evidence persistence and a real endpoint model first |
| R7 | Are ensemble/conformal intervals calibrated under scaffold shift? | Open — not started | Scaffold-shift calibration study (2026) | Needs per-endpoint model + calibration split | Empirical vs nominal coverage, subgroup coverage | Not run. The product currently reports a heuristic error scale, explicitly not an interval |
| R8 | Can a target/structure store carry provenance without leaking unsupported structures? | Open | RCSB PDB / UniProt conventions | Reserved `targets`/`structures` tables exist | WP2 design and integration tests | Not implemented; tables are reserved and may change |

## Conventions

- "Answered (narrow)" means the claim holds only for the stated fixture; it is not a
  general benchmark.
- No row may be marked answered by a passing unit test alone.
- Negative outcomes stay in the register.
