# ESOL aqueous solubility validation

Generated from the checked-in measured dataset by `scripts/science/validate_esol.py`. Re-run the script (or `python scripts/science/validate_esol.py --check` in CI) to verify these numbers still match the model code and fixture.

## Dataset

- Dataset: AqSolDB Solubility Challenge subset (Llinas et al. 2008 source records)
- Records evaluated: 45
- Fixture: `tests/fixtures/esol_solubility_challenge.json` (SHA-256 `3462c19372dab529c8f4128fcb4ddf482626a5a337093512c4a448f5928354a1`)
- Distribution: [AqSolDB curated dataset, results/data_curated.csv](https://raw.githubusercontent.com/mcsorkun/AqSolDB/master/results/data_curated.csv), DOI 10.1038/s41597-019-0151-1, license MIT
- Original measurements: Llinas, A.; Glen, R. C.; Goodman, J. M. (2008). Solubility Challenge: Can You Predict Solubilities of 32 Molecules Using a Database of 100 Reliable Measurements? J. Chem. Inf. Model. 48(7), 1289-1303. (DOI 10.1021/ci800058v)
- Retrieved: 2026-10-29
- Selection rule: All AqSolDB rows whose ID begins with 'I-' (the Llinas et al. 2008 source), retained only if RDKit parses the SMILES, the record is single-component and formally neutral, every element is in the ESOL domain (H, C, N, O, P, S, F, Cl, Br, I), molecular weight is in [30, 800] Da, and heavy-atom count is in [2, 60].
- Excluded `I-75` (ranitidine): contains a formally charged atom.

## Results

| Metric | Value |
| --- | ---: |
| n | 45 |
| RMSE (log10 units) | 0.9677 |
| RMSE 95% bootstrap CI | [0.7084, 1.2602] |
| MAE (log10 units) | 0.7286 |
| R² | 0.0719 |
| Mean error (prediction − measurement) | +0.2239 |
| Mean-baseline RMSE | 1.0045 |
| Predictions within 10× of measurement | 71.1% |
| Largest absolute error (log10 units) | 3.5340 |

The mean baseline predicts the dataset mean for every molecule; a model that does not beat it has no demonstrated ranking or absolute accuracy on this set.

## Per-molecule predictions

| ID | Name | Measured logS | Predicted logS | Error |
| --- | --- | ---: | ---: | ---: |
| I-2 | 2_amino_5_bromobenzoic_acid | -3.070 | -2.607 | +0.463 |
| I-4 | 5_bromo_2_4_dihydroxybenzoic_acid | -2.620 | -2.571 | +0.049 |
| I-6 | acetazolamide | -2.440 | -0.831 | +1.609 |
| I-9 | amitryptyline | -4.550 | -4.411 | +0.139 |
| I-10 | amodiaquine | -5.790 | -5.387 | +0.403 |
| I-11 | atropine | -2.000 | -2.798 | -0.798 |
| I-13 | benzylimidazole | -2.260 | -2.584 | -0.324 |
| I-14 | bromogramine | -4.060 | -3.638 | +0.422 |
| I-17 | carvedilol | -4.260 | -4.524 | -0.264 |
| I-18 | cephalothin | -2.940 | -2.417 | +0.523 |
| I-19 | chlorpheniramine | -2.670 | -4.087 | -1.417 |
| I-20 | chlorpromazine | -5.070 | -5.059 | +0.011 |
| I-21 | chlorpropamide | -3.250 | -2.648 | +0.602 |
| I-24 | chlorzoxazone | -2.660 | -2.615 | +0.045 |
| I-26 | ciprofloxacin | -3.600 | -3.002 | +0.598 |
| I-27 | danofloxacin | -2.900 | -3.444 | -0.544 |
| I-28 | deprenyl | -2.510 | -2.429 | +0.081 |
| I-33 | diltiazem | -3.160 | -4.442 | -1.282 |
| I-34 | diphenydramine | -2.950 | -3.608 | -0.658 |
| I-37 | famotidine | -2.650 | -1.171 | +1.479 |
| I-38 | fenoprofen | -3.700 | -3.882 | -0.182 |
| I-42 | glipizide | -5.490 | -3.736 | +1.754 |
| I-43 | guanine | -4.430 | -0.896 | +3.534 |
| I-45 | hydroflumethiazide | -2.970 | -2.059 | +0.911 |
| I-54 | nalidixic_acid | -3.610 | -2.480 | +1.130 |
| I-55 | naloxone | -2.900 | -2.743 | +0.157 |
| I-56 | naproxen | -4.500 | -3.418 | +1.082 |
| I-60 | nortriptiline | -4.020 | -4.130 | -0.110 |
| I-62 | oxytetracycline | -3.090 | -1.815 | +1.275 |
| I-63 | papaverine | -3.870 | -4.454 | -0.584 |
| I-65 | phenazopyridine | -4.190 | -3.262 | +0.928 |
| I-66 | phenobarbital | -2.290 | -1.850 | +0.440 |
| I-70 | pindolol | -3.790 | -2.554 | +1.236 |
| I-72 | procaine | -1.720 | -2.284 | -0.564 |
| I-74 | quinine | -2.790 | -3.895 | -1.105 |
| I-76 | sarafloxacin | -3.130 | -3.951 | -0.821 |
| I-77 | sparfloxacin | -3.370 | -3.651 | -0.281 |
| I-79 | sulfamethazine | -2.730 | -2.765 | -0.035 |
| I-80 | sulfasalazine | -6.140 | -4.722 | +1.418 |
| I-83 | sulindac_form_II | -4.500 | -4.891 | -0.391 |
| I-84 | tetracaine | -3.010 | -2.833 | +0.177 |
| I-85 | tetracycline | -2.930 | -2.467 | +0.463 |
| I-86 | thymol | -2.190 | -2.888 | -0.698 |
| I-93 | verapamil | -3.980 | -5.278 | -1.298 |
| I-94 | warfarin | -4.780 | -4.276 | +0.504 |

## Interpretation and limitations

- This is a measured-value check of the Delaney (2004) four-descriptor reduced ESOL equation, not a re-fit. On this 45-molecule drug-like challenge set it achieves RMSE 0.968 log10 units and R² 0.072. The near-zero R² means the model explains little of the variance in this set; absolute solubility predictions should not be treated as reliable for these compounds.
- The set postdates Delaney (2004), but AqSolDB curation may still share source measurements with that training data; this report does not claim a fully leakage-audited benchmark.
- ESOL estimates intrinsic solubility of the neutral form. It does not model ionization, salt form, pH, polymorphs, or kinetic dissolution, all of which matter for the ionizable and zwitterionic molecules here.
- Applicability-domain flags only state that descriptors fall inside the fitted range. They do not certify accuracy, as the errors above show.
- The 95% bootstrap interval [0.708, 1.260] reflects sampling noise for n=45; it is wide and does not include model-form error.

Environment: Python 3.12.13, RDKit 2026.09.1. Model weights hash `09fcfc4a4a1ea22756d2328267cbeec4566900f3c2f427f689162f395a60053c`.
