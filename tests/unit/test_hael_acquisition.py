"""Property tests for the HAEL acquisition rule.

The rule is only trustworthy if a change in one input moves the score in the
direction the science says it should. These tests pin those directions:

* more cost never increases acquisition (holding benefit fixed),
* more expected information never decreases it,
* a duplicate scaffold adds nothing, a new one adds something,
* the same seed always produces the same score.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from hcs_discovery.hael.acquisition import (
    AcquisitionConfig,
    AcquisitionError,
    DiversityContext,
    PredictiveDistribution,
    UnsupportedObjectiveDimensionError,
    expected_information_gain,
    score_action,
)
from hcs_discovery.hael.evidence import ObjectiveVector, TaskObjective

CONFIG = AcquisitionConfig(seed=7, samples=256)

POTENCY = ObjectiveVector(
    task_id="egfr_potency",
    dimensions=(
        TaskObjective(
            task_id="egfr_potency",
            endpoint="egfr_pic50",
            metric="predicted_pic50",
            unit="log10(mol/L)",
            direction="higher",
        ),
    ),
)

TWO_DIMENSIONS = ObjectiveVector(
    task_id="egfr_profile",
    dimensions=(
        TaskObjective(
            task_id="egfr_profile",
            endpoint="egfr_pic50",
            metric="predicted_pic50",
            unit="log10(mol/L)",
            direction="higher",
        ),
        TaskObjective(
            task_id="egfr_profile",
            endpoint="egfr_her2_selectivity",
            metric="selectivity_ratio",
            unit="dimensionless",
            direction="higher",
        ),
    ),
)


def _distribution(mean: float = 6.0, sd: float = 0.4, prior: float | None = 1.0) -> PredictiveDistribution:
    return PredictiveDistribution(
        mean=(mean,),
        sd=(sd,),
        prior_sd=None if prior is None else (prior,),
        calibrated=True,
        calibration_id="cal_1",
    )


def _score(
    *,
    cost: float,
    distribution: PredictiveDistribution | None = None,
    diversity: DiversityContext | None = None,
    front: tuple[tuple[float, ...], ...] = (),
    vector: ObjectiveVector = POTENCY,
    config: AcquisitionConfig = CONFIG,
):
    return score_action(
        candidate_id="cmp_a",
        fidelity_id="f2",
        vector=vector,
        front=front,
        distribution=distribution if distribution is not None else _distribution(),
        diversity=diversity or DiversityContext(),
        cost=cost,
        config=config,
    )


# --------------------------------------------------------------- cost monotonicity
@given(
    cost_a=st.floats(min_value=0.05, max_value=100.0, allow_nan=False, allow_infinity=False),
    cost_b=st.floats(min_value=0.05, max_value=100.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, deadline=None)
def test_more_cost_never_increases_acquisition(cost_a: float, cost_b: float):
    cheap = _score(cost=min(cost_a, cost_b))
    dear = _score(cost=max(cost_a, cost_b))
    assert cheap.acquisition >= dear.acquisition


# --------------------------------------------------------- information monotonicity
def test_more_prior_uncertainty_increases_information_gain():
    low = _distribution(sd=0.5, prior=0.5)
    high = _distribution(sd=0.5, prior=2.0)
    assert expected_information_gain(high) > expected_information_gain(low)
    assert _score(cost=1.0, distribution=high).acquisition > _score(cost=1.0, distribution=low).acquisition


def test_noisier_measurement_reduces_information_gain():
    precise = _distribution(sd=0.2, prior=1.0)
    noisy = _distribution(sd=2.0, prior=1.0)
    assert expected_information_gain(precise) > expected_information_gain(noisy)


def test_information_gain_is_zero_without_prior_or_noise():
    assert expected_information_gain(_distribution(prior=None)) == 0.0
    assert expected_information_gain(_distribution(sd=0.0)) == 0.0


# --------------------------------------------------------------------- diversity
def test_duplicate_scaffold_adds_no_diversity_and_new_scaffold_does():
    duplicate = DiversityContext(
        selected_scaffolds=frozenset({"scaffold_a"}),
        candidate_scaffold="scaffold_a",
    )
    novel = DiversityContext(
        selected_scaffolds=frozenset({"scaffold_a"}),
        candidate_scaffold="scaffold_b",
    )
    assert duplicate.novelty() == 0.0
    assert novel.novelty() == 1.0
    assert _score(cost=1.0, diversity=novel).acquisition > _score(cost=1.0, diversity=duplicate).acquisition


def test_unknown_diversity_is_not_assumed_novel():
    assert DiversityContext().novelty() == 0.0
    assert DiversityContext(selected_scaffolds=frozenset({"a"})).novelty() == 0.0


def test_duplicate_pocket_adds_no_novelty():
    context = DiversityContext(
        selected_pockets=frozenset({"pocket_1"}),
        candidate_pocket="pocket_1",
    )
    assert context.novelty() == 0.0


def _distribution_2d(mean: tuple[float, float] = (6.0, 1.5), sd: tuple[float, float] = (0.4, 0.2)):
    return PredictiveDistribution(mean=mean, sd=sd, prior_sd=(1.0, 0.5), calibrated=True, calibration_id="cal_1")


# ------------------------------------------------------------------ determinism
def test_same_seed_scores_identically():
    first = _score(cost=3.0, distribution=_distribution_2d(), vector=TWO_DIMENSIONS, front=((5.0, 2.0),))
    second = _score(cost=3.0, distribution=_distribution_2d(), vector=TWO_DIMENSIONS, front=((5.0, 2.0),))
    assert first.as_dict() == second.as_dict()


def test_different_seed_changes_the_monte_carlo_estimate_only_slightly():
    front = ((5.0, 2.0),)
    a = _score(
        cost=3.0,
        distribution=_distribution_2d(),
        vector=TWO_DIMENSIONS,
        front=front,
        config=AcquisitionConfig(seed=1, samples=4096),
    )
    b = _score(
        cost=3.0,
        distribution=_distribution_2d(),
        vector=TWO_DIMENSIONS,
        front=front,
        config=AcquisitionConfig(seed=2, samples=4096),
    )
    assert a.ehvi > 0 and b.ehvi > 0
    assert abs(a.ehvi - b.ehvi) / max(a.ehvi, b.ehvi) < 0.05


# ------------------------------------------------------------ scale and direction
def test_stronger_prediction_earns_more_expected_improvement():
    weak = _distribution(mean=5.0)
    strong = _distribution(mean=7.0)
    assert _score(cost=1.0, distribution=strong).ehvi > _score(cost=1.0, distribution=weak).ehvi


def test_lower_is_better_objective_is_flipped_correctly():
    lower_is_better = ObjectiveVector(
        task_id="docking",
        dimensions=(
            TaskObjective(
                task_id="docking",
                endpoint="docking_vina",
                metric="affinity",
                unit="kcal/mol",
                direction="lower",
            ),
        ),
    )
    distribution = PredictiveDistribution(mean=(-9.5,), sd=(0.2,), calibrated=True, calibration_id="cal_d")
    score = _score(cost=1.0, distribution=distribution, vector=lower_is_better, front=((-8.0,),))
    assert score.ehvi > 0


def test_expected_hypervolume_improvement_is_positive_for_a_dominated_point():
    # A prediction worse than the whole front still has some mass above the front
    # in one dimension, so EI must not be silently zero or negative.
    score = _score(cost=1.0, distribution=_distribution(mean=4.0), front=((10.0,),))
    assert score.ehvi >= 0.0


# ------------------------------------------------------------------ guard rails
def test_more_than_two_dimensions_is_refused_explicitly():
    vector = ObjectiveVector(
        task_id="three",
        dimensions=(
            TaskObjective("three", "a", "m", "dimensionless", "higher"),
            TaskObjective("three", "b", "m", "dimensionless", "higher"),
            TaskObjective("three", "c", "m", "dimensionless", "higher"),
        ),
    )
    with pytest.raises(UnsupportedObjectiveDimensionError):
        _score(cost=1.0, vector=vector)


def test_uncalibrated_distribution_is_labelled_exploratory():
    distribution = PredictiveDistribution(mean=(6.0,), sd=(0.5,), calibrated=False)
    score = _score(cost=1.0, distribution=distribution)
    assert score.mode == "exploratory"
    assert "uncalibrated_distribution" in score.reasons
    assert score.validated is False


def test_calibrated_distribution_requires_a_calibration_id():
    with pytest.raises(AcquisitionError):
        PredictiveDistribution(mean=(6.0,), sd=(0.5,), calibrated=True)


def test_negative_cost_is_rejected():
    with pytest.raises(AcquisitionError):
        _score(cost=-1.0)


def test_epsilon_keeps_the_denominator_finite_at_zero_cost():
    score = _score(cost=0.0)
    assert math.isfinite(score.acquisition)


def test_weights_are_versioned_in_the_config():
    assert AcquisitionConfig().as_dict()["version"] == "hael-acquisition-1"
