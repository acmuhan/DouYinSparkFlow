from __future__ import annotations

import logging
import multiprocessing
import time
from uuid import uuid4

from .config import get_settings
from .db import SessionLocal
from .models import Worker
from .services.jobs import claim_next_run, finish_interrupted, heartbeat, recover_expired_runs, renew_lease, scheduler_tick
from .services.billing import expire_pending_orders
from .services.runner import execute_run

logger = logging.getLogger(__name__)


def supervise_run(run_id: str, worker_id: str, timeout: int) -> None:
    process = multiprocessing.get_context("spawn").Process(target=execute_run, args=(run_id, worker_id))
    deadline = time.monotonic() + timeout
    reason = "Worker process stopped before completion; delivery may be partial"
    try:
        process.start()
        while process.is_alive():
            process.join(timeout=1)
            if not process.is_alive():
                break
            if time.monotonic() >= deadline:
                reason = "Execution deadline exceeded; delivery may be partial. Automatic replay disabled."
                break
            with SessionLocal() as db:
                heartbeat(db, worker_id)
                held = renew_lease(db, run_id, worker_id)
                db.commit()
            if not held:
                reason = "Execution stopped after cancellation or lease loss; delivery may be partial"
                break
    finally:
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
            process.join(timeout=5)
            if process.is_alive():
                process.kill()
                process.join()
            process.close()
        with SessionLocal() as db:
            finish_interrupted(db, run_id, worker_id, reason)
            db.commit()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_settings()
    if not settings.worker_enabled:
        logger.info("Worker disabled by configuration")
        return
    worker_id = f"worker-{uuid4().hex[:12]}"
    try:
        while True:
            try:
                scheduler_tick(SessionLocal)
                with SessionLocal() as db:
                    heartbeat(db, worker_id)
                    recover_expired_runs(db)
                    expire_pending_orders(db)
                    run_id = claim_next_run(db, worker_id)
                    db.commit()
                if run_id:
                    supervise_run(run_id, worker_id, settings.worker_timeout)
                else:
                    time.sleep(2)
            except Exception as exc:
                logger.error("worker.iteration_failed worker_id=%s error_type=%s", worker_id, type(exc).__name__)
                time.sleep(5)
    except KeyboardInterrupt:
        logger.info("Worker shutting down")
    finally:
        with SessionLocal() as db:
            worker = db.get(Worker, worker_id)
            if worker:
                worker.status = "OFFLINE"
                db.commit()


if __name__ == "__main__":
    main()
