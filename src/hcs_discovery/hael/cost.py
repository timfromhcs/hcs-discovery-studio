"""Measured compute cost, not guessed compute cost.

HAEL divides expected benefit by cost, so a wrong cost model silently redirects
compute. This module therefore refuses to invent a number: an action without any
measured observation and without an explicitly configured default is
``unknown_cost`` and is skipped, not estimated from marketing material.

Observations are wall-clock seconds recorded by the run that actually executed
the action. The estimate is a rolling percentile over the most recent window,
defaulting to p90 so the scheduler is pessimistic about slow tails.
"""

from __future__ import annotations

import math
import statistics
from collections import deque
from collections.abc import Iterable

from ..core.errors import AppError


class UnknownCostError(AppError):
    """Raised when an action has no measured and no configured cost."""

    code = "unknown_cost"
    http_status = 422
    exit_code = 3

    def __init__(self, action_key: str) -> None:
        super().__init__(
            f"No measured cost for action '{action_key}' and no configured default.",
            details={
                "action_key": action_key,
                "hint": "Run the action once and record its duration, or set an explicit default cost.",
            },
        )
        self.action_key = action_key


class CostModel:
    """Rolling per-action cost estimates with an explicit cold-start policy."""

    def __init__(
        self,
        *,
        percentile: float = 0.9,
        window: int = 20,
        defaults: dict[str, float] | None = None,
    ) -> None:
        if not 0.0 <= percentile <= 1.0:
            raise ValueError(f"percentile must be within [0, 1], got {percentile!r}")
        if window < 1:
            raise ValueError(f"window must be >= 1, got {window!r}")
        self.percentile = percentile
        self.window = window
        self._observations: dict[str, deque[float]] = {}
        self._defaults: dict[str, float] = dict(defaults or {})

    def default_for(self, action_key: str) -> float | None:
        return self._defaults.get(action_key)

    def set_default(self, action_key: str, seconds: float) -> None:
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError(f"default cost for '{action_key}' must be a positive finite number")
        self._defaults[action_key] = seconds

    def record(self, action_key: str, seconds: float) -> None:
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError(f"cost observation for '{action_key}' must be finite and >= 0")
        self._observations.setdefault(action_key, deque(maxlen=self.window)).append(float(seconds))

    def observations(self, action_key: str) -> tuple[float, ...]:
        return tuple(self._observations.get(action_key, ()))

    def estimate(self, action_key: str) -> float:
        """Return the cost estimate in seconds or raise :class:`UnknownCostError`."""
        samples = self._observations.get(action_key)
        if samples:
            return _percentile(samples, self.percentile)
        default = self._defaults.get(action_key)
        if default is not None:
            return default
        raise UnknownCostError(action_key)

    def cost_known(self, action_key: str) -> bool:
        return bool(self._observations.get(action_key)) or action_key in self._defaults

    def as_dict(self) -> dict[str, object]:
        return {
            "percentile": self.percentile,
            "window": self.window,
            "defaults": dict(sorted(self._defaults.items())),
            "observations": {key: list(values) for key, values in sorted(self._observations.items())},
        }


def _percentile(samples: Iterable[float], fraction: float) -> float:
    """Linear-interpolated percentile of a small sample."""
    values = sorted(samples)
    if not values:
        raise ValueError("percentile of an empty sample is undefined")
    if len(values) == 1:
        return values[0]
    # statistics.quantiles needs at least two points and excludes the extremes,
    # so interpolate directly to keep p0 == min and p1 == max.
    position = fraction * (len(values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[int(position)]
    weight = position - lower
    return values[lower] * (1 - weight) + values[upper] * weight


def median(samples: Iterable[float]) -> float:
    """Median helper used by the ablation script and diagnostics."""
    return statistics.median(list(samples))
