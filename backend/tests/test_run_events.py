from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import run_events
from backend.crypto import encrypt_secret
from backend.db import Base
from backend.models import Account, Run, RunEvent, Subscription, Task, User
from backend.services.jobs import claim_next_run, enqueue_run
from backend.services.runner import execute_run
from backend.services.scheduling import utc_now


@pytest.fixture
def queued():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        db.add(User(id="user", name="User", email="user@example.com", password_hash="unused", status="ACTIVE"))
        db.add(Account(id="account", user_id="user", name="Account", unique_id="user",
                       cookies_encrypted=encrypt_secret("[]"), status="READY"))
        task = Task(id="task", user_id="user", account_id="account", plugin_id="douyin_streak", name="Task",
                    targets=["private-friend"], message="private-message", hitokoto_types=[],
                    schedule_time="12:00", timezone="UTC", enabled=False, archived=False)
        db.add(task)
        db.add(Subscription(id="sub", user_id="user", plan_id="plan", snapshot={"run_limit": 100},
                            expires_at=utc_now() + timedelta(days=1)))
        db.commit()
        run = enqueue_run(db, task=task, trigger_type="MANUAL")
        db.commit()
        assert claim_next_run(db, "worker") == run.id
        db.commit()
        run_id = run.id
    try:
        yield factory, run_id
    finally:
        engine.dispose()


def test_progress_events_and_tenant_access(queued):
    factory, run_id = queued

    def executor(**kwargs):
        kwargs["on_sent"](1)
        kwargs["on_sent"](1)
        return SimpleNamespace(sent_count=1, missing_count=0)

    execute_run(run_id, "worker", session_factory=factory, executor=executor)
    with factory() as db:
        events = run_events(run_id, User(id="user"), db)
        assert [item.code for item in events] == ["queued", "started", "progress", "succeeded"]
        assert events[-1].sent_count == 1
        assert db.get(Run, run_id).status == "SUCCEEDED"
        assert all("private-" not in item.message for item in events)
        with pytest.raises(HTTPException) as error:
            run_events(run_id, User(id="other-user"), db)
        assert error.value.status_code == 404


def test_failure_message_does_not_copy_executor_secrets(queued):
    factory, run_id = queued

    def fail(**_):
        raise RuntimeError("private-cookie private-message private-friend")

    execute_run(run_id, "worker", session_factory=factory, executor=fail)
    with factory() as db:
        run = db.get(Run, run_id)
        assert run.status == "FAILED"
        assert "private-" not in run.result
        events = list(db.scalars(select(RunEvent).where(RunEvent.run_id == run_id)))
        assert any(item.code == "failed" for item in events)
        assert all("private-" not in item.message for item in events)
