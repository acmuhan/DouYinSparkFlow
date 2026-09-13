from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app import app, current_user
from backend.db import Base, get_db
from backend.models import Account, ApiKey, AuthSession, Run, Subscription, Task, User
from backend.security import hash_password, verify_password
from backend.services.scheduling import utc_now


@pytest.fixture
def context():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        users = {
            key: User(id=key, email=f"{key}@example.com", name=key, password_hash=hash_password("password"), role=role, status="ACTIVE")
            for key, role in [("admin", "ADMIN"), ("alice", "USER"), ("bob", "USER")]
        }
        db.add_all(users.values())
        db.commit()
        identity = {"id": "admin"}
        saved = app.dependency_overrides.copy()
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[current_user] = lambda: users[identity["id"]]
        http = TestClient(app)
        try:
            yield http, db, identity
        finally:
            http.close()
            app.dependency_overrides.clear()
            app.dependency_overrides.update(saved)
    engine.dispose()


def credentials(db):
    db.add(AuthSession(id="session", user_id="alice", expires_at=utc_now() + timedelta(days=1)))
    db.add(ApiKey(id="key", user_id="alice", name="key", prefix="sf_", token_hash="unique", expires_at=utc_now() + timedelta(days=1)))
    db.commit()


def test_admin_create_and_rebind(context):
    http, db, _ = context
    body = {"name": "New User", "email": " NEW@example.com ", "password": "  password  "}
    created = http.post("/api/v1/admin/users", json=body)
    assert created.status_code == 201, created.text
    assert "password_hash" not in created.json()
    assert created.json()["email"] == "new@example.com"
    assert verify_password(body["password"], db.get(User, created.json()["id"]).password_hash)
    assert http.post("/api/v1/admin/users", json=body).status_code == 409
    credentials(db)
    duplicate = http.patch("/api/v1/admin/users/alice", json={"email": "bob@example.com", "name": "Alice"})
    assert duplicate.status_code == 409, duplicate.text
    assert db.get(AuthSession, "session") is not None
    assert db.get(ApiKey, "key").revoked_at is None
    assert http.patch("/api/v1/admin/users/alice", json={"email": "rebound@example.com", "name": "Alice"}).status_code == 200
    assert db.get(AuthSession, "session") is None
    assert db.get(ApiKey, "key").revoked_at is not None


def test_delete_revokes_execution_and_cannot_be_reactivated(context):
    http, db, _ = context
    credentials(db)
    db.add(Account(id="account", user_id="alice", name="Account", unique_id="alice", cookies_encrypted="secret", status="READY"))
    db.flush()
    db.add(Task(id="task", user_id="alice", account_id="account", name="Task", targets=["friend"], message="hi",
                hitokoto_types=[], schedule_time="12:00", timezone="UTC", enabled=True, archived=False))
    db.flush()
    for state in ["QUEUED", "RUNNING"]:
        db.add(Run(id=state, user_id="alice", task_id="task", status=state, trigger_type="MANUAL", snapshot={}))
    db.commit()
    assert http.delete("/api/v1/admin/users/alice").status_code == 204
    assert http.delete("/api/v1/admin/users/alice").status_code == 204
    assert db.get(User, "alice").status == "DELETED"
    assert db.get(AuthSession, "session") is None
    assert db.get(ApiKey, "key").revoked_at is not None
    assert db.get(Account, "account").cookies_encrypted == ""
    assert db.get(Task, "task").archived
    assert db.get(Run, "QUEUED").status == "CANCELLED"
    assert db.get(Run, "RUNNING").cancel_requested
    assert http.patch("/api/v1/admin/users/alice/status", json={"status": "ACTIVE"}).status_code == 404
    assert "alice" not in [item["id"] for item in http.get("/api/v1/admin/users").json()]
    assert db.scalar(select(User).where(User.email == "alice@example.com")) is None


def test_permissions_and_administrator_protection(context):
    http, _, identity = context
    assert http.delete("/api/v1/admin/users/admin").status_code == 409
    assert http.patch("/api/v1/admin/users/admin/status", json={"status": "BANNED"}).status_code == 409
    identity["id"] = "bob"
    assert http.post("/api/v1/admin/users", json={"name": "New", "email": "new@example.com", "password": "password"}).status_code == 403
    assert http.patch("/api/v1/admin/users/alice", json={"name": "Alice", "email": "new@example.com"}).status_code == 403
    assert http.delete("/api/v1/admin/users/alice").status_code == 403


def test_smtp_permissions_and_selected_user_recipient(context, monkeypatch):
    http, _, identity = context
    sent = []

    def send(_db, recipient, payload):
        sent.append((recipient, payload.subject))
        return "<test@example.com>"

    monkeypatch.setattr("backend.app.send_mail", send)
    response = http.post("/api/v1/admin/users/alice/email", json={"subject": "Hello", "body": "Message"})
    assert response.status_code == 200
    assert response.json()["status"] == "ACCEPTED"
    assert sent == [("alice@example.com", "Hello")]
    assert http.post("/api/v1/admin/settings/smtp/test").status_code == 200
    assert sent[-1][0] == "admin@example.com"
    identity["id"] = "bob"
    assert http.get("/api/v1/admin/settings/smtp").status_code == 403
    assert http.put("/api/v1/admin/settings/smtp", json={}).status_code == 403
    assert http.post("/api/v1/admin/settings/smtp/test").status_code == 403
    assert http.post("/api/v1/admin/users/alice/email", json={"subject": "Hello", "body": "Message"}).status_code == 403
    assert len(sent) == 2


def test_resource_refresh_tenant_isolation_and_secret_response(context):
    http, db, identity = context
    db.add(Subscription(id="sub", user_id="alice", plan_id="plan", snapshot={"permissions": ["accounts.validate"]},
                        expires_at=utc_now() + timedelta(days=1)))
    db.add(Account(id="account", user_id="alice", name="Account", unique_id="alice",
                   cookies_encrypted="old-secret", status="READY", inspection_status="SUCCEEDED",
                   friends=[{"id": "old-friend", "name": "Old", "unique_id": ""}]))
    db.commit()
    body = {"name": "Updated", "unique_id": "alice", "cookies": [
        {"name": "sessionid", "value": "new-secret", "domain": ".douyin.com", "path": "/"},
    ]}
    identity["id"] = "bob"
    assert http.get("/api/v1/accounts/account/friends").status_code == 404
    assert http.post("/api/v1/accounts/account/validate").status_code == 404
    assert http.patch("/api/v1/accounts/account", json=body).status_code == 404
    assert db.get(Account, "account").cookies_encrypted == "old-secret"
    identity["id"] = "alice"
    assert http.get("/api/v1/accounts/account/friends").json()["items"][0]["id"] == "old-friend"
    response = http.patch("/api/v1/accounts/account", json=body)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "UNVERIFIED"
    assert response.json()["inspection_status"] == "QUEUED"
    assert "new-secret" not in response.text
    assert http.get("/api/v1/accounts/account/friends").json()["items"] == []
    assert db.get(Account, "account").cookies_encrypted != "new-secret"
    assert http.post("/api/v1/accounts/account/validate").status_code == 202
