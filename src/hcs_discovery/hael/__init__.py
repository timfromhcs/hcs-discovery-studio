"""HCS Adaptive Evidence Ladder (HAEL).

HAEL is an original scheduling method assembled from established ideas:
multi-fidelity optimisation, expected hypervolume improvement, expected
information gain, calibrated uncertainty, applicability-domain checks, scaffold
diversity and measured compute cost.

The package deliberately contains no science of its own. It decides *which*
calculation is worth running next and refuses to promote evidence that has not
earned it. Every module is pure Python and deterministic for a fixed seed, so
the decision trace can be tested and replayed.

Status: **experimental**. This is not a published algorithm and it has no
validated advantage over a static cascade yet; see
``docs/research/HAEL.md`` for the current evidence, ablations and limits.
"""

from __future__ import annotations

from .acquisition import (
    AcquisitionConfig,
    ActionScore,
    DiversityContext,
    PredictiveDistribution,
    score_action,
)
from .cost import CostModel, UnknownCostError
from .evidence import (
    ApplicabilityDomain,
    EvidenceError,
    EvidenceItem,
    EvidenceLedger,
    EvidenceStatus,
    GateDecision,
    ObjectiveVector,
    TaskObjective,
    UncertaintyKind,
)
from .scheduler import (
    ActionResult,
    Candidate,
    Executor,
    Fidelity,
    Scheduler,
    SchedulerConfig,
    SchedulerTrace,
    Step,
)

__all__ = [
    "AcquisitionConfig",
    "ActionResult",
    "ActionScore",
    "ApplicabilityDomain",
    "Candidate",
    "CostModel",
    "DiversityContext",
    "EvidenceError",
    "EvidenceItem",
    "EvidenceLedger",
    "EvidenceStatus",
    "Executor",
    "Fidelity",
    "GateDecision",
    "ObjectiveVector",
    "PredictiveDistribution",
    "Scheduler",
    "SchedulerConfig",
    "SchedulerTrace",
    "Step",
    "TaskObjective",
    "UncertaintyKind",
    "UnknownCostError",
    "score_action",
]
