import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.db import Base
from backend.models import Plan, SystemSetting, User
from backend.schemas import CheckoutIn, OrderOut
from backend.services.billing import create_order
from backend.services.epay import v1_sign, verify_callback
from backend.services.errors import PaymentError
from backend.services.payment_settings import PaymentUpdate, load_payment, order_payment_config, save_payment


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


def config(key="old-secret"):
    return PaymentUpdate(enabled=True, epay_url="https://pay.example.com", epay_pid="merchant", epay_key=key)


def test_rotation_keeps_old_orders_verifiable_and_hides_keys(db):
    out = save_payment(db, config())
    db.add(User(id="user", name="User", email="user@example.com", password_hash="unused"))
    db.add(Plan(id="plan", slug="custom", name="Custom", description="", monthly_cents=100, quarterly_cents=300,
                yearly_cents=1200, account_limit=1, task_limit=1, run_limit=100, features=[], active=True))
    db.commit()
    assert out.key_configured
    assert "old-secret" not in out.model_dump_json()
    assert "old-secret" not in db.get(SystemSetting, "payment").value_encrypted
    order = create_order(db, user_id="user", data=CheckoutIn(plan_id="plan", cycle="monthly", idempotency_key="checkout-1"),
                         app_url="https://console.example.com")
    assert "old-secret" not in OrderOut.model_validate(order).model_dump_json()
    assert "payment_config_encrypted" not in OrderOut.model_validate(order).model_dump()
    save_payment(db, config("new-secret"))
    db.commit()
    params = {"pid": "merchant", "out_trade_no": order.id, "trade_no": "trade", "money": "1.00", "trade_status": "TRADE_SUCCESS", "sign_type": "MD5"}
    params["sign"] = v1_sign(params, "old-secret")
    verify_callback(params, settings=order_payment_config(order))
    with pytest.raises(PaymentError):
        verify_callback(params, settings=load_payment(db))
    # Retrying the same checkout does not replace its verification snapshot.
    duplicate = create_order(db, user_id="user", data=CheckoutIn(plan_id="plan", cycle="monthly", idempotency_key="checkout-1"),
                             app_url="https://console.example.com")
    assert duplicate.id == order.id
    verify_callback(params, settings=order_payment_config(duplicate))


def test_merchant_and_algorithm_are_not_chosen_by_callback():
    settings = config()
    params = {"pid": "different", "sign_type": "MD5"}
    params["sign"] = v1_sign(params, "old-secret")
    with pytest.raises(PaymentError):
        verify_callback(params, settings=settings)
    params = {"pid": "merchant", "sign_type": "RSA-SHA256"}
    params["sign"] = v1_sign(params, "old-secret")
    with pytest.raises(PaymentError):
        verify_callback(params, settings=settings)
    params = {"pid": "merchant", "sign_type": "MD5"}
    params["sign"] = v1_sign(params, "")
    with pytest.raises(PaymentError):
        verify_callback(params, settings=config(""))


def test_new_gateway_requires_new_secret(db):
    save_payment(db, config())
    db.commit()
    changed = PaymentUpdate(enabled=True, epay_url="https://other.example.com", epay_pid="merchant")
    with pytest.raises(ValueError):
        save_payment(db, changed)
    save_payment(db, config(None))
    db.commit()
    assert load_payment(db).epay_key == "old-secret"
