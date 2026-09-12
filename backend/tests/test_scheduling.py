from datetime import datetime

from backend.services.scheduling import next_daily_run


def test_next_daily_run_uses_user_timezone():
    # 09:30 in Shanghai is 01:30 UTC on the same day.
    assert next_daily_run("09:30", "Asia/Shanghai", datetime(2026, 9, 12, 0, 0)) == datetime(2026, 9, 12, 1, 30)


def test_next_daily_run_rolls_to_next_local_day_after_time():
    assert next_daily_run("09:30", "Asia/Shanghai", datetime(2026, 9, 12, 2, 0)) == datetime(2026, 9, 13, 1, 30)


def test_next_daily_run_handles_dst_zone():
    # 09:30 America/New_York is 13:30 UTC while daylight saving is active.
    assert next_daily_run("09:30", "America/New_York", datetime(2026, 7, 1, 12, 0)) == datetime(2026, 7, 1, 13, 30)
