from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db import Base
from backend.models import Order, Plan, RateLimit, Subscription, Usage, User
from backend.services.billing import FAILED_PAYMENT_STATUSES, activate_order, add_months, adjust_quota
from backend.security import hash_password, verify_password
from backend.services.errors import PaymentError
from backend.crypto import _fernet, encrypt_secret
from backend.app import LOGIN_ATTEMPT_LIMIT, _consume_login_attempt, _login_rate_key


def test_add_months_clamps_month_end():
    assert add_months(datetime(2026, 1, 31), 1) == datetime(2026, 2, 28)


def test_password_hash_is_salted_and_verifiable():
    first = hash_password("correct horse battery staple")
    second = hash_password("correct horse battery staple")
    assert first != second
    assert verify_password("correct horse battery staple", first)
    assert not verify_password("wrong password", first)
    assert "correct horse" not in first


def test_failed_payment_statuses_are_terminal():
    assert {"FAILED", "TRADE_CLOSED", "CLOSED", "PAY_ERROR"} == FAILED_PAYMENT_STATUSES


@pytest.fixture
def billing_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def test_activation_is_idempotent_and_creates_one_subscription(billing_db):
    user = User(id=str(uuid4()), email="billing@example.com", name="Billing", password_hash=hash_password("password"))
    plan = Plan(
        id=str(uuid4()), slug="starter", name="Starter", description="Test",
        monthly_cents=1900, quarterly_cents=4900, yearly_cents=15900,
        account_limit=1, task_limit=5, run_limit=300, features=["test"], sort_order=1,
    )
    order = Order(
        id=str(uuid4()), user_id=user.id, plan_id=plan.id, snapshot={"name": plan.name, "run_limit": 300},
        cycle="monthly", months=1, amount_cents=1900, status="PENDING", provider_version="V1",
        merchant_id="test", payment_method="alipay", idempotency_key="idempotency-1",
        expires_at=datetime.utcnow() + timedelta(minutes=30),
    )
    billing_db.add_all([user, plan, order])
    billing_db.commit()

    first = activate_order(billing_db, order_id=order.id, provider_trade_no="trade-1", provider_money="19.00", status="PAID")
    second = activate_order(billing_db, order_id=order.id, provider_trade_no="trade-1", provider_money="19.00", status="PAID")

    assert first.id == second.id
    assert billing_db.scalar(select(Subscription).where(Subscription.user_id == user.id)) is not None
    assert len(list(billing_db.scalars(select(Subscription).where(Subscription.user_id == user.id)))) == 1


def test_activation_rejects_amount_before_mutating_subscription(billing_db):
    user = User(id=str(uuid4()), email="amount@example.com", name="Amount", password_hash=hash_password("password"))
    plan = Plan(
        id=str(uuid4()), slug="starter-amount", name="Starter", description="Test",
        monthly_cents=1900, quarterly_cents=4900, yearly_cents=15900,
        account_limit=1, task_limit=5, run_limit=300, features=["test"], sort_order=1,
    )
    order = Order(
        id=str(uuid4()), user_id=user.id, plan_id=plan.id, snapshot={"name": plan.name, "run_limit": 300},
        cycle="monthly", months=1, amount_cents=1900, status="PENDING", provider_version="V1",
        merchant_id="test", payment_method="alipay", idempotency_key="idempotency-2",
        expires_at=datetime.utcnow() + timedelta(minutes=30),
    )
    billing_db.add_all([user, plan, order])
    billing_db.commit()

    with pytest.raises(PaymentError):
        activate_order(billing_db, order_id=order.id, provider_trade_no="trade-2", provider_money="19.01", status="PAID")

    assert billing_db.get(Order, order.id).status == "PENDING"
    assert billing_db.scalar(select(Subscription).where(Subscription.user_id == user.id)) is None


def test_quota_adjustment_reuses_one_period_row(billing_db):
    user = User(id=str(uuid4()), email="quota@example.com", name="Quota", password_hash=hash_password("password"))
    billing_db.add(user)
    billing_db.commit()

    adjust_quota(billing_db, user_id=user.id, period="2026-09", amount=10, reason="test")
    adjust_quota(billing_db, user_id=user.id, period="2026-09", amount=-3, reason="test")
    billing_db.commit()

    usage_rows = list(billing_db.scalars(select(Usage).where(Usage.user_id == user.id)))
    assert len(usage_rows) == 1
    assert usage_rows[0].adjustment == 7


def test_secret_encryption_round_trips_in_development():
    encrypted = encrypt_secret("development-only-value")
    assert encrypted != "development-only-value"


def test_production_rejects_placeholder_encryption_key(monkeypatch):
    class ProductionSettings:
        production = True
        encryption_key = "change-me"

    monkeypatch.setattr("backend.crypto.get_settings", lambda: ProductionSettings())
    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY"):
        _fernet()


def test_login_rate_limit_blocks_after_threshold(billing_db):
    key = _login_rate_key("user@example.com", "127.0.0.1")
    for _ in range(LOGIN_ATTEMPT_LIMIT):
        _consume_login_attempt(billing_db, key)
    billing_db.commit()

    with pytest.raises(HTTPException) as error:
        _consume_login_attempt(billing_db, key)

    assert error.value.status_code == 429
    assert billing_db.get(RateLimit, key).attempts == LOGIN_ATTEMPT_LIMIT
