"""Inline execution for hosts that cannot keep a worker process alive.

A serverless function is frozen as soon as the response is sent, so the embedded
worker thread that ``serve`` starts would stop mid-run. With
``HCS_RUN_MODE=inline`` the submitting request claims **exactly the run it just
created**, executes it through the normal :class:`Worker` and returns the
terminal state, so a hosted instance is usable without a second process.

Honest limits, deliberately not hidden:

* Once a run is claimed it executes to completion. ``inline_run_budget_seconds``
  only stops *further* attempts inside one request; it cannot interrupt the
  executor. A run longer than the platform's function duration is killed by the
  host, its lease expires and the normal stale-run recovery retries it later.
* Inline mode serialises work through the request. It is a preview/one-user
  mechanism, not a replacement for the queue and a real worker.
"""

from __future__ import annotations

import time

from sqlalchemy.orm import Session, sessionmaker

from ..core.config import Settings
from ..core.logging import get_logger
from ..database.base import get_session_factory
from ..database.models import Run
from ..workflow.registry import NodeRegistry
from .worker import Worker

logger = get_logger("hcs.inline")

TERMINAL = {"succeeded", "failed", "cancelled"}


def read_status(factory: sessionmaker[Session], run_id: str) -> str:
    with factory() as session:
        run = session.get(Run, run_id)
        return run.status if run is not None else "missing"


def execute_inline(
    settings: Settings,
    *,
    run_id: str,
    registry: NodeRegistry | None = None,
) -> str:
    """Execute one queued run inside the caller's request.

    Returns the run status after the attempt: ``succeeded``, ``failed``,
    ``cancelled``, or ``queued`` when the budget expired before the run could be
    claimed (it stays claimable by any worker).
    """
    factory = get_session_factory(settings)
    worker = Worker(
        settings=settings,
        factory=factory,
        registry=registry,
        worker_id=f"inline-{run_id}",
    )
    deadline = time.monotonic() + settings.inline_run_budget_seconds
    claimed_any = False
    while time.monotonic() < deadline:
        claimed = worker.run_once(only_run_id=run_id)
        if claimed is None:
            break
        claimed_any = True
        status = read_status(factory, run_id)
        if status in TERMINAL:
            return status
    status = read_status(factory, run_id)
    if not claimed_any:
        logger.info("inline run not claimed", extra={"run_id": run_id, "status": status})
    elif status not in TERMINAL:
        logger.warning("inline run still unfinished", extra={"run_id": run_id, "status": status})
    return status
