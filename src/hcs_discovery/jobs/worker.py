"""Worker process/thread loop."""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from ..core.config import Settings
from ..core.logging import get_logger
from ..database.base import get_session_factory
from ..database.models import Run
from ..workflow.executor import RunExecutor
from ..workflow.registry import NodeRegistry
from .queue import claim_next_run, recover_stale_runs

logger = get_logger("hcs.worker")


class Worker:
    def __init__(
        self,
        *,
        settings: Settings,
        factory: sessionmaker[Session] | None = None,
        registry: NodeRegistry | None = None,
        worker_id: str | None = None,
    ) -> None:
        self.settings = settings
        self.factory = factory or get_session_factory(settings)
        self.registry = registry
        self.worker_id = worker_id or f"worker-{threading.get_ident()}"
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run_once(self) -> Run | None:
        recovered = recover_stale_runs(self.factory, self.settings)
        for item in recovered:
            logger.warning("recovered run", extra={"run_id": item["run_id"], "event": item["outcome"]})
        run = claim_next_run(
            self.factory,
            worker_id=self.worker_id,
            lease_seconds=self.settings.run_lease_seconds,
        )
        if run is None:
            return None
        logger.info("claimed run", extra={"run_id": run.id})
        executor = RunExecutor(
            run_id=run.id,
            session_factory=self.factory,
            settings=self.settings,
            registry=self.registry,
            worker_id=self.worker_id,
        )
        executor.execute()
        return run

    def run_forever(self, *, stale_check_seconds: float = 15.0) -> None:
        last_recovery = 0.0
        while not self._stop.is_set():
            run = self.run_once()
            if run is None:
                now = time.monotonic()
                if now - last_recovery > stale_check_seconds:
                    recover_stale_runs(self.factory, self.settings)
                    last_recovery = now
                self._stop.wait(self.settings.worker_poll_seconds)


def run_worker_loop(
    settings: Settings,
    *,
    concurrency: int = 1,
    stop_event: threading.Event | None = None,
    registry: NodeRegistry | None = None,
) -> None:
    stop_event = stop_event or threading.Event()
    workers = [
        Worker(settings=settings, registry=registry, worker_id=f"worker-{index}")
        for index in range(max(1, concurrency))
    ]
    if len(workers) == 1:
        workers[0].run_forever()
        return

    def loop(worker: Worker) -> None:
        while not stop_event.is_set():
            if worker.run_once() is None:
                stop_event.wait(settings.worker_poll_seconds)

    with ThreadPoolExecutor(max_workers=len(workers)) as pool:
        futures = [pool.submit(loop, worker) for worker in workers]
        try:
            for future in futures:
                future.result()
        except KeyboardInterrupt:  # pragma: no cover - interactive path
            stop_event.set()


def ensure_data_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
