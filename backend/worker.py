from __future__ import annotations

import logging
import multiprocessing
import time
from uuid import uuid4

from .config import get_settings
from .db import SessionLocal, engine
from .migrations import ensure_schema
from .models import Account, Worker
from .services.jobs import claim_next_run, finish_interrupted, heartbeat, recover_expired_runs, renew_lease, scheduler_tick
from .services.billing import expire_pending_orders
from .services.runner import execute_run
from .services.account_inspection import claim_inspection, execute_inspection
from .services.scheduling import utc_now
from .services.platform_settings import worker_settings

logger = logging.getLogger(__name__)


def supervise_inspection(account_id: str, worker_id: str) -> None:
    process = multiprocessing.get_context("spawn").Process(target=execute_inspection, args=(account_id,))
    deadline = time.monotonic() + 90
    try:
        process.start()
        while process.is_alive() and time.monotonic() < deadline:
            process.join(timeout=2)
            with SessionLocal() as db:
                heartbeat(db, worker_id)
                db.commit()
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
            account = db.get(Account, account_id)
            if account and account.status != "DELETED" and account.inspection_status == "CHECKING":
                account.status = "UNVERIFIED"
                account.inspection_status = "FAILED"
                account.inspection_message = "检测进程中断或超时，请重试"
                account.checked_at = utc_now()
                db.commit()


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
        if process.exitcode not in (None, 0) and reason.startswith("Worker process stopped"):
            reason = f"Worker process exited with code {process.exitcode}; delivery may be partial"
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
    # Tests may replace SessionLocal with an isolated SQLite sessionmaker.
    # Production and normal local runs use the module-level engine.
    bound_engine = getattr(SessionLocal, "kw", {}).get("bind")
    if get_settings().auto_migrate and (bound_engine is None or bound_engine is engine):
        ensure_schema()
    worker_id = f"worker-{uuid4().hex[:12]}"
    try:
        while True:
            try:
                with SessionLocal() as db:
                    settings = worker_settings(db)
                    heartbeat(db, worker_id)
                    if not settings.enabled:
                        db.get(Worker, worker_id).status = "PAUSED"
                    recover_expired_runs(db)
                    expire_pending_orders(db)
                    db.commit()
                if not settings.enabled:
                    time.sleep(2)
                    continue
                scheduler_tick(SessionLocal)
                with SessionLocal() as db:
                    heartbeat(db, worker_id)
                    recover_expired_runs(db)
                    expire_pending_orders(db)
                    run_id = claim_next_run(db, worker_id)
                    db.commit()
                if run_id:
                    supervise_run(run_id, worker_id, settings.timeout)
                else:
                    with SessionLocal() as db:
                        account_id = claim_inspection(db)
                        db.commit()
                    if account_id:
                        supervise_inspection(account_id, worker_id)
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
