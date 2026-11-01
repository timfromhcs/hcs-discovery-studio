# HAEL — HCS Adaptive Evidence Ladder

**Status: `experimental`.** HAEL is an original *engineering composition* of
established ideas. It is not a published algorithm, it has no demonstrated
advantage on a real drug-discovery task, and it is **not** the default scheduler
of any shipped workflow. The code lives in `src/hcs_discovery/hael/` and is
covered by unit and property tests; nothing in the UI or the workflow engine
calls it yet.

This document records what exists, what the tests prove, what the ablation
measured and what remains unknown.

---

## 1. The problem it solves

A fixed workflow runs every engine on every molecule. A cheaper strategy ranks by
descriptors and docks only the top *k*, which discards candidates early and cannot
recover them. Neither adapts to what is already known about a specific candidate,
and neither accounts for the fact that a 35-second reference assay may be worth
far more than twenty 1-second descriptors.

HAEL chooses the next calculation for a `(candidate, fidelity)` pair by comparing
the expected value of that calculation against its measured cost.

## 2. Acquisition rule

```text
A(c, f) = (EHVI(c, f | D) + λ · EIG(c, f | D) + ν · ΔDiversity(c, f)) / (C(c, f) + ε)
```

| Term | Implementation | Notes |
|---|---|---|
| `EHVI` | Closed-form expected improvement for 1 objective; seeded Monte-Carlo (default 512 samples) for 2 objectives | More than 2 dimensions is refused, not approximated silently |
| `EIG` | `0.5 · ln(1 + σ²_prior / σ²_observation)`, summed over dimensions | Analytic Gaussian entropy reduction; no sampling needed |
| `ΔDiversity` | Mean novelty over the scaffold and pocket signals that are known | A duplicate scaffold contributes exactly `0`; unknown diversity contributes `0`, never assumed novelty |
| `C` | Measured recordings, rolling p90 over a 20-sample window, or an explicitly configured default | No observation and no default ⇒ the action is skipped as `unknown_cost` |
| `λ, ν, ε` | `AcquisitionConfig(version="hael-acquisition-1")`, defaults `0.5`, `0.25`, `1e-9` | Versioned and written into every decision trace |

The whole rule is pure: the same inputs and seed produce the same score and the
same trace digest.

## 3. Evidence gates

The acquisition rule can only *select* an action. Whether the result may influence
the validated frontier is decided separately by `EvidenceLedger.gate`, which
demands all of:

- the same endpoint as the task dimension,
- the same unit label (and a unit the registry knows),
- the same direction,
- `status` of `validated` or `reference_tested` (not `exploratory`, never `blocked`),
- a calibration record **and** a conformal or credible interval when the task
  requires calibration,
- `applicability_domain == "in_domain"`.

Anything else stays visible as exploratory evidence. There is no method anywhere in
the package that collapses several dimensions into one scalar score, so a docking
energy cannot be added to a predicted pIC50 by accident.

Failed calculations become `EvaluationFailure` rows with an error code. They are
never converted to `0`, a mean or a success, and a candidate with a failure has no
value in the objective table.

## 4. What the tests establish

`tests/unit/test_hael_evidence.py`, `test_hael_acquisition.py`,
`test_hael_scheduler.py` and `test_hael_guards.py` (94 tests) cover the properties
listed in the project mandate:

| Property | Test |
|---|---|
| Dimensional integrity | mixed endpoints/units raise; `ObjectiveVector` has no scalar method |
| Gate integrity | uncalibrated, out-of-domain, blocked and exploratory evidence cannot reach the frontier |
| Cost monotonicity | Hypothesis: for any two positive costs, the cheaper action never scores lower |
| Information monotonicity | more prior uncertainty raises EIG; noisier measurement lowers it |
| Diversity | duplicate scaffold/pocket adds `0`; a new scaffold adds `> 0` |
| Determinism | same inputs and seed ⇒ identical trace and digest |
| Budget | budget is respected; `max_steps` and cancellation stop the campaign |
| Failure recovery | an engine error does not end the campaign or create a value |
| Auditability | every considered and skipped action is persisted with its reason |
| Guard rails | unknown units, unknown costs, >2 dimensions and malformed evidence fail closed |

Coverage: `acquisition` 99 %, `evidence` 99 %, `scheduler` 94 %, `cost` 95 %,
`units` 96 % (branch coverage).

## 5. Ablation at matched budget (synthetic)

`uv run python scripts/science/benchmark_hael.py` — 20 seeds, 24 candidates, three
fidelities (cost 1 s / 8 s / 35 s, noise 1.10 / 0.35 / 0.10 log units), 90 s budget
per seed. The metric is the regret of the **selected candidate**: after the
campaign, the candidate with the highest mean measurement is chosen and scored
against the true best latent potency. `0` is perfect; negative is worse.

| Policy | Median regret | Mean regret | Worst |
|---|---:|---:|---:|
| `hael` | 0.0000 | **−0.2852** | −2.3320 |
| `hael_cost_unaware` | 0.0000 | −0.4978 | −2.3124 |
| `descriptor_only` | 0.0000 | −0.5190 | −2.4352 |
| `random` | −0.9230 | −1.1401 | −3.2761 |
| `static_cascade` | −1.3086 | −1.4499 | −3.9482 |
| `best_rung_round_robin` | −1.5137 | −1.6562 | −4.0052 |

Reading this honestly:

- HAEL has the best mean regret, but the margin over cost-unaware HAEL and over
  "run the cheap descriptor on everything" is **small**, and the worst case is not
  better than the cheap baseline.
- The clear separation is against *uninformed* policies (random, static cascade,
  best-rung round robin), which is the weakest possible claim.
- This is a **synthetic** one-dimensional problem. It ablates the deciding, not the
  chemistry. It is not evidence that HAEL finds better molecules.

## 6. Known limits

- Two objective dimensions maximum. Three or more raises
  `UnsupportedObjectiveDimensionError` instead of a silent approximation.
- EHVI for two dimensions is a Monte-Carlo estimate with a reference point fixed by
  the prediction and the current front; the sample count and seed are recorded, but
  the estimate is not exact.
- The exploratory policy is "novelty per cost" only. There is no calibrated
  prediction, so there is no honest EIG to compute.
- No integration yet: no workflow node, no API route, no CLI command, no UI. The
  scheduler needs an `Executor` that the workflow layer does not yet provide.
- Cost recordings are per fidelity id, not per `(fidelity, problem size)` bucket, so
  a large ligand reuses a small ligand's estimate.
- The diversity signal is scaffold/pocket equality, not a graded similarity.

## 7. What would justify promoting it

Per the project mandate, HAEL may only stop being experimental when a
pre-registered evaluation on a real task shows a meaningful benefit over the best
relevant baseline at matched compute, without regressions in calibration, diversity,
runtime or failure rate — on more than one target family and more than one property
task. Until then it stays `experimental`, is never the default, and every report
that mentions it must carry this document's caveat.
