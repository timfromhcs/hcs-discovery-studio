"""Matched-budget ablation of the HAEL scheduler against simple selection policies.

Run from the repository root:

    uv run python scripts/science/benchmark_hael.py
    uv run python scripts/science/benchmark_hael.py --json

What this measures
------------------
A synthetic search: 24 candidates with a latent potency, three fidelities with
different noise and cost, and a fixed wall-clock budget. Every policy spends the
same budget, and we report how much of the true best potency it found.

What this does **not** measure
------------------------------
Anything chemical. The latent values are generated, so this is an ablation of the
*deciding*, not evidence that HAEL finds better molecules. A real evaluation needs
a task-specific dataset, a pre-registered split and inspected test data; see
``docs/research/HAEL.md``.

The result is recorded, not asserted: if HAEL does not beat the baselines, that
is a finding, and HAEL stays experimental.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from hcs_discovery.hael.acquisition import AcquisitionConfig, PredictiveDistribution
from hcs_discovery.hael.cost import CostModel
from hcs_discovery.hael.evidence import (
    EvidenceItem,
    EvidenceLedger,
    ObjectiveVector,
    TaskObjective,
)
from hcs_discovery.hael.scheduler import ActionResult, Candidate, Fidelity, Scheduler, SchedulerConfig

CANDIDATES = 24
BUDGET_SECONDS = 90.0
SEEDS = range(1, 21)

VECTOR = ObjectiveVector(
    task_id="ablation_potency",
    dimensions=(
        TaskObjective(
            task_id="ablation_potency",
            endpoint="ablation_pic50",
            metric="latent_pic50",
            unit="log10(mol/L)",
            direction="higher",
        ),
    ),
)


@dataclass(frozen=True)
class Rung:
    fidelity_id: str
    name: str
    cost: float
    noise: float
    rank: int


RUNGS: tuple[Rung, ...] = (
    Rung("f1", "Descriptor proxy", cost=1.0, noise=1.10, rank=1),
    Rung("f2", "Endpoint model", cost=8.0, noise=0.35, rank=2),
    Rung("f3", "Reference assay", cost=35.0, noise=0.10, rank=3),
)


@dataclass
class Scenario:
    """Ground truth plus a deterministic measurement function."""

    seed: int
    latent: dict[str, float]
    scaffolds: dict[str, str]

    @classmethod
    def build(cls, seed: int) -> Scenario:
        rng = random.Random(seed)
        latent = {f"cmp_{index:02d}": rng.gauss(5.5, 1.2) for index in range(CANDIDATES)}
        scaffolds = {f"cmp_{index:02d}": f"scaffold_{index % 5}" for index in range(CANDIDATES)}
        return cls(seed=seed, latent=latent, scaffolds=scaffolds)

    def measure(self, candidate_id: str, rung: Rung, draw: int) -> float:
        rng = random.Random(f"{self.seed}|{candidate_id}|{rung.fidelity_id}|{draw}")
        return self.latent[candidate_id] + rng.gauss(0.0, rung.noise)

    def predict(self, candidate_id: str, rung: Rung) -> PredictiveDistribution:
        # A predictive distribution that is honest about its own noise.
        return PredictiveDistribution(
            mean=(self.latent[candidate_id],),
            sd=(rung.noise,),
            prior_sd=(1.5,),
            calibrated=True,
            calibration_id=f"synthetic-{rung.fidelity_id}",
        )


def _evidence(candidate_id: str, rung: Rung, value: float, index: int) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=f"ev_{candidate_id}_{rung.fidelity_id}_{index}",
        candidate_id=candidate_id,
        endpoint="ablation_pic50",
        value=value,
        unit="log10(mol/L)",
        direction="higher",
        method=rung.name,
        engine="synthetic-ablation",
        engine_version="1",
        status="validated",
        uncertainty_kind="conformal",
        uncertainty_low=value - rung.noise,
        uncertainty_high=value + rung.noise,
        calibration_id=f"synthetic-{rung.fidelity_id}",
        applicability_domain="in_domain",
        cost_seconds=rung.cost,
    )


def _fidelities() -> list[Fidelity]:
    return [Fidelity(rung.fidelity_id, rung.name, rank=rung.rank) for rung in RUNGS]


def _baseline_costs() -> CostModel:
    costs = CostModel()
    for rung in RUNGS:
        costs.set_default(rung.fidelity_id, rung.cost)
    return costs


# --------------------------------------------------------------------- policies
Policy = Callable[[Scenario, str], float]


def run_hael(scenario: Scenario, policy: str) -> float:
    ledger = EvidenceLedger()
    counter = {"n": 0}

    def execute(candidate: Candidate, fidelity: Fidelity) -> ActionResult:
        rung = next(r for r in RUNGS if r.fidelity_id == fidelity.fidelity_id)
        counter["n"] += 1
        value = scenario.measure(candidate.candidate_id, rung, counter["n"])
        return ActionResult(
            evidence=(_evidence(candidate.candidate_id, rung, value, counter["n"]),),
            cost_seconds=rung.cost,
        )

    config = SchedulerConfig(
        budget_seconds=BUDGET_SECONDS,
        acquisition=AcquisitionConfig(seed=scenario.seed, samples=128),
        allow_exploratory=False,
    )
    if policy == "cost_unaware":
        costs = CostModel()
        for rung in RUNGS:
            costs.set_default(rung.fidelity_id, 1.0)
    else:
        costs = _baseline_costs()

    scheduler = Scheduler(
        vector=VECTOR,
        ledger=ledger,
        costs=costs,
        config=config,
        distribution=lambda candidate, fidelity: scenario.predict(
            candidate.candidate_id, next(r for r in RUNGS if r.fidelity_id == fidelity.fidelity_id)
        ),
    )
    candidates = [Candidate(cid, scaffold_id=scaffold) for cid, scaffold in scenario.scaffolds.items()]
    scheduler.run(candidates, _fidelities(), execute)
    return _selected_latent(scenario, ledger)


def run_random(scenario: Scenario, policy: str) -> float:
    rng = random.Random(scenario.seed * 7919)
    ledger = EvidenceLedger()
    spent = 0.0
    index = 0
    while True:
        legal = [rung for rung in RUNGS if spent + rung.cost <= BUDGET_SECONDS]
        if not legal:
            break
        rung = rng.choice(legal)
        candidate_id = rng.choice(sorted(scenario.latent))
        index += 1
        spent += rung.cost
        ledger.add(_evidence(candidate_id, rung, scenario.measure(candidate_id, rung, index), index))
    return _selected_latent(scenario, ledger)


def run_static_cascade(scenario: Scenario, policy: str) -> float:
    ledger = EvidenceLedger()
    spent = 0.0
    index = 0
    for candidate_id in sorted(scenario.latent):
        for rung in RUNGS:
            if spent + rung.cost > BUDGET_SECONDS:
                return _selected_latent(scenario, ledger)
            index += 1
            spent += rung.cost
            ledger.add(_evidence(candidate_id, rung, scenario.measure(candidate_id, rung, index), index))
    return _selected_latent(scenario, ledger)


def run_descriptor_only(scenario: Scenario, policy: str) -> float:
    ledger = EvidenceLedger()
    spent = 0.0
    cheap = RUNGS[0]
    for draw, candidate_id in enumerate(sorted(scenario.latent), start=1):
        if spent + cheap.cost > BUDGET_SECONDS:
            break
        spent += cheap.cost
        ledger.add(_evidence(candidate_id, cheap, scenario.measure(candidate_id, cheap, draw), draw))
    return _selected_latent(scenario, ledger)


def run_round_robin(scenario: Scenario, policy: str) -> float:
    """Spend on the best rung of each candidate before moving on: a fair baseline."""
    ledger = EvidenceLedger()
    spent = 0.0
    best = RUNGS[-1]
    for draw, candidate_id in enumerate(sorted(scenario.latent), start=1):
        if spent + best.cost > BUDGET_SECONDS:
            break
        spent += best.cost
        ledger.add(_evidence(candidate_id, best, scenario.measure(candidate_id, best, draw), draw))
    return _selected_latent(scenario, ledger)


POLICIES: dict[str, Policy] = {
    "hael": run_hael,
    "hael_cost_unaware": lambda scenario, policy: run_hael(scenario, "cost_unaware"),
    "random": run_random,
    "static_cascade": run_static_cascade,
    "descriptor_only": run_descriptor_only,
    "best_rung_round_robin": run_round_robin,
}


def _selected_latent(scenario: Scenario, ledger: EvidenceLedger) -> float:
    """Latent potency of the candidate the campaign would pick.

    Selection uses the mean of each candidate's own measurements, which is what a
    researcher would do with noisy numbers. Scoring the *selected candidate's true
    value* rather than the best observed number keeps measurement noise from
    being rewarded.
    """
    observed: dict[str, list[float]] = {}
    for item in ledger:
        observed.setdefault(item.candidate_id, []).append(item.value)
    if not observed:
        return float("nan")
    best = max(sorted(observed), key=lambda cid: statistics.fmean(observed[cid]))
    return scenario.latent[best]


# ------------------------------------------------------------------------ report
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Machine-readable output.")
    args = parser.parse_args()

    results: dict[str, list[float]] = {name: [] for name in POLICIES}
    for seed in SEEDS:
        scenario = Scenario.build(seed)
        optimum = max(scenario.latent.values())
        for name, policy in POLICIES.items():
            found = policy(scenario, name)
            results[name].append(found - optimum)  # regret: <= 0, closer to 0 is better

    summary: dict[str, dict[str, float]] = {}
    for name, regrets in results.items():
        summary[name] = {
            "median_regret": round(statistics.median(regrets), 4),
            "mean_regret": round(statistics.fmean(regrets), 4),
            "worst_regret": round(min(regrets), 4),
            "best_regret": round(max(regrets), 4),
        }

    payload: dict[str, Any] = {
        "kind": "synthetic_scheduler_ablation",
        "seeds": len(list(SEEDS)),
        "budget_seconds": BUDGET_SECONDS,
        "candidates": CANDIDATES,
        "rungs": [{"id": rung.fidelity_id, "cost": rung.cost, "noise": rung.noise} for rung in RUNGS],
        "metric": "regret_of_selected_candidate (0 is perfect, negative is worse)",
        "results": summary,
        "caveat": "Synthetic latent values. This ablates the scheduler, not chemistry.",
    }

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    print(
        f"Synthetic scheduler ablation: {len(list(SEEDS))} seeds, {BUDGET_SECONDS:.0f}s budget, {CANDIDATES} candidates"
    )
    print(f"{'policy':<24}{'median':>10}{'mean':>10}{'worst':>10}{'best':>10}")
    for name, row in sorted(summary.items(), key=lambda kv: kv[1]["mean_regret"], reverse=True):
        print(
            f"{name:<24}{row['median_regret']:>10.4f}{row['mean_regret']:>10.4f}"
            f"{row['worst_regret']:>10.4f}{row['best_regret']:>10.4f}"
        )
    print("\nRegret is relative to the true best latent potency; 0 would be perfect.")
    print("Synthetic data: this ablates the deciding, not the chemistry.")
    return 0


def main_sequence() -> Sequence[str]:
    return tuple(POLICIES)


if __name__ == "__main__":
    raise SystemExit(main())
