import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app import app, current_user
from backend.db import Base, get_db
from backend.models import User


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        users = {
            key: User(id=key, email=f"{key}@example.com", name=key, password_hash="unused", role=role, status="ACTIVE")
            for key, role in [("admin", "ADMIN"), ("alice", "USER"), ("bob", "USER")]
        }
        db.add_all(users.values())
        db.commit()
        identity = {"id": "admin"}
        saved = app.dependency_overrides.copy()
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[current_user] = lambda: users[identity["id"]]
        try:
            # Do not execute production startup/seeding in this isolated database.
            http = TestClient(app, raise_server_exceptions=True)
            try:
                yield http, identity
            finally:
                http.close()
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(saved)
    engine.dispose()


def test_announcement_lifecycle_and_read_isolation(client):
    http, identity = client
    body = {"title": "Maintenance", "content": "Service update", "active": True}
    result = http.post("/api/v1/admin/announcements", json=body)
    assert result.status_code == 201, result.text
    item_id = result.json()["id"]
    identity["id"] = "alice"
    assert http.post("/api/v1/admin/announcements", json=body).status_code == 403
    assert http.get("/api/v1/admin/announcements").status_code == 403
    assert http.patch(f"/api/v1/admin/announcements/{item_id}", json=body).status_code == 403
    assert http.delete(f"/api/v1/admin/announcements/{item_id}").status_code == 403
    for _ in range(2):
        assert http.put(f"/api/v1/notifications/announcements/{item_id}/read").status_code == 204
    assert http.get("/api/v1/notifications/announcements").json()[0]["read_at"] is not None
    identity["id"] = "bob"
    assert http.get("/api/v1/notifications/announcements").json()[0]["read_at"] is None
    identity["id"] = "admin"
    assert http.patch(f"/api/v1/admin/announcements/{item_id}", json={**body, "active": False}).status_code == 200
    assert http.get("/api/v1/announcements").json() == []
    identity["id"] = "alice"
    assert http.get("/api/v1/notifications/announcements").json() == []
    assert http.put(f"/api/v1/notifications/announcements/{item_id}/read").status_code == 404
    identity["id"] = "admin"
    assert http.delete(f"/api/v1/admin/announcements/{item_id}").status_code == 204
    assert http.get("/api/v1/admin/announcements").json() == []


def test_blank_announcement_rejected(client):
    http, _ = client
    assert http.post("/api/v1/admin/announcements", json={"title": " ", "content": "text"}).status_code == 422
