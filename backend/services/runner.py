from __future__ import annotations

import json
import logging

from playwright.sync_api import sync_playwright
from sqlalchemy import select, update

from core.msg_builder import build_message
from core.runner import DouyinRunner

from ..crypto import decrypt_secret
from ..db import SessionLocal
from ..models import Account, Run
from ..schemas import RunSnapshot
from .audit import record_audit
from .errors import RunCancelled
from .jobs import execution_allowed
from .scheduling import utc_now

logger = logging.getLogger(__name__)


def browser_execution(*, cookies, snapshot, checkpoint, on_sent):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            return DouyinRunner().run(
                browser, cookies=cookies, targets=snapshot.targets,
                message_factory=lambda: build_message(snapshot.message, snapshot.hitokoto_types),
                checkpoint=checkpoint, on_sent=on_sent,
            )
        finally:
            browser.close()


def execute_run(run_id: str, worker_id: str, *, session_factory=SessionLocal, executor=browser_execution) -> None:
    def checkpoint() -> None:
        with session_factory() as db:
            current = db.get(Run, run_id)
            if (
                not current or current.status != "RUNNING" or current.worker_id != worker_id
                or current.cancel_requested or not current.lease_until or current.lease_until <= utc_now()
                or not execution_allowed(db, current, snapshot.account_id)
            ):
                raise RunCancelled()

    def on_sent(count: int) -> None:
        with session_factory() as db:
            db.execute(update(Run).where(
                Run.id == run_id, Run.worker_id == worker_id, Run.status == "RUNNING",
            ).values(sent_count=count))
            db.commit()

    with session_factory() as db:
        run = db.scalar(select(Run).where(Run.id == run_id).with_for_update())
        if (
            not run or run.status != "CLAIMED" or run.worker_id != worker_id
            or not run.lease_until or run.lease_until <= utc_now()
        ):
            return
        run.status = "RUNNING"
        run.started_at = utc_now()
        db.commit()

    try:
        snapshot = RunSnapshot.model_validate(run.snapshot)
        checkpoint()
        with session_factory() as db:
            account = db.get(Account, snapshot.account_id)
            cookies = json.loads(decrypt_secret(account.cookies_encrypted))
        result = executor(cookies=cookies, snapshot=snapshot, checkpoint=checkpoint, on_sent=on_sent)
        outcome = "SUCCEEDED" if result.missing_count == 0 else "FAILED"
        message = f"{result.sent_count} browser submissions; {result.missing_count} targets not found"
    except RunCancelled:
        outcome, message = "CANCELLED", "Execution stopped; delivery may be partial"
    except Exception as exc:
        # Browser errors may embed cookies, draft text or target identifiers.
        logger.error("run.failed run_id=%s error_type=%s", run_id, type(exc).__name__)
        outcome, message = "FAILED", "Execution failed; delivery may be partial. Inspect worker status before retrying."
    with session_factory() as db:
        run = db.scalar(select(Run).where(Run.id == run_id).with_for_update())
        if not run or run.status != "RUNNING" or run.worker_id != worker_id or not run.lease_until or run.lease_until <= utc_now():
            return
        run.status = "CANCELLED" if run.cancel_requested else outcome
        run.result = message
        run.finished_at = utc_now()
        run.lease_until = None
        record_audit(db, actor_id=run.user_id, action=f"run.{run.status.lower()}", target_id=run.id, detail={"sent_count": run.sent_count})
        db.commit()
