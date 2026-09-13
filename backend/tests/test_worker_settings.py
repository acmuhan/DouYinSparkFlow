import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend import worker
from backend.app import admin_update_general_settings
from backend.db import Base
from backend.models import Worker, User
from backend.schemas import GeneralSettingsIn
from backend.services.platform_settings import WorkerSettings, set_worker_settings, worker_settings


@pytest.fixture
def factory():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    yield sessions
    engine.dispose()


def test_partial_general_update_preserves_worker_config(factory):
    with factory() as db:
        set_worker_settings(db, WorkerSettings(enabled=False, timeout=123))
        db.commit()
        output = admin_update_general_settings(GeneralSettingsIn(registration_enabled=True), User(id="admin"), db)
        assert output.worker_enabled is False
        assert output.worker_timeout == 123
    with factory() as db:
        assert worker_settings(db) == WorkerSettings(enabled=False, timeout=123)
    with pytest.raises(ValueError):
        GeneralSettingsIn(registration_enabled=True, worker_timeout=3601)


def test_paused_worker_resumes_without_restart(factory, monkeypatch):
    with factory() as db:
        set_worker_settings(db, WorkerSettings(enabled=False, timeout=123))
        db.commit()
    calls = []
    monkeypatch.setattr(worker, "SessionLocal", factory)
    monkeypatch.setattr(worker, "scheduler_tick", lambda _: calls.append("schedule"))

    def claim(db, worker_id):
        calls.append("claim")
        return "run"

    def sleep(_):
        assert calls == []
        with factory() as db:
            assert db.scalar(select(Worker)).status == "PAUSED"
            set_worker_settings(db, WorkerSettings(enabled=True, timeout=234))
            db.commit()
        calls.append("resume")

    def supervise(run_id, worker_id, timeout):
        assert run_id == "run"
        assert timeout == 234
        assert calls == ["resume", "schedule", "claim"]
        raise KeyboardInterrupt()

    monkeypatch.setattr(worker, "claim_next_run", claim)
    monkeypatch.setattr(worker.time, "sleep", sleep)
    monkeypatch.setattr(worker, "supervise_run", supervise)
    worker.main()
    with factory() as db:
        assert db.scalar(select(Worker)).status == "OFFLINE"
