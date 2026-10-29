"""Run executor: validates, executes nodes, caches outputs, records provenance."""

from __future__ import annotations

import json
import os
import platform
import shutil
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import rdkit
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from .. import __version__
from ..core.config import Settings
from ..core.errors import AppError, NotFoundError, RunCancelledError, ValidationError
from ..core.hashing import sha256_file, stable_json_hash
from ..core.logging import get_logger
from ..core.paths import relative_artifact_path, safe_filename, safe_join
from ..core.redaction import redact_text
from ..core.timeutil import db_now
from ..database.models import Artifact, Compound, Dataset, Run, RunEvent, RunNode, RunResult
from ..jobs.queue import heartbeat as renew_lease
from .cache import CachedOutput, NodeCache, cache_key
from .registry import NodeContext, NodeRegistry, default_registry
from .schema import WorkflowSpec, dataset_table, validate_workflow
from .table import IDENTITY_COLUMNS, Table

logger = get_logger("hcs.run")

TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}


class LeaseLostError(RuntimeError):
    """Raised when this worker can no longer prove that it owns the run lease.

    The worker must stop without writing a terminal state, because another worker
    may already have recovered the run.
    """


class _LeaseHeartbeat:
    """Renew the run lease from a background thread while a node is executing."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        run_id: str,
        worker_id: str,
        lease_seconds: int,
        interval: float | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._run_id = run_id
        self._worker_id = worker_id
        self._interval = interval if interval is not None else max(5.0, lease_seconds / 3.0)
        self._stop = threading.Event()
        self._lost = threading.Event()
        self._thread = threading.Thread(target=self._loop, name=f"lease-{run_id}", daemon=True)

    @property
    def lost(self) -> bool:
        return self._lost.is_set()

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=5.0)

    def _loop(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                renewed = renew_lease(
                    self._session_factory,
                    self._run_id,
                    worker_id=self._worker_id,
                    lease_seconds=max(1, int(self._interval * 3)),
                )
            except Exception as exc:  # transient database contention must not lose the lease
                logger.warning("lease heartbeat failed", extra={"run_id": self._run_id, "error": str(exc)})
                continue
            if not renewed:
                self._lost.set()
                return


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC).isoformat(timespec="seconds")


class EventRecorder:
    def __init__(self, session: Session, run: Run) -> None:
        self.session = session
        self.run = run

    def emit(
        self,
        event_type: str,
        message: str = "",
        *,
        level: str = "info",
        node_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        # The API can append events (for example a cancellation request) while a
        # worker is running, so the next sequence number must be read at write
        # time instead of cached. Retry if another writer won the race.
        for attempt in range(3):
            current = self.session.execute(
                select(func.max(RunEvent.seq)).where(RunEvent.run_id == self.run.id)
            ).scalar()
            event = RunEvent(
                run_id=self.run.id,
                seq=(current or 0) + 1,
                type=event_type,
                level=level,
                message=redact_text(message)[:8000],
                node_id=node_id,
                data=data or {},
            )
            self.session.add(event)
            self.run.heartbeat_at = db_now()
            try:
                self.session.commit()
                return
            except IntegrityError:
                self.session.rollback()
                if attempt == 2:
                    raise


class RunExecutor:
    def __init__(
        self,
        *,
        run_id: str,
        session_factory: sessionmaker[Session],
        settings: Settings,
        registry: NodeRegistry | None = None,
        worker_id: str | None = None,
    ) -> None:
        self.run_id = run_id
        self.session_factory = session_factory
        self.settings = settings
        self.registry = registry or default_registry()
        self.worker_id = worker_id or f"{platform.node()}-{os.getpid()}"
        self.cache = NodeCache(settings.cache_dir)
        self.run_dir = settings.runs_dir / run_id
        self._pending_artifacts: list[dict[str, Any]] = []
        self._artifact_files: dict[str, Path] = {}
        self._last_progress = 0.0
        self._node_started = 0.0
        self._node_timeout = 300
        self._node_row: RunNode | None = None
        self._heartbeat: _LeaseHeartbeat | None = None
        self.warnings: list[str] = []

    # ------------------------------------------------------------------ public
    def execute(self) -> str:
        with self.session_factory() as session:
            run = session.get(Run, self.run_id)
            if run is None:
                raise NotFoundError(f"Run '{self.run_id}' does not exist.")
            if run.status in TERMINAL_STATUSES:
                logger.info("run already terminal", extra={"run_id": run.id, "event": run.status})
                return run.status

            self.events = EventRecorder(session, run)
            self.session = session
            self.run = run
            self._heartbeat = _LeaseHeartbeat(
                self.session_factory,
                run_id=self.run_id,
                worker_id=self.worker_id,
                lease_seconds=self.settings.run_lease_seconds,
            )
            self._heartbeat.start()
            try:
                return self._execute_inner(run)
            finally:
                self._heartbeat.stop()
                session.close()

    # ------------------------------------------------------------------ internals
    def _execute_inner(self, run: Run) -> str:
        started = time.perf_counter()
        self._node_started = started
        run.status = "running"
        run.started_at = run.started_at or db_now()
        run.lease_owner = self.worker_id
        run.heartbeat_at = db_now()
        self.session.commit()
        self.events.emit("run.started", f"Run started on {platform.node()}.", data={"worker": self.worker_id})

        if self.run_dir.exists():
            shutil.rmtree(self.run_dir, ignore_errors=True)
        self.run_dir.mkdir(parents=True, exist_ok=True)

        try:
            workflow = WorkflowSpec.model_validate(run.workflow_snapshot)
            validated = validate_workflow(
                workflow,
                registry=self.registry,
                input_columns=list(IDENTITY_COLUMNS),
            )
            table = self._input_table(run)
            self.events.emit("run.validated", "Workflow and dataset validated.", data={"rows": len(table.rows)})

            node_tables: dict[str, Table] = {}
            for node in validated.order:
                self._check_cancelled(run)
                p_ids = validated.parents_map.get(node.id, [])
                if not p_ids:
                    in_table = table
                    incoming_tables: dict[str, Table] = {}
                elif len(p_ids) == 1:
                    in_table = node_tables[p_ids[0]]
                    incoming_tables = {p_ids[0]: in_table}
                else:
                    in_table = node_tables[p_ids[0]]
                    incoming_tables = {pid: node_tables[pid] for pid in p_ids}

                node_out = self._run_node(
                    run,
                    node.id,
                    node.type,
                    node.config,
                    node.timeout_seconds,
                    in_table,
                    incoming_tables=incoming_tables,
                )
                node_tables[node.id] = node_out
                self._check_cancelled(run)

            final_table = node_tables[validated.order[-1].id]
            self._persist_results(run, final_table)
            self._write_manifest(run, validated.spec, final_table, started)
            self._ensure_lease()
            run.status = "succeeded"
            run.finished_at = db_now()
            run.lease_owner = None
            run.lease_expires_at = None
            self.session.commit()
            self.events.emit(
                "run.succeeded",
                f"Run completed in {time.perf_counter() - started:.1f}s.",
                data={"rows": len(table.rows), "artifacts": len(self._pending_artifacts)},
            )
            return "succeeded"

        except RunCancelledError:
            self._fail_open_node(run, "cancelled", "Cancelled by user request.")
            run.status = "cancelled"
            run.finished_at = db_now()
            run.lease_owner = None
            self.session.commit()
            self.events.emit("run.cancelled", "Run cancelled.", level="warning")
            return "cancelled"

        except LeaseLostError as exc:
            # Another worker may own (or be about to own) this run. Do not write a
            # terminal state from a stale owner.
            logger.warning("lease lost; abandoning run execution", extra={"run_id": run.id, "error": str(exc)})
            self.session.rollback()
            return "lease_lost"

        except AppError as exc:
            self._fail_open_node(run, "failed", exc.message)
            self._finalize_failure(run, exc.code, exc.message, exc.details)
            return "failed"

        except Exception as exc:
            logger.exception("unexpected run failure", extra={"run_id": run.id})
            message = redact_text(f"{type(exc).__name__}: {exc}")
            self._fail_open_node(run, "failed", message)
            self._finalize_failure(run, "internal_error", message, {})
            return "failed"

    def _input_table(self, run: Run) -> Table:
        if not run.dataset_id:
            raise ValidationError("The run has no dataset.")
        dataset = self.session.get(Dataset, run.dataset_id)
        if dataset is None:
            raise NotFoundError("Dataset for this run no longer exists.")
        compounds = (
            self.session.execute(
                select(Compound)
                .where(Compound.dataset_id == dataset.id)
                .order_by(Compound.source_row_index, Compound.id)
            )
            .scalars()
            .all()
        )
        if not compounds:
            raise ValidationError("Dataset contains no usable compounds; import could not be completed.")
        table = dataset_table(
            [
                {
                    "id": compound.id,
                    "isomeric_smiles": compound.isomeric_smiles,
                    "name": compound.name,
                    "source_id": compound.source_id,
                }
                for compound in compounds
            ]
        )
        return table

    def _node_state(self, node_id: str) -> RunNode:
        node = self.session.execute(
            select(RunNode).where(RunNode.run_id == self.run_id, RunNode.node_id == node_id)
        ).scalar_one()
        return node

    def _run_node(
        self,
        run: Run,
        node_id: str,
        node_type: str,
        config: dict[str, Any],
        timeout_seconds: int,
        input_table: Table,
        incoming_tables: dict[str, Table] | None = None,
    ) -> Table:
        definition = self.registry.get(node_type)
        parsed_config = definition.parse_config(config)
        node_row = self._node_state(node_id)
        self._node_row = node_row
        self._node_started = time.perf_counter()
        self._node_timeout = timeout_seconds
        self._pending_artifacts = []
        self._artifact_files = {}
        node_row.status = "running"
        node_row.started_at = db_now()
        node_row.progress = 0.0
        self.session.commit()
        self.events.emit("node.started", f"Starting {definition.title}.", node_id=node_id)

        input_hash = input_table.content_hash()
        key = cache_key(
            node_type=node_type,
            node_version=definition.version,
            config=parsed_config.model_dump(mode="json"),
            input_hash=input_hash,
            engine_versions=self._engine_versions(),
            schema_version=run.workflow_snapshot.get("schema_version", 1),
            implementation_hash=definition.implementation_hash,
        )
        node_row.cache_key = key
        self.session.commit()

        cached = self.cache.get(key)
        if cached is not None and self._restore_from_cache(node_row, node_id, cached):
            self._ensure_lease()
            node_row.status = "succeeded"
            node_row.cached = True
            node_row.progress = 1.0
            node_row.finished_at = db_now()
            node_row.summary = cached.summary
            self.session.commit()
            self.events.emit(
                "node.succeeded",
                f"Reused cached result for {definition.title}.",
                node_id=node_id,
                data={"cached": True, "rows": len(cached.table.rows)},
            )
            return cached.table

        work_dir = self.run_dir / "nodes" / node_id
        work_dir.mkdir(parents=True, exist_ok=True)
        context = NodeContext(
            run_id=self.run_id,
            node_id=node_id,
            work_dir=work_dir,
            emit=self._node_emit,
            report_progress=self._node_progress,
            check_cancel=lambda: self._check_cancelled(run),
            write_artifact=self._write_artifact,
            engine_versions=self._engine_versions(),
            incoming_tables=incoming_tables or {},
        )
        try:
            output = definition.handler(input_table.copy(), parsed_config, context)
        except RunCancelledError:
            node_row.status = "cancelled"
            node_row.finished_at = db_now()
            self.session.commit()
            self.events.emit("node.cancelled", "Node cancelled.", level="warning", node_id=node_id)
            raise
        except AppError:
            node_row.status = "failed"
            node_row.finished_at = db_now()
            self.session.commit()
            self.events.emit("node.failed", f"{definition.title} failed.", level="error", node_id=node_id)
            raise
        except Exception as exc:
            node_row.status = "failed"
            node_row.finished_at = db_now()
            node_row.error = {"code": "node_error", "message": redact_text(str(exc))}
            self.session.commit()
            self.events.emit(
                "node.failed",
                f"{definition.title} failed: {type(exc).__name__}",
                level="error",
                node_id=node_id,
            )
            raise

        duration_ms = int((time.perf_counter() - self._node_started) * 1000)
        self._ensure_lease()
        artifacts = self._persist_artifacts(node_id)
        summary = output.summary()
        node_row.status = "succeeded"
        node_row.progress = 1.0
        node_row.finished_at = db_now()
        node_row.summary = {
            **summary,
            "duration_ms": duration_ms,
            "artifacts": [a["rel_path"] for a in artifacts],
        }
        self.session.commit()

        stored_cache = self.cache.put(
            key,
            CachedOutput(table=output, artifacts=self._pending_artifacts, summary=summary),
            self._artifact_files,
        )
        if not stored_cache:
            logger.warning("cache entry was not written", extra={"run_id": self.run_id, "node_id": node_id, "key": key})
        self.events.emit(
            "node.succeeded",
            f"{definition.title} finished in {duration_ms / 1000:.1f}s ({len(output.rows)} rows).",
            node_id=node_id,
            data={"cached": False, "rows": len(output.rows), "duration_ms": duration_ms},
        )
        return output

    def _restore_from_cache(self, node_row: RunNode, node_id: str, cached: CachedOutput) -> bool:
        """Copy cached artifacts into the run directory.

        Returns False (cache miss) instead of accepting a partially restored entry.
        """
        work_dir = self.run_dir / "nodes" / node_id
        work_dir.mkdir(parents=True, exist_ok=True)
        prefixed: list[tuple[dict[str, Any], Path, Path]] = []
        for artifact in cached.artifacts:
            filename = artifact.get("filename")
            cache_file = artifact.get("cache_file")
            if not filename or not cache_file:
                return False
            source = self.cache.artifact_path(node_row.cache_key or "", cache_file)
            if not source.exists():
                return False
            prefixed.append((artifact, source, work_dir / filename))
        for _artifact, source, destination in prefixed:
            shutil.copy2(source, destination)
        for artifact, _source, _destination in prefixed:
            self._record_artifact(
                node_id=node_id,
                filename=artifact["filename"],
                media_type=artifact.get("media_type", "application/octet-stream"),
                kind=artifact.get("kind", "artifact"),
            )
        return True

    def _engine_versions(self) -> dict[str, str]:
        versions = self.registry.engine_versions()
        versions["rdkit"] = rdkit.__version__
        versions["python"] = platform.python_version()
        return versions

    # ------------------------------------------------------------------ context callbacks
    def _node_emit(self, level: str, message: str, data: dict[str, Any] | None, event_type: str) -> None:
        self.events.emit(
            event_type,
            message,
            level=level,
            node_id=self._node_row.node_id if self._node_row else None,
            data=data or {},
        )

    def _node_progress(self, fraction: float | None) -> None:
        if fraction is None or self._node_row is None:
            return
        now = time.monotonic()
        if now - self._last_progress < 0.4 and fraction < 1.0:
            return
        self._last_progress = now
        self._node_row.progress = max(0.0, min(1.0, fraction))
        self.session.commit()

    def _write_artifact(self, filename: str, content: str | bytes, media_type: str) -> dict[str, Any]:
        name = safe_filename(filename)
        if self._node_row is None:
            raise ValidationError("Artifacts can only be written from a running node.")
        work_dir = self.run_dir / "nodes" / self._node_row.node_id
        destination = safe_join(work_dir, name)
        payload = content.encode("utf-8") if isinstance(content, str) else content
        destination.write_bytes(payload)
        rel_path = relative_artifact_path(self.run_dir, destination)
        record = {
            "filename": name,
            "rel_path": rel_path,
            "media_type": media_type,
            "kind": "node_artifact",
            "size_bytes": len(payload),
            "sha256": sha256_file(destination),
            "node_id": self._node_row.node_id,
        }
        self._pending_artifacts.append(record)
        self._artifact_files[name] = destination
        return record

    def _persist_artifacts(self, node_id: str) -> list[dict[str, Any]]:
        created = []
        for record in self._pending_artifacts:
            artifact = Artifact(
                run_id=self.run_id,
                node_id=node_id,
                kind=record["kind"],
                rel_path=record["rel_path"],
                media_type=record["media_type"],
                size_bytes=record["size_bytes"],
                sha256=record["sha256"],
            )
            self.session.add(artifact)
            created.append(record)
        self.session.commit()
        return created

    def _record_artifact(self, *, node_id: str | None, filename: str, media_type: str, kind: str) -> None:
        path = self.run_dir / "nodes" / node_id / filename if node_id else self.run_dir / filename
        if not path.exists():
            return
        record = {
            "filename": filename,
            "rel_path": relative_artifact_path(self.run_dir, path),
            "media_type": media_type,
            "kind": kind,
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "node_id": node_id,
        }
        self.session.add(
            Artifact(
                run_id=self.run_id,
                node_id=node_id,
                kind=kind,
                rel_path=record["rel_path"],
                media_type=media_type,
                size_bytes=record["size_bytes"],
                sha256=record["sha256"],
            )
        )
        self.session.commit()

    # ------------------------------------------------------------------ state helpers
    def _ensure_lease(self) -> None:
        if self._heartbeat is not None and self._heartbeat.lost:
            raise LeaseLostError("The worker lease was lost or revoked.")

    def _check_cancelled(self, run: Run) -> None:
        self._ensure_lease()
        flag = self.session.execute(text("SELECT cancel_requested FROM runs WHERE id = :id"), {"id": run.id}).scalar()
        if flag:
            raise RunCancelledError("Run cancellation was requested.")
        if time.perf_counter() - self._node_started > self._node_timeout:
            raise ValidationError(
                f"Node exceeded its timeout of {self._node_timeout}s.",
                details={"node": self._node_row.node_id if self._node_row else None},
            )

    def _fail_open_node(self, run: Run, status: str, message: str) -> None:
        try:
            node = (
                self.session.execute(select(RunNode).where(RunNode.run_id == run.id, RunNode.status == "running"))
                .scalars()
                .first()
            )
            if node is not None:
                node.status = status
                node.finished_at = db_now()
                node.error = {"code": status, "message": redact_text(message)}
                self.session.commit()
        except Exception:
            self.session.rollback()

    def _finalize_failure(self, run: Run, code: str, message: str, details: dict[str, Any]) -> None:
        run.status = "failed"
        run.error = {"code": code, "message": redact_text(message), "details": details}
        run.finished_at = db_now()
        run.lease_owner = None
        self.session.commit()
        self.events.emit(
            "run.failed",
            redact_text(message)[:2000],
            level="error",
            data={"code": code},
        )

    def _persist_results(self, run: Run, table: Table) -> None:
        self.session.execute(text("DELETE FROM run_results WHERE run_id = :id"), {"id": run.id})
        metric_columns = [column for column in table.columns if column.type == "number"]
        for row in table.rows:
            reasons = [part.strip() for part in str(row.get("filter_reasons") or "").split(";") if part.strip()]
            metrics = {column.name: row.get(column.name) for column in metric_columns}
            self.session.add(
                RunResult(
                    run_id=run.id,
                    compound_id=str(row.get("compound_id")),
                    rank=int(row["rank"]) if row.get("rank") is not None else None,
                    composite_score=float(row["composite_score"]) if row.get("composite_score") is not None else None,
                    pareto_front=int(row["pareto_rank"]) if row.get("pareto_rank") is not None else None,
                    rejected=not bool(row.get("filter_pass", True)),
                    reasons=reasons,
                    metrics=metrics,
                )
            )
        self.session.commit()

        result_columns = [column.as_dict() for column in table.columns]
        payload = {
            "run_id": run.id,
            "columns": result_columns,
            "rows": table.rows,
            "caveat": (
                "Scores and descriptors are prioritisation signals computed by the methods listed per column. "
                "They are not experimental measurements, proof of binding, safety or efficacy."
            ),
        }
        json_path = self.run_dir / "results.json"
        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        self._record_artifact(node_id=None, filename="results.json", media_type="application/json", kind="result")

        csv_path = self.run_dir / "results.csv"
        import csv as csv_module

        names = [column.name for column in table.columns]
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv_module.DictWriter(handle, fieldnames=names, extrasaction="ignore")
            writer.writeheader()
            for row in table.rows:
                writer.writerow({key: row.get(key) for key in names})
        self._record_artifact(node_id=None, filename="results.csv", media_type="text/csv", kind="result")

    def _write_manifest(self, run: Run, spec: WorkflowSpec, table: Table, started: float) -> None:
        artifacts = self.session.execute(select(Artifact).where(Artifact.run_id == run.id)).scalars().all()
        nodes = self.session.execute(select(RunNode).where(RunNode.run_id == run.id)).scalars().all()
        dataset = self.session.get(Dataset, run.dataset_id) if run.dataset_id else None
        manifest = {
            "schema": "hcs.manifest/1",
            "run_id": run.id,
            "product": {"name": "HCS Discovery Studio", "version": __version__},
            "workflow": {
                "name": spec.name,
                "id": spec.id,
                "content_hash": run.workflow_hash,
                "snapshot": spec.model_dump(mode="json"),
            },
            "dataset": {
                "id": dataset.id if dataset else None,
                "sha256": dataset.sha256 if dataset else None,
                "name": dataset.name if dataset else None,
                "source_format": dataset.source_format if dataset else None,
            },
            "inputs_hash": stable_json_hash(
                {
                    "dataset": dataset.sha256 if dataset else None,
                    "workflow": run.workflow_hash,
                    "rows": len(table.rows),
                }
            ),
            "environment": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "rdkit": rdkit.__version__,
                "engines": self._engine_versions(),
            },
            "hardware": {
                "cpu_count": os.cpu_count(),
                "cpu": platform.processor() or platform.machine(),
                "backend": "cpu",
            },
            "seed": run.seed,
            "columns": [column.as_dict() for column in table.columns],
            "warnings": self.warnings,
            "nodes": [
                {
                    "node_id": node.node_id,
                    "type": node.node_type,
                    "status": node.status,
                    "cached": node.cached,
                    "cache_key": node.cache_key,
                    "duration_ms": node.summary.get("duration_ms") if node.summary else None,
                }
                for node in nodes
            ],
            "artifacts": [
                {
                    "rel_path": artifact.rel_path,
                    "sha256": artifact.sha256,
                    "media_type": artifact.media_type,
                }
                for artifact in artifacts
            ],
            "duration_seconds": round(time.perf_counter() - started, 3),
            "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "limitations": [
                "Descriptors are estimates computed by RDKit, not measurements.",
                "Ranking uses the configured weights; it is not a validated efficacy predictor.",
                "Pareto ranks are limited to the configured number of fronts.",
            ],
        }
        # Declare the manifest's own location before persisting so the file and the
        # database row stay byte-for-byte consistent. Reassign (instead of mutating)
        # so SQLAlchemy tracks the JSON change.
        manifest["artifact_rel_path"] = "manifest.json"
        run.manifest = manifest
        path = self.run_dir / "manifest.json"
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        self._record_artifact(node_id=None, filename="manifest.json", media_type="application/json", kind="manifest")
        self.session.commit()


def mark_queued(session: Session, run_id: str) -> None:
    session.execute(update(Run).where(Run.id == run_id, Run.status == "queued").values(heartbeat_at=db_now()))
    session.commit()
