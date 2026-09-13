from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from pydantic import BaseModel, ConfigDict, Field

from backend.db import Base
from backend.models import Run, Subscription, Task, User
from backend.plugins import PLUGINS, Plugin, allowed_plugins
from backend.schemas import PlanCreateIn, TaskIn
from backend.services.errors import QuotaError
from backend.services.jobs import enqueue_run
from backend.services.plugin_access import ensure_plugin_access
from backend.services.runner import browser_execution
from backend.services.scheduling import utc_now
from backend.app import create_task
from backend.services.jobs import claim_next_run
from backend.services.runner import execute_run


def test_permissions_are_explicit_and_legacy_scope_is_fixed():
    assert allowed_plugins({}) == ["douyin_streak"]
    assert allowed_plugins({"plugin_permissions": []}) == []
    with pytest.raises(ValueError):
        PlanCreateIn(slug="example", name="Example", description="", monthly_cents=1, quarterly_cents=1, yearly_cents=1,
                     account_limit=1, task_limit=1, run_limit=1, features=[], plugin_permissions=["unknown"])


def test_new_plugin_dispatch_does_not_use_douyin_runner(monkeypatch):
    calls = []
    def execute(**kwargs):
        calls.append(kwargs)
        return "plugin-result"
    monkeypatch.setitem(PLUGINS, "test_plugin", Plugin(
        id="test_plugin", name="Test", description="", execute=execute,
        config_model=BaseModel, requires_account=False,
    ))
    snapshot = SimpleNamespace(plugin_id="test_plugin")
    assert browser_execution(cookies=[], snapshot=snapshot, checkpoint=None, on_sent=None) == "plugin-result"
    assert calls[0]["snapshot"] is snapshot
    assert "test_plugin" not in allowed_plugins({})


def test_revoked_plugin_cannot_enqueue_even_with_quota():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        subscription = Subscription(id="subscription", user_id="user", plan_id="plan",
                                    snapshot={"run_limit": 100, "plugin_permissions": []},
                                    expires_at=utc_now() + timedelta(days=1))
        db.add(subscription)
        db.commit()
        with pytest.raises(QuotaError):
            ensure_plugin_access(db, "user", "douyin_streak")
        with pytest.raises(QuotaError):
            enqueue_run(db, task=Task(id="task", user_id="user", plugin_id="douyin_streak"), trigger_type="MANUAL")
        subscription.snapshot = {"plugin_permissions": ["douyin_streak"]}
        db.commit()
        ensure_plugin_access(db, "user", "douyin_streak")
        subscription.expires_at = utc_now() - timedelta(seconds=1)
        db.commit()
        with pytest.raises(QuotaError):
            ensure_plugin_access(db, "user", "douyin_streak")
    engine.dispose()


def test_task_rejects_unknown_plugin():
    with pytest.raises(ValueError):
        TaskIn(account_id="account", plugin_id="unknown", name="Task", targets=["target"],
               message="test", schedule_time="12:00")


def test_plugin_without_douyin_fields_runs_through_queue(monkeypatch):
    class DiagnosticConfig(BaseModel):
        model_config = ConfigDict(extra="forbid")
        repetitions: int = Field(ge=1, le=3)

    calls = []

    def diagnostic(*, cookies, snapshot, checkpoint, on_sent):
        assert cookies == []
        checkpoint()
        calls.append(snapshot.plugin_config)
        on_sent(snapshot.plugin_config["repetitions"])
        return SimpleNamespace(sent_count=snapshot.plugin_config["repetitions"], missing_count=0)

    monkeypatch.setitem(PLUGINS, "diagnostic", Plugin(
        id="diagnostic", name="Diagnostic", description="Test only", execute=diagnostic,
        config_model=DiagnosticConfig, requires_account=False, legacy_fields=(),
    ))
    fields = dict(plugin_id="diagnostic", name="Diagnostic", schedule_time="12:00", plugin_config={"repetitions": 2})
    with pytest.raises(ValueError):
        TaskIn(**{**fields, "plugin_config": {"repetitions": 4}})
    with pytest.raises(ValueError):
        TaskIn(**fields, account_id="unwanted-credentials")
    payload = TaskIn(**fields)
    assert payload.targets == [] and payload.message == ""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        user = User(id="user", email="user@example.com", name="User", password_hash="unused", status="ACTIVE")
        db.add(user)
        db.add(Subscription(id="sub", user_id="user", plan_id="plan", snapshot={
            "plugin_permissions": ["diagnostic"], "permissions": ["tasks.create", "tasks.manual"], "task_limit": 3, "run_limit": 10,
        }, expires_at=utc_now() + timedelta(days=1)))
        db.commit()
        task = create_task(payload, user, db)
        assert task.account_id is None
        assert task.plugin_config == {"repetitions": 2}
        run = enqueue_run(db, task=task, trigger_type="MANUAL")
        db.commit()
        run_id = claim_next_run(db, "worker")
        db.commit()
        # Editing the task cannot change an already queued configuration.
        task.plugin_config = {"repetitions": 1}
        db.commit()
    execute_run(run_id, "worker", session_factory=factory)
    with factory() as db:
        assert db.get(Run, run.id).status == "SUCCEEDED"
        assert db.get(Run, run.id).sent_count == 2
    assert calls == [{"repetitions": 2}]
    engine.dispose()


def test_legacy_douyin_configuration_is_normalized():
    task = TaskIn(account_id="account", name="Legacy", targets=["friend", "friend"],
                  message="hello", schedule_time="12:00")
    assert task.plugin_config == {"targets": ["friend"], "message": "hello", "hitokoto_types": []}
