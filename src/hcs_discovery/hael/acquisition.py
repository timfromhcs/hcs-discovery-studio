"""The HAEL acquisition rule.

    A(c, f) = (EHVI(c, f | D) + λ · EIG(c, f | D) + ν · ΔDiversity(c, f)) / (C(c, f) + ε)

Every term is computed only from quantities the caller can justify:

* ``EHVI`` needs a *calibrated* predictive distribution for a single,
  task-specific objective vector. Without one there is no expected hypervolume
  improvement to compute, and the action is scored by a separately labelled
  exploratory policy instead.
* ``EIG`` is the analytic entropy reduction of a Gaussian observation,
  ``0.5 · ln(1 + σ_prior² / σ_observation²)``. It rises with current uncertainty
  and falls with measurement noise.
* ``ΔDiversity`` rewards reaching a scaffold or pocket not already selected. A
  duplicate scaffold contributes exactly zero.
* ``C`` comes from :class:`hcs_discovery.hael.cost.CostModel`, which refuses to
  guess.

The function is pure: same inputs and seed → same score. That is what makes the
decision trace replayable.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any, Literal

from ..core.errors import ValidationError
from .evidence import ObjectiveVector

ScoreMode = Literal["validated", "exploratory"]


class AcquisitionError(ValidationError):
    code = "acquisition_invalid"


class UnsupportedObjectiveDimensionError(AcquisitionError):
    """Raised for objective vectors this implementation cannot score exactly."""

    def __init__(self, dimensions: int) -> None:
        super().__init__(
            f"Exactly {dimensions} objective dimensions are not supported; only 1 and 2 are implemented.",
            details={
                "dimensions": dimensions,
                "hint": "Split the task, or rank on one dimension and keep the others as evidence.",
            },
        )


@dataclass(frozen=True)
class PredictiveDistribution:
    """What the proposed action is expected to tell us about one candidate.

    ``mean`` and ``sd`` are per objective dimension, in the dimension's own unit.
    ``prior_sd`` is the current uncertainty about the same quantity; it is the
    baseline that information gain is measured against.
    """

    mean: tuple[float, ...]
    sd: tuple[float, ...]
    prior_sd: tuple[float, ...] | None = None
    calibrated: bool = False
    calibration_id: str | None = None

    def __post_init__(self) -> None:
        if not self.mean:
            raise AcquisitionError("PredictiveDistribution needs at least one dimension.")
        if len(self.mean) != len(self.sd):
            raise AcquisitionError("PredictiveDistribution.mean and .sd must have the same length.")
        if self.prior_sd is not None and len(self.prior_sd) != len(self.mean):
            raise AcquisitionError("PredictiveDistribution.prior_sd must match the value length.")
        for value in (*self.mean, *self.sd, *(self.prior_sd or ())):
            if not math.isfinite(value):
                raise AcquisitionError("PredictiveDistribution values must be finite.")
        for sigma in self.sd:
            if sigma < 0:
                raise AcquisitionError("PredictiveDistribution.sd must be >= 0.")
        for sigma in self.prior_sd or ():
            if sigma < 0:
                raise AcquisitionError("PredictiveDistribution.prior_sd must be >= 0.")
        if self.calibrated and not self.calibration_id:
            raise AcquisitionError("A calibrated distribution needs a calibration_id so the claim can be audited.")


@dataclass(frozen=True)
class DiversityContext:
    """What the campaign has already covered."""

    selected_scaffolds: frozenset[str] = frozenset()
    selected_pockets: frozenset[str] = frozenset()
    candidate_scaffold: str | None = None
    candidate_pocket: str | None = None

    def novelty(self) -> float:
        """Mean novelty across available signals; 0.0 when nothing is known.

        Unknown diversity is reported as no gain rather than assumed novelty, so
        the term cannot quietly dominate the ranking.
        """
        signals: list[float] = []
        if self.candidate_scaffold:
            signals.append(0.0 if self.candidate_scaffold in self.selected_scaffolds else 1.0)
        if self.candidate_pocket:
            signals.append(0.0 if self.candidate_pocket in self.selected_pockets else 1.0)
        return sum(signals) / len(signals) if signals else 0.0


@dataclass(frozen=True)
class AcquisitionConfig:
    """Explicit, versioned weights. Defaults are a starting point, not constants of nature."""

    lambda_eig: float = 0.5
    nu_diversity: float = 0.25
    epsilon: float = 1e-9
    seed: int = 0
    samples: int = 512
    version: str = "hael-acquisition-1"

    def __post_init__(self) -> None:
        if self.epsilon <= 0:
            raise AcquisitionError("epsilon must be > 0 so the divisor cannot vanish.")
        if self.lambda_eig < 0 or self.nu_diversity < 0:
            raise AcquisitionError("lambda_eig and nu_diversity must be >= 0.")
        if self.samples < 1:
            raise AcquisitionError("samples must be >= 1.")
        if not self.version:
            raise AcquisitionError("version must not be empty; the rule is versioned.")

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "lambda_eig": self.lambda_eig,
            "nu_diversity": self.nu_diversity,
            "epsilon": self.epsilon,
            "seed": self.seed,
            "samples": self.samples,
        }


@dataclass(frozen=True)
class ActionScore:
    """One scored (candidate, fidelity) option, with everything the term used."""

    candidate_id: str
    fidelity_id: str
    acquisition: float
    ehvi: float
    eig: float
    diversity: float
    cost: float
    mode: ScoreMode
    reasons: tuple[str, ...] = field(default_factory=tuple)
    features: dict[str, Any] = field(default_factory=dict)

    @property
    def validated(self) -> bool:
        return self.mode == "validated"

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "fidelity_id": self.fidelity_id,
            "acquisition": self.acquisition,
            "ehvi": self.ehvi,
            "eig": self.eig,
            "diversity": self.diversity,
            "cost": self.cost,
            "mode": self.mode,
            "reasons": list(self.reasons),
            "features": dict(self.features),
        }


def score_action(
    *,
    candidate_id: str,
    fidelity_id: str,
    vector: ObjectiveVector,
    front: tuple[tuple[float, ...], ...],
    distribution: PredictiveDistribution | None,
    diversity: DiversityContext,
    cost: float,
    config: AcquisitionConfig,
) -> ActionScore:
    """Score one action. Raises rather than inventing an improvement term."""
    if not math.isfinite(cost) or cost < 0:
        raise AcquisitionError(f"cost must be finite and >= 0, got {cost!r}")
    if len(vector.dimensions) not in (1, 2):
        raise UnsupportedObjectiveDimensionError(len(vector.dimensions))

    reasons: list[str] = []
    mode: ScoreMode = "validated"
    ehvi = 0.0
    eig = 0.0
    if distribution is None:
        mode = "exploratory"
        reasons.append("no_predictive_distribution")
    else:
        if len(distribution.mean) != len(vector.dimensions):
            raise AcquisitionError(
                "PredictiveDistribution length does not match the objective vector.",
                details={
                    "distribution": len(distribution.mean),
                    "dimensions": len(vector.dimensions),
                },
            )
        if not distribution.calibrated:
            mode = "exploratory"
            reasons.append("uncalibrated_distribution")
        ehvi = expected_hypervolume_improvement(vector, front, distribution, config)
        eig = expected_information_gain(distribution)

    novelty = diversity.novelty()
    benefit = ehvi + config.lambda_eig * eig + config.nu_diversity * novelty
    acquisition = benefit / (cost + config.epsilon)

    return ActionScore(
        candidate_id=candidate_id,
        fidelity_id=fidelity_id,
        acquisition=acquisition,
        ehvi=ehvi,
        eig=eig,
        diversity=novelty,
        cost=cost,
        mode=mode,
        reasons=tuple(reasons),
        features={
            "benefit": benefit,
            "dimensions": len(vector.dimensions),
            "front_size": len(front),
            "task_id": vector.task_id,
            "calibration_id": distribution.calibration_id if distribution else None,
            "prior_sd": list(distribution.prior_sd) if distribution and distribution.prior_sd else None,
            "sd": list(distribution.sd) if distribution else None,
            "mean": list(distribution.mean) if distribution else None,
        },
    )


def expected_information_gain(distribution: PredictiveDistribution) -> float:
    """Analytic Gaussian entropy reduction, summed over dimensions.

    Observing a quantity with prior variance ``σ0²`` through a measurement with
    variance ``σn²`` leaves ``1/(1/σ0² + 1/σn²)``. The differential entropy drops
    by ``0.5 · ln(1 + σ0²/σn²)``. Zero noise or zero prior uncertainty means no
    information, and the function says so instead of dividing by zero.
    """
    if distribution.prior_sd is None:
        return 0.0
    total = 0.0
    for prior_sigma, sigma in zip(distribution.prior_sd, distribution.sd, strict=True):
        if prior_sigma <= 0 or sigma <= 0:
            continue
        total += 0.5 * math.log1p((prior_sigma * prior_sigma) / (sigma * sigma))
    return total


def expected_hypervolume_improvement(
    vector: ObjectiveVector,
    front: tuple[tuple[float, ...], ...],
    distribution: PredictiveDistribution,
    config: AcquisitionConfig,
) -> float:
    """Expected hypervolume improvement of adding one candidate.

    One dimension uses the closed-form expected improvement. Two dimensions use a
    seeded Monte-Carlo estimate over ``config.samples`` samples with a reference
    point just below the combined bounding box; this is an approximation and the
    sample count and seed are recorded in the decision features.
    """
    means = _as_maximisation(vector, distribution.mean)
    sigmas = tuple(abs(float(value)) for value in distribution.sd)
    front_points = tuple(_as_maximisation(vector, point) for point in front)

    if len(vector.dimensions) == 1:
        return _expected_improvement_1d(means[0], sigmas[0], front_points)

    return _ehvi_monte_carlo(means, sigmas, front_points, config)


def _as_maximisation(vector: ObjectiveVector, point: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(
        value if dimension.direction == "higher" else -value
        for dimension, value in zip(vector.dimensions, point, strict=True)
    )


def _expected_improvement_1d(mean: float, sigma: float, front: tuple[tuple[float, ...], ...]) -> float:
    """EI = (m − best)·Φ(z) + σ·φ(z) against the best validated value.

    With no incumbent the zero point of the dimension is the reference, so a
    prediction only earns improvement when it is on the good side of zero. That
    keeps the term monotone in the predicted value in both directions.
    """
    best = max((point[0] for point in front), default=None)
    if best is None:
        return max(0.0, mean)
    if sigma == 0:
        return max(0.0, mean - best)
    z = (mean - best) / sigma
    return max(0.0, (mean - best) * _normal_cdf(z) + sigma * _normal_pdf(z))


def _ehvi_monte_carlo(
    means: tuple[float, ...],
    sigmas: tuple[float, ...],
    front: tuple[tuple[float, ...], ...],
    config: AcquisitionConfig,
) -> float:
    rng = random.Random(config.seed)
    samples = [
        (
            rng.gauss(means[0], sigmas[0]) if sigmas[0] > 0 else means[0],
            rng.gauss(means[1], sigmas[1]) if sigmas[1] > 0 else means[1],
        )
        for _ in range(config.samples)
    ]
    # The reference point is fixed by the distribution and the current front, not
    # by the random draws, so the estimate does not depend on an outlier sample.
    # With no incumbent, improvement is measured from the dimension's zero point.
    nadir = tuple(mean - 3.0 * sigma for mean, sigma in zip(means, sigmas, strict=True))
    reference = (
        (min([nadir[0], *(point[0] for point in front)]) if front else min(0.0, nadir[0])),
        (min([nadir[1], *(point[1] for point in front)]) if front else min(0.0, nadir[1])),
    )
    reference = (reference[0] - 1e-9 * max(1.0, abs(reference[0])), reference[1] - 1e-9 * max(1.0, abs(reference[1])))

    baseline = _hypervolume_2d(front, reference)
    total = 0.0
    for sample in samples:
        total += _hypervolume_2d((*front, sample), reference) - baseline
    return total / len(samples)


def _hypervolume_2d(points: tuple[tuple[float, ...], ...], reference: tuple[float, float]) -> float:
    """Union area dominated by ``points`` inside the box from ``reference`` upward."""
    relevant = sorted(
        (x, y) for x, y in ((float(p[0]), float(p[1])) for p in points) if x > reference[0] and y > reference[1]
    )
    if not relevant:
        return 0.0
    edges = [reference[0], *[x for x, _ in relevant]]
    area = 0.0
    for left, right in pairwise(edges):
        if right <= left:
            continue
        # Height of this vertical slice: the best y among points that reach it.
        height = max(y for x, y in relevant if x >= right) - reference[1]
        if height > 0:
            area += (right - left) * height
    return area


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _normal_pdf(value: float) -> float:
    return math.exp(-0.5 * value * value) / math.sqrt(2.0 * math.pi)
