from datetime import datetime

import pytest

from backend.services.billing import FAILED_PAYMENT_STATUSES, add_months
from backend.security import hash_password, verify_password


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
