from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from config import Settings
from strava_utils import StravaClient


def _parse_date(activity: dict[str, Any]) -> datetime.date | None:
    raw = activity.get("start_date")
    if not isinstance(raw, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).date()


def get_streak(lookback_days: int = 366) -> int | None:
    settings = Settings.from_env()
    settings.validate()
    client = StravaClient(settings)
    start_dt = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    activities = client.get_activities_after(start_dt)

    run_days = set()
    for activity in activities:
        sport_type = str(activity.get("sport_type", "")).lower()
        activity_type = str(activity.get("type", "")).lower()
        if sport_type not in {"run", "virtualrun"} and activity_type not in {"run", "virtualrun"}:
            continue
        activity_day = _parse_date(activity)
        if activity_day:
            run_days.add(activity_day)

    if not run_days:
        return None

    streak = 0
    day_cursor = max(run_days)
    while day_cursor in run_days:
        streak += 1
        day_cursor -= timedelta(days=1)
    return streak


if __name__ == "__main__":
    print(f"Current streak: {get_streak()}")
