"""Lease-based persistent job queue on top of the relational database.

Runs are claimed with a conditional UPDATE, so two workers cannot claim the same
run. Leases expire, which lets a crashed worker's run be recovered instead of
hanging forever. Execution is at-least-once: nodes are re-executed after recovery,
which is safe because node handlers must be deterministic or cache-keyed.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session, sessionmaker

from ..core.config import Settings
from ..core.errors import ConflictError, NotFoundError
from ..core.redaction import redact_text
from ..core.timeutil import db_now
from ..database.models import Run, RunEvent, RunNode

CLAIMABLE = {"queued"}


def new_event(
    session: Session,
    run_id: str,
    event_type: str,
    message: str = "",
    *,
    level: str = "info",
    data: dict[str, Any] | None = None,
) -> RunEvent:
    current = session.execute(
        select(RunEvent.seq).where(RunEvent.run_id == run_id).order_by(RunEvent.seq.desc()).limit(1)
    ).scalar()
    event = RunEvent(
        run_id=run_id,
        seq=(current or 0) + 1,
        type=event_type,
        level=level,
        message=redact_text(message)[:8000],
        data=data or {},
    )
    session.add(event)
    return event


def claim_next_run(
    factory: sessionmaker[Session],
    *,
    worker_id: str,
    lease_seconds: int,
) -> Run | None:
    with factory() as session:
        candidate = session.execute(
            select(Run).where(Run.status.in_(CLAIMABLE)).order_by(Run.created_at, Run.id).limit(1)
        ).scalar_one_or_none()
        if candidate is None:
            return None
        now = db_now()
        result = cast(
            CursorResult[Any],
            session.execute(
                update(Run)
                .where(Run.id == candidate.id, Run.status == "queued")
                .values(
                    status="running",
                    lease_owner=worker_id,
                    lease_expires_at=now + timedelta(seconds=lease_seconds),
                    heartbeat_at=now,
                    started_at=Run.started_at,
                    attempt=Run.attempt + 1,
                )
            ),
        )
        if result.rowcount != 1:
            session.rollback()
            return None
        session.commit()
        session.expire_all()
        run = session.get(Run, candidate.id)
        if run is None:
            return None
        session.expunge(run)
        return run


def heartbeat(factory: sessionmaker[Session], run_id: str, *, worker_id: str, lease_seconds: int) -> bool:
    with factory() as session:
        result = cast(
            CursorResult[Any],
            session.execute(
                update(Run)
                .where(Run.id == run_id, Run.lease_owner == worker_id)
                .values(
                    heartbeat_at=db_now(),
                    lease_expires_at=db_now() + timedelta(seconds=lease_seconds),
                )
            ),
        )
        session.commit()
        return result.rowcount == 1


def recover_stale_runs(factory: sessionmaker[Session], settings: Settings) -> list[dict[str, str]]:
    """Return runs whose lease expired, requeueing or failing them visibly."""
    recovered: list[dict[str, str]] = []
    with factory() as session:
        now = db_now()
        stale = (
            session.execute(
                select(Run).where(
                    Run.status == "running",
                    Run.lease_expires_at.is_not(None),
                    Run.lease_expires_at < now,
                )
            )
            .scalars()
            .all()
        )
        for run in stale:
            running_nodes = (
                session.execute(select(RunNode).where(RunNode.run_id == run.id, RunNode.status == "running"))
                .scalars()
                .all()
            )
            for node in running_nodes:
                node.status = "failed"
                node.finished_at = now
                node.error = {
                    "code": "lease_expired",
                    "message": "Worker lease expired during this node.",
                }
            if run.attempt >= settings.max_run_attempts:
                run.status = "failed"
                run.error = {
                    "code": "lease_expired",
                    "message": "Worker lease expired and the retry budget is exhausted.",
                }
                run.finished_at = now
                run.lease_owner = None
                run.lease_expires_at = None
                new_event(
                    session,
                    run.id,
                    "run.failed",
                    "Run failed: worker lease expired.",
                    level="error",
                )
                recovered.append({"run_id": run.id, "outcome": "failed"})
            else:
                run.status = "queued"
                run.lease_owner = None
                run.lease_expires_at = None
                new_event(
                    session,
                    run.id,
                    "run.requeued",
                    "Worker lease expired; run requeued for a fresh execution.",
                    level="warning",
                )
                recovered.append({"run_id": run.id, "outcome": "requeued"})
        session.commit()
    return recovered


def request_cancel(session: Session, run_id: str) -> Run:
    run = session.get(Run, run_id)
    if run is None:
        raise NotFoundError(f"Run '{run_id}' does not exist.")
    if run.status in {"succeeded", "failed", "cancelled"}:
        raise ConflictError(f"Run is already {run.status}.", details={"status": run.status})
    run.cancel_requested = True
    if run.status == "queued":
        run.status = "cancelled"
        run.finished_at = db_now()
        run.error = {"code": "cancelled", "message": "Cancelled before execution started."}
        new_event(session, run.id, "run.cancelled", "Run cancelled before it started.", level="warning")
    else:
        new_event(
            session,
            run.id,
            "run.cancel_requested",
            "Cancellation requested; the worker will stop at the next safe point.",
        )
    session.commit()
    session.refresh(run)
    return run
