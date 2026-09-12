from __future__ import annotations

import time
from datetime import datetime, timedelta

from sqlalchemy import select

from .db import SessionLocal
from .models import Run, Worker
from .services.runner import execute_run


def main():
    worker_id = f"worker-{__import__('uuid').uuid4().hex[:12]}"
    while True:
        db = SessionLocal()
        try:
            worker = db.get(Worker, worker_id)
            if not worker:
                worker = Worker(id=worker_id, heartbeat_at=datetime.utcnow(), status="ONLINE")
                db.add(worker)
            else:
                worker.heartbeat_at = datetime.utcnow()
                worker.status = "ONLINE"
            db.commit()
            run = db.scalar(
                select(Run)
                .where(Run.status == "QUEUED", Run.cancel_requested.is_(False))
                .order_by(Run.created_at)
                .with_for_update(skip_locked=True)
            )
            if run:
                run.status = "CLAIMED"
                run.worker_id = worker_id
                run.lease_until = datetime.utcnow() + timedelta(minutes=10)
                db.commit()
                run_id = run.id
            else:
                run_id = None
        finally:
            db.close()
        if run_id:
            execute_run(run_id)
        else:
            time.sleep(2)


if __name__ == "__main__":
    main()
