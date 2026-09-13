import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app import admin_create_plan, admin_delete_plan, admin_update_plan
from backend.db import Base
from backend.models import Plan, User
from backend.schemas import PlanCreateIn, PlanUpdateIn
from backend.app import admin_update_general_settings, register
from backend.schemas import GeneralSettingsIn, RegisterIn
from backend.models import SystemSetting
from backend.services.platform_settings import registration_enabled
from fastapi import Response


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


def payload(**changes):
    return PlanCreateIn(**{
        "id": "custom", "slug": "custom", "name": "Custom",
        "description": "", "monthly_cents": 100, "quarterly_cents": 300,
        "yearly_cents": 1200, "account_limit": 1, "task_limit": 1,
        "run_limit": 100, "features": [], **changes,
    })


def test_create_custom_id_update_legacy_payload_and_delete(db):
    actor = User(id="admin")
    plan = admin_create_plan(payload(), actor, db)
    assert plan.id == "custom"
    update = PlanUpdateIn(**payload(name="Updated").model_dump(exclude={"id", "slug"}))
    assert admin_update_plan(plan.id, update, actor, db).slug == "custom"
    assert plan.name == "Updated"
    admin_delete_plan(plan.id, actor, db)
    assert db.get(Plan, "custom") is None


def test_duplicate_slug_returns_conflict(db):
    actor = User(id="admin")
    admin_create_plan(payload(), actor, db)
    with pytest.raises(HTTPException) as error:
        admin_create_plan(payload(id="other"), actor, db)
    assert error.value.status_code == 409


def test_registration_setting_persists_and_blocks_registration(db):
    actor = User(id="admin")
    admin_update_general_settings(GeneralSettingsIn(registration_enabled=False), actor, db)
    db.expire_all()
    assert not registration_enabled(db)
    assert db.get(SystemSetting, "registration_enabled").value_encrypted != "false"
    with pytest.raises(HTTPException) as error:
        register(RegisterIn(email="new@example.com", name="New", password="long-password"), Response(), db)
    assert error.value.status_code == 403
    admin_update_general_settings(GeneralSettingsIn(registration_enabled=True), actor, db)
    assert registration_enabled(db)
