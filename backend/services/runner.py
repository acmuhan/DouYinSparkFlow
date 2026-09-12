from __future__ import annotations

import json
import traceback
from datetime import datetime, timedelta
from uuid import uuid4

from playwright.sync_api import sync_playwright
from sqlalchemy import select

from ..crypto import decrypt_secret
from ..db import SessionLocal
from ..models import Account, Run, Task, Usage
from .audit import record_audit


def execute_run(run_id: str) -> None:
    db = SessionLocal()
    run = db.scalar(select(Run).where(Run.id == run_id))
    if not run or run.status not in {"QUEUED", "RETRY"}:
        db.close()
        return
    task = db.scalar(select(Task).where(Task.id == run.task_id, Task.user_id == run.user_id))
    account = db.scalar(select(Account).where(Account.id == task.account_id, Account.user_id == run.user_id)) if task else None
    if not task or not account:
        run.status, run.result, run.finished_at = "FAILED", "task or account not found", datetime.utcnow()
        db.commit()
        db.close()
        return
    run.status = "RUNNING"
    run.worker_id = f"local-{uuid4().hex[:12]}"
    run.started_at = datetime.utcnow()
    run.lease_until = datetime.utcnow() + timedelta(minutes=10)
    db.commit()
    try:
        cookies = json.loads(decrypt_secret(account.cookies_encrypted))
        from core.tasks import do_user_task

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                do_user_task(browser, account.name, cookies, task.targets)
            finally:
                browser.close()
        period = datetime.utcnow().strftime("%Y-%m")
        usage = db.scalar(select(Usage).where(Usage.user_id == run.user_id, Usage.period == period))
        if not usage:
            usage = Usage(id=str(uuid4()), user_id=run.user_id, period=period, used=0, adjustment=0)
            db.add(usage)
        usage.used += 1
        run.status, run.sent_count, run.result = "SUCCEEDED", len(task.targets), "Task completed"
        record_audit(db, actor_id=run.user_id, action="run.completed", target_id=run.id, detail={"sent_count": len(task.targets)})
    except Exception as exc:
        run.status, run.result = "FAILED", f"{exc}\n{traceback.format_exc(limit=2)}"
        record_audit(db, actor_id=run.user_id, action="run.failed", target_id=run.id, detail={"error": str(exc)})
    finally:
        run.finished_at = datetime.utcnow()
        run.lease_until = None
        db.commit()
        db.close()
