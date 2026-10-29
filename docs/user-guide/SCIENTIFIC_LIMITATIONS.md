# Scientific limitations

Read this before using any result in a research decision. The application is a
reproducible triage workbench, not a predictor of clinical outcomes.

## The central caveat

Every number produced here is a computational signal derived from a structure
and a named method. It is not a measurement. It does not prove binding, potency,
selectivity, safety, efficacy, toxicity, bioavailability or clinical utility.
Experimental validation is required before any biological conclusion.

## What each method actually is

### Standardisation

Imported structures are parsed by RDKit. Salt stripping, neutralisation and
canonical tautomer selection change the structure. Two inputs that a chemist
considers equivalent may produce different standardised forms, and two different
inputs may collapse to the same canonical form. The raw input is retained, but
downstream descriptors describe the standardised structure, not necessarily the
source record. Review the import warnings.

### Descriptors

- **Molecular weight** is an average mass including implicit hydrogens.
- **cLogP** is the Wildman–Crippen estimate, not an experimental logD.
- **TPSA** is the Ertl topological polar surface area.
- **HBD/HBA** use Lipinski definitions and are not pH-dependent.
- **Rotatable bonds** use the RDKit Lipinski definition.
- **QED** is a heuristic composite of drug-likeness properties. It is not a
  probability of success and not a regulatory criterion.
- **Fraction sp3**, ring counts and heavy-atom counts are structural counts.

Descriptor values depend on the RDKit version. The manifest records it. A value
computed with a different RDKit version may differ slightly.

### Similarity

Morgan/ECFP Tanimoto similarity measures fingerprint overlap. It is not a
measure of biological similarity, off-target risk or synthetic accessibility. A
high similarity to a known active molecule is a hypothesis, not evidence that the
new molecule is active. The query structure and fingerprint parameters are part
of the run configuration and must be reported with the result.

### Rule filters

Thresholds such as "MW 150–600" or "TPSA ≤ 160" are project criteria. They are
inspired by common drug-likeness heuristics but are not universal laws, and they
can exclude useful compounds. The filter reasons are retained so you can audit
every exclusion. A passing row is not "drug-like"; it merely satisfies the rules
you chose.

### Pareto fronts and composite score

- Pareto non-dominated sorting identifies rows that are not worse than another
  row on every objective. It does not identify the "best" molecule.
- The composite score is a weighted average of min-max normalised objectives.
  Min-max normalisation is sensitive to the current dataset's range: adding an
  outlier changes every score.
- Weights are a value judgement. Different weights produce a different ranking
  from identical data. Report the weights.
- Missing objective values produce an empty composite score.
- Filter-failing rows are excluded from Pareto fronts and ranked after passing
  rows. Their `pareto_rank` is `null`.
- Rows beyond `pareto_front_limit` are not assigned a front; this is a display
  and ranking limit, not a scientific result.

### Summaries and reports

Reports are generated from persisted run data. They faithfully reproduce the
stored numbers and methods, but a well-formatted report is not evidence of
validity.

## Docking (AutoDock Vina)

- Vina scores are an empirical scoring function in kcal/mol. They rank poses;
  they are not binding free energies, affinities, selectivity or efficacy.
- Ligands are prepared by RDKit (ETKDGv3 + MMFF94, Gasteiger charges, AutoDock 4
  types, merged non-polar hydrogens). Protonation and tautomers are taken as
  given in the input; no pH-dependent enumeration is done. Rings of 7+ atoms
  are kept rigid. Salts are reduced to the largest fragment and the row says so.
- Receptors must already be prepared PDBQT. The application validates the
  format but does not add hydrogens, assign charges or check the binding site.
- The search box, exhaustiveness and seed are user choices and change results.
- Preparation was compared with Meeko 0.8.0 on 51 fixture ligands; that is a
  format check, not evidence of docking accuracy.

## Property estimates

- **ESOL** is a reduced four-descriptor form of Delaney (2004). On 45 measured
  compounds from the Solubility Challenge it reaches RMSE 0.97 and R² 0.07
  log10 units, barely better than predicting the mean. Its uncertainty column is
  a heuristic descriptor-distance scale, not a confidence interval.
- **CNS MPO** uses Wager et al. (2010) desirability functions, with cLogP in
  place of ClogD and an assumed pKa (9.0 aliphatic amines, 11.0 amidines and
  guanidines) when a basic centre is detected. It is a physicochemical
  desirability score, not a probability of brain penetration, and reports no
  uncertainty.

## What is not implemented

- No docking benchmark: Vina runs, but no redocking or pose-recovery study has
  been performed (see Docking above).
- No molecular dynamics or free-energy calculation.
- No learned ADMET, toxicity or activity prediction.
- No structure prediction or co-folding.
- No target or structure database integration.
- No experimental data ingestion or assay curve fitting.
- No uncertainty calibration for any score.
- No statistical applicability-domain model; ESOL and CNS MPO flag simple
  descriptor ranges only.

The model registry lists several of these as `planned`. They are not runnable and
must not be described as available.

## Data quality

- Import accepts CSV, SDF and SMILES. It does not verify that a structure is the
  intended compound, that a name matches the structure, or that a source
  identifier is correct.
- Duplicate structures are kept. The import count reflects rows, not unique
  compounds.
- Invalid rows are retained with an error. A successful import can still contain
  rows that failed; check `error_count`.
- Units are declared per column, but the application does not convert source
  units. If your source file mixes units, fix it before import.
- There is no automatic detection of assay units, censored values or
  stereochemistry inconsistencies beyond RDKit parsing.

## Reproducibility is not validity

A run can be perfectly reproducible and scientifically wrong. Reproducibility
means the same inputs, configuration, code and engine versions produce the same
output. It does not mean the output is correct. The manifest gives you the
information needed to reproduce and critique a run; it does not certify it.

## Appropriate uses

- Triaging a library with explicit, documented criteria.
- Teaching and demonstrating reproducible cheminformatics workflows.
- Comparing descriptor distributions under a fixed method.
- Generating hypotheses for experimental follow-up.
- Auditing how a ranking changes when weights or thresholds change.

## Inappropriate uses

- Claiming a molecule is safe, effective or non-toxic.
- Selecting a clinical candidate without experimental and regulatory work.
- Reporting a ranking as a prediction of binding affinity.
- Comparing scores across datasets without re-normalising and documenting the
  difference.
- Using the output as the sole basis for a patent, regulatory or investment
  decision.

## Reporting a scientific issue

If a method is mislabeled, a unit is wrong, or a result is not reproducible,
open an issue with the run ID, workflow hash, manifest and the exact command used.
Do not include confidential structures. See `CONTRIBUTING.md`.
