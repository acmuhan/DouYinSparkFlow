from datetime import datetime

import pytest

from backend.services.billing import add_months


def test_add_months_clamps_month_end():
    assert add_months(datetime(2026, 1, 31), 1) == datetime(2026, 2, 28)

