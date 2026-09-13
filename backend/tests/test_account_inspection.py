import json
from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.crypto import encrypt_secret
from backend.db import Base
from backend.models import Account, Subscription, User
from backend.plugins.douyin_inspection import InspectionResult, parse_friends
from backend.schemas import AccountIn
from backend.services.account_inspection import claim_inspection, execute_inspection
from backend.services.scheduling import utc_now


def test_friend_parser_deduplicates_ids_and_ignores_bad_items():
    rows = parse_friends({"data": [{"sec_uid": "id", "nickname": "Name"}, {"sec_uid": "id", "remark_name": "Remark"}, {}, None]})
    assert rows == [{"id": "id", "name": "Remark", "unique_id": ""}]
    with pytest.raises(ValueError):
        parse_friends({"data": {}})


def test_cookie_domain_restriction_and_url_removal():
    with pytest.raises(ValueError):
        AccountIn(name="account", unique_id="id", cookies=[{"name": "session", "value": "secret", "domain": "attacker.example"}])
    parsed = AccountIn(name="account", unique_id="id", cookies=[{
        "name": "session", "value": "secret", "domain": ".douyin.com", "url": "https://attacker.example",
    }])
    assert "url" not in parsed.cookies[0]


def test_inspection_persists_and_does_not_revive_deleted_resource():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        db.add(User(id="user", name="User", email="user@example.com", password_hash="unused", status="ACTIVE"))
        db.add(Subscription(id="sub", user_id="user", plan_id="plan", snapshot={"permissions": ["accounts.validate"]},
                            expires_at=utc_now() + timedelta(days=1)))
        db.add(Account(id="account", user_id="user", name="Account", unique_id="user",
                       cookies_encrypted=encrypt_secret(json.dumps([])), status="UNVERIFIED", inspection_status="QUEUED"))
        db.commit()
        assert claim_inspection(db) == "account"
        db.commit()
    execute_inspection("account", session_factory=factory, inspector=lambda _: InspectionResult("READY", "ok", [{"id": "friend"}]))
    with factory() as db:
        assert db.get(Account, "account").status == "READY"
        assert db.get(Account, "account").friends == [{"id": "friend"}]
        db.get(Account, "account").inspection_status = "QUEUED"
        db.commit()
        claim_inspection(db)
        db.commit()

    def delete_during_inspection(_):
        with factory() as db:
            db.get(Account, "account").status = "DELETED"
            db.commit()
        return InspectionResult("READY", "ok")

    execute_inspection("account", session_factory=factory, inspector=delete_during_inspection)
    with factory() as db:
        assert db.get(Account, "account").status == "DELETED"
    engine.dispose()
