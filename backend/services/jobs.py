from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfoNotFoundError

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models import Account, Run, Subscription, Task, Usage, User, Worker
from ..schemas import RunSnapshot, TaskIn
from .audit import record_audit
from .billing import ensure_can_create
from .errors import QuotaError, TaskError
from .scheduling import next_daily_run, utc_now
from .plugin_access import ensure_plugin_access, ensure_permission
from ..permissions import effective_permissions
from .run_events import add_run_event
from ..plugins import PLUGINS, allowed_plugins

ACTIVE_RUN_STATES = ("QUEUED", "CLAIMED", "RUNNING")
LEASE_SECONDS = 60


def owned_task(db: Session, user_id: str, task_id: str) -> Task:
    db.scalar(select(User).where(User.id == user_id).with_for_update())
    task = db.scalar(
        select(Task).where(Task.id == task_id, Task.user_id == user_id, Task.archived.is_(False))
        .with_for_update().execution_options(populate_existing=True)
    )
    if not task:
        raise TaskError("task not found")
    return task


def enqueue_run(db: Session, *, task: Task, trigger_type: str, now: datetime | None = None) -> Run:
    """Caller owns the user/task locks and commits the run and quota together."""
    now = now or utc_now()
    ensure_plugin_access(db, task.user_id, task.plugin_id)
    ensure_permission(db, task.user_id, "tasks.schedule" if trigger_type == "SCHEDULED" else "tasks.manual")
    if PLUGINS[task.plugin_id].requires_account:
        account = db.scalar(select(Account).where(Account.id == task.account_id, Account.user_id == task.user_id).with_for_update())
        if not account or account.status != "READY":
            raise TaskError("account is not available")
    existing = db.scalar(
        select(Run).where(Run.task_id == task.id, Run.status.in_(ACTIVE_RUN_STATES))
        .with_for_update().execution_options(populate_existing=True)
    )
    if existing:
        return existing
    ensure_can_create(db, user_id=task.user_id, resource="run", now=now)
    period = now.strftime("%Y-%m")
    usage = db.scalar(select(Usage).where(Usage.user_id == task.user_id, Usage.period == period).with_for_update())
    if not usage:
        usage = Usage(id=str(uuid4()), user_id=task.user_id, period=period, used=0, adjustment=0)
        db.add(usage)
    usage.used += 1
    snapshot = RunSnapshot(
        **TaskIn.model_validate(task, from_attributes=True).model_dump(),
        usage_period=period,
    )
    run = Run(
        id=str(uuid4()), user_id=task.user_id, task_id=task.id,
        status="QUEUED", trigger_type=trigger_type, snapshot=snapshot.model_dump(),
        created_at=now,
    )
    db.add(run)
    record_audit(db, actor_id=task.user_id, action="run.queued", target_id=run.id, detail={"task_id": task.id, "trigger": trigger_type})
    db.flush()
    add_run_event(db, run, "queued")
    return run


def schedule_due_task(db: Session, *, user_id: str, task_id: str, now: datetime | None = None) -> Run | None:
    now = now or utc_now()
    task = owned_task(db, user_id, task_id)
    if not task.enabled or (task.next_run_at and task.next_run_at > now):
        return None
    try:
        next_run_at = next_daily_run(task.schedule_time, task.timezone, now)
    except (ValueError, ZoneInfoNotFoundError):
        task.enabled = False
        task.next_run_at = None
        record_audit(db, actor_id=None, action="schedule.invalid", target_id=task.id)
        return None
    first_schedule = task.next_run_at is None
    task.next_run_at = next_run_at
    if first_schedule:
        return None
    try:
        return enqueue_run(db, task=task, trigger_type="SCHEDULED", now=now)
    except (QuotaError, TaskError) as exc:
        record_audit(db, actor_id=None, action="schedule.skipped", target_id=task.id, detail={"reason": str(exc)})
        return None


def scheduler_tick(session_factory, *, now: datetime | None = None, batch_size: int = 100) -> int:
    now = now or utc_now()
    # Candidate discovery is a separate transaction, so MySQL REPEATABLE READ
    # cannot retain a pre-lock snapshot while checking another worker's queue.
    with session_factory() as db:
        candidates = list(db.execute(
            select(Task.user_id, Task.id).where(
                Task.enabled.is_(True), Task.archived.is_(False),
                (Task.next_run_at.is_(None)) | (Task.next_run_at <= now),
            ).order_by(Task.next_run_at, Task.id).limit(batch_size)
        ))
    admitted = 0
    for user_id, task_id in candidates:
        with session_factory() as db:
            try:
                run = schedule_due_task(db, user_id=user_id, task_id=task_id, now=now)
                db.commit()
                admitted += int(run is not None)
            except TaskError:
                db.rollback()
    return admitted


def claim_next_run(db: Session, worker_id: str, *, now: datetime | None = None) -> str | None:
    now = now or utc_now()
    run = db.scalar(
        select(Run).where(Run.status == "QUEUED", Run.cancel_requested.is_(False))
        .order_by(Run.created_at, Run.id).limit(1).with_for_update(skip_locked=True)
    )
    if not run:
        return None
    run.status = "CLAIMED"
    run.worker_id = worker_id
    run.lease_until = now + timedelta(seconds=LEASE_SECONDS)
    db.flush()
    return run.id


def heartbeat(db: Session, worker_id: str, *, now: datetime | None = None) -> None:
    now = now or utc_now()
    worker = db.get(Worker, worker_id)
    if worker is None:
        db.add(Worker(id=worker_id, heartbeat_at=now, status="ONLINE"))
    else:
        worker.heartbeat_at = now
        worker.status = "ONLINE"


def renew_lease(db: Session, run_id: str, worker_id: str, *, now: datetime | None = None) -> bool:
    now = now or utc_now()
    result = db.execute(update(Run).where(
        Run.id == run_id, Run.worker_id == worker_id, Run.status.in_(("CLAIMED", "RUNNING")),
        Run.cancel_requested.is_(False), Run.lease_until > now,
    ).values(lease_until=now + timedelta(seconds=LEASE_SECONDS)))
    return result.rowcount == 1


def finish_interrupted(db: Session, run_id: str, worker_id: str, reason: str) -> None:
    run = db.scalar(select(Run).where(Run.id == run_id, Run.worker_id == worker_id).with_for_update())
    if run and run.status in ("CLAIMED", "RUNNING"):
        run.status = "CANCELLED" if run.cancel_requested else "FAILED"
        run.result = reason
        run.finished_at = utc_now()
        run.lease_until = None
        record_audit(db, actor_id=None, action="run.interrupted", target_id=run.id, detail={"reason": reason})
        add_run_event(db, run, "interrupted")


def recover_expired_runs(db: Session, *, now: datetime | None = None) -> int:
    now = now or utc_now()
    expired = list(db.scalars(select(Run).where(
        Run.status.in_(("CLAIMED", "RUNNING")), Run.lease_until <= now,
    ).limit(100).with_for_update(skip_locked=True)))
    for run in expired:
        run.status = "CANCELLED" if run.cancel_requested else "FAILED"
        run.finished_at = now
        run.lease_until = None
        run.result = "Worker lease expired; delivery may be partial. Automatic replay disabled."
        record_audit(db, actor_id=None, action="run.lease_expired", target_id=run.id)
        add_run_event(db, run, "lease_expired")
    return len(expired)


def cancel_run(db: Session, *, run_id: str, user_id: str) -> Run:
    db.scalar(select(User).where(User.id == user_id).with_for_update())
    run = db.scalar(select(Run).where(Run.id == run_id, Run.user_id == user_id).with_for_update())
    if not run:
        raise TaskError("run not found")
    if run.status not in ACTIVE_RUN_STATES or run.cancel_requested:
        return run
    run.cancel_requested = True
    if run.status == "QUEUED":
        run.status = "CANCELLED"
        run.finished_at = utc_now()
        run.result = "Cancelled before execution"
        period = run.snapshot.get("usage_period")
        if period:
            usage = db.scalar(select(Usage).where(Usage.user_id == user_id, Usage.period == period).with_for_update())
            if usage:
                usage.used = max(0, usage.used - 1)
    record_audit(db, actor_id=user_id, action="run.cancel_requested", target_id=run.id)
    add_run_event(db, run, "cancelled" if run.status == "CANCELLED" else "cancel_requested")
    return run


def execution_allowed(db: Session, run: Run, account_id: str | None) -> bool:
    user = db.get(User, run.user_id)
    task = db.get(Task, run.task_id)
    account = db.get(Account, account_id) if account_id else None
    plugin = PLUGINS.get(run.snapshot.get("plugin_id", "douyin_streak"))
    account_allowed = bool(plugin and (
        (not plugin.requires_account and account_id is None)
        or (plugin.requires_account and account and account.status == "READY" and account.user_id == run.user_id)
    ))
    subscription = db.scalar(select(Subscription).where(Subscription.user_id == run.user_id))
    return bool(
        user and user.status == "ACTIVE" and task and not task.archived and task.user_id == run.user_id
        and account_allowed
        and subscription and subscription.expires_at and subscription.expires_at > utc_now()
        and run.snapshot.get("plugin_id", "douyin_streak") in PLUGINS
        and run.snapshot.get("plugin_id", "douyin_streak") in allowed_plugins(subscription.snapshot)
        and ("tasks.schedule" if run.trigger_type == "SCHEDULED" else "tasks.manual") in effective_permissions(subscription.snapshot)
    )
