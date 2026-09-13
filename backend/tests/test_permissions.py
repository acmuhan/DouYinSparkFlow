from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.db import Base
from backend.models import Account, Run, Subscription, Task, User
from backend.permissions import effective_permissions
from backend.schemas import PlanCreateIn
from backend.services.errors import QuotaError
from backend.services.jobs import enqueue_run, execution_allowed
from backend.services.plugin_access import ensure_permission
from backend.services.scheduling import utc_now


def test_permission_defaults_and_validation():
    assert effective_permissions({"permissions": []}) == []
    assert "tasks.manual" in effective_permissions({})
    assert "future.permission" not in effective_permissions({})
    fields = dict(slug="custom", name="Custom", description="", monthly_cents=1, quarterly_cents=1,
                  yearly_cents=1, account_limit=1, task_limit=1, run_limit=1, features=[])
    assert PlanCreateIn(**fields).permissions == []
    with pytest.raises(ValueError):
        PlanCreateIn(**fields, permissions=["unregistered"])


def test_scheduled_and_manual_execution_enforced_separately():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        db.add(User(id="user", email="user@example.com", name="User", password_hash="unused", status="ACTIVE"))
        db.add(Account(id="account", user_id="user", name="Account", unique_id="u", cookies_encrypted="unused", status="READY"))
        task = Task(id="task", user_id="user", account_id="account", plugin_id="douyin_streak", name="Task",
                    targets=["friend"], message="message", hitokoto_types=[], schedule_time="12:00", timezone="UTC", archived=False)
        subscription = Subscription(id="sub", user_id="user", plan_id="plan",
                                    snapshot={"permissions": ["tasks.manual"], "plugin_permissions": ["douyin_streak"], "run_limit": 100},
                                    expires_at=utc_now() + timedelta(days=1))
        db.add_all([task, subscription])
        db.commit()
        ensure_permission(db, "user", "tasks.manual")
        with pytest.raises(QuotaError):
            enqueue_run(db, task=task, trigger_type="SCHEDULED")
        run = enqueue_run(db, task=task, trigger_type="MANUAL")
        db.commit()
        assert execution_allowed(db, run, "account")
        subscription.snapshot = {**subscription.snapshot, "permissions": []}
        db.commit()
        assert not execution_allowed(db, run, "account")
        with pytest.raises(QuotaError):
            ensure_permission(db, "user", "api.access")
        assert db.get(Run, run.id) is not None
    engine.dispose()
