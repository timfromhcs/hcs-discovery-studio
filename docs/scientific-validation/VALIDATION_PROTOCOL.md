# Scientific validation protocol

This protocol defines how a scientific claim may be made about an adapter or a
workflow. It exists to prevent the project from presenting a plausible-looking
number as validated science.

**Current status:** no predictive accuracy claim is made for 0.1.0. RDKit
descriptor correctness is covered by deterministic tests against RDKit itself,
not against experimental endpoints. No docking, ADMET, activity or structure
prediction model is implemented.

## 1. Define the question and output

Write one sentence that names the task, the input, the output and the unit. Do
not combine tasks.

Examples of acceptable scopes:

- "Parse and standardise a SMILES/SDF library; report the fraction of rows that
  produce a valid molecule and the reason for each failure."
- "Compute RDKit QED for a fixed molecule set with a pinned RDKit version;
  compare to a recorded reference table."
- "Rank a fixed library by Morgan/Tanimoto similarity to a named query; report
  the top-k overlap with a reference implementation."

Examples of unacceptable scopes:

- "Predict drug-likeness."
- "Find the best compound."
- "Validate the model on our library" without naming the endpoint, labels,
  split and metric.

## 2. Data

Record for every dataset:

- name, version or release tag, source URL,
- retrieval date and SHA-256,
- license and attribution,
- inclusion/exclusion criteria,
- number of records before and after cleaning,
- how duplicates, salts, mixtures and missing values were handled,
- whether the data may be redistributed.

Do not commit restricted data. Publish a manifest and, where allowed, a checksum
and retrieval script instead.

## 3. Splits and leakage

Choose the split before looking at test performance.

- **Random split** is acceptable only when near-duplicates are not a concern.
- **Scaffold split** (Bemis–Murcko) is the default for molecular property tasks.
- **Time split** is required when the intended use is prospective and dates are
  available.
- **Sequence/structure similarity clustering** is required for target-based
  tasks; a random split across homologous proteins leaks information.

Report the split algorithm, seed, cluster cutoff and the number of records in
each fold. Check for duplicate structures and near-duplicates across splits.

## 4. Preprocessing and units

- Freeze the standardisation options (salt stripping, neutralisation, tautomer)
  before evaluation.
- Keep raw values and the exclusion log.
- State the endpoint unit, assay type and censoring rule.
- Do not mix pIC50, IC50, Ki and Kd without an explicit conversion and a
  sensitivity analysis.
- Record the software and engine versions used to featurise the data.

## 5. Baselines

Every claim needs a baseline evaluated on the same split and inputs:

- a trivial baseline (global mean, majority class, random ranking),
- a simple descriptor baseline (for example a linear model on the same
  descriptors),
- the proposed method.

If the proposed method does not beat the trivial baseline, say so.

## 6. Metrics chosen in advance

Pick metrics before running the final evaluation. Report at least:

- the primary metric and why it matches the decision,
- a ranking metric where relevant (for example enrichment factor at a stated
  cutoff),
- calibration or uncertainty where the output is probabilistic,
- sample counts and missingness,
- confidence intervals (bootstrap or an appropriate analytic interval),
- runtime, memory and hardware,
- the exact command and commit.

Do not report only the best metric or the best fold. Report all folds and the
aggregation rule.

## 7. Seeds and nondeterminism

- Run at least three seeds for stochastic methods and report mean and spread.
- Record the seed in the run manifest.
- Identify sources of nondeterminism (thread scheduling, GPU kernels, library
  versions) and either eliminate or document them.
- A single deterministic run may be reported as deterministic, not as robust.

## 8. Development versus held-out evaluation

- Tune on a development split only.
- Touch the test split once, after the method is frozen.
- If you tune against the test set, the result is no longer an independent
  evaluation; label it as development performance.
- Keep a decision log of every configuration change made after seeing test
  results.

## 9. Reproducibility package

Publish, within license limits:

- the exact commit and tag,
- `uv.lock` and `package-lock.json`,
- the dataset manifest and checksums,
- the workflow YAML/JSON and seeds,
- the benchmark script,
- the result artifact and the report,
- hardware and runtime,
- known deviations from this protocol.

## 10. Result status

Every result must carry one status:

| Status | Meaning |
|---|---|
| `reproduced` | An independent run on the same data and protocol produced a result consistent within the stated uncertainty |
| `partially reproduced` | Direction or ranking is consistent, but magnitudes or secondary metrics differ materially |
| `not comparable` | The data, split, metric or preprocessing differs enough that comparison is invalid |
| `not reproduced` | The result could not be obtained; explain what differed |

Never label a result "SOTA" without a named benchmark, a named baseline, the
official split and an independent reproduction. Even then, state the scope.

## 11. Current adapter checks

### RDKit descriptor parity

- Fixed molecule set with expected values recorded from the pinned RDKit
  version.
- Assert exact or tolerance-bound equality for each descriptor.
- Assert that each column carries a label, unit, direction and method.
- Re-run on Linux and Windows CI.

### Import correctness

- Fixture files with valid rows, invalid SMILES, missing structures, duplicate
  headers and mixed encodings.
- Assert per-row status and error messages.
- Assert the file checksum and record counts.

### Ranking invariants

- A dominated row never receives a better Pareto front than its dominator.
- Filter-failing rows receive no Pareto front.
- Changing a weight changes the composite order in the expected direction.
- Adding an outlier changes min-max scores; this must be documented, not hidden.

These are correctness checks, not efficacy validation.

## 12. Template for a future model report

```markdown
# Validation report: <adapter> <version>

- Status: reproduced | partially reproduced | not comparable | not reproduced
- Commit/tag:
- Task and output unit:
- Dataset and checksum:
- License/redistribution:
- Split and leakage controls:
- Preprocessing:
- Baseline(s):
- Primary metric and CI:
- Secondary metrics:
- Seeds and runs:
- Hardware and runtime:
- Result artifact:
- Deviations:
- Limitations:
```

## 13. Review checklist

- [ ] The claim is one task, one output, one unit.
- [ ] The dataset is licensed and checksummed.
- [ ] The split is appropriate and leakage was checked.
- [ ] Baselines use the same inputs and split.
- [ ] Metrics were chosen before the final run.
- [ ] Confidence intervals and sample counts are reported.
- [ ] Seeds and nondeterminism are documented.
- [ ] The test split was not used for tuning.
- [ ] The result status is honest.
- [ ] The report does not imply clinical or experimental validity.
