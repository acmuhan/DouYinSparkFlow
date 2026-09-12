from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    """Database timestamps are naive UTC, never local wall-clock time."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def next_daily_run(schedule_time: str, zone_name: str, after: datetime) -> datetime:
    zone = ZoneInfo(zone_name)
    instant = after.replace(tzinfo=timezone.utc) if after.tzinfo is None else after.astimezone(timezone.utc)
    hour, minute = map(int, schedule_time.split(":"))
    day = instant.astimezone(zone).date()
    # Run once per local date: use the first fold; skip nonexistent local times.
    for offset in range(370):
        local = datetime.combine(day + timedelta(days=offset), datetime.min.time()).replace(hour=hour, minute=minute)
        candidate = local.replace(tzinfo=zone, fold=0).astimezone(timezone.utc)
        if candidate.astimezone(zone).replace(tzinfo=None) == local and candidate > instant:
            return candidate.replace(tzinfo=None)
    raise ValueError("could not calculate next daily run")
