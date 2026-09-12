from backend.services.epay import v1_sign, validate_money
from backend.services.errors import PaymentError


def test_v1_sign_is_deterministic():
    assert v1_sign({"b": "2", "a": "1"}, "secret") == "8d9f51949e440aa629fd1a035708473a"


def test_validate_money_rejects_mismatch():
    try:
        validate_money(1900, "19.01")
    except PaymentError:
        return
    raise AssertionError("expected PaymentError")
