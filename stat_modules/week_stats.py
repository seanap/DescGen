from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from strava_utils import get_gap_speed_mps, mps_to_pace


def _parse_datetime(activity: dict[str, Any]) -> datetime | None:
    raw = activity.get("start_date")
    if not isinstance(raw, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_duration(total_seconds: int) -> str:
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{hours}h:{minutes:02d}m"


def _is_run(activity: dict[str, Any]) -> bool:
    sport_type = str(activity.get("sport_type", "")).lower()
    activity_type = str(activity.get("type", "")).lower()
    return sport_type in {"run", "virtualrun"} or activity_type in {"run", "virtualrun"}


def _calories_for_activity(activity: dict[str, Any]) -> float:
    calories = activity.get("calories")
    if isinstance(calories, (int, float)) and calories > 0:
        return float(calories)
    return 0.0


def summarize_period(
    activities: list[dict[str, Any]],
    start_utc: datetime,
    end_utc_exclusive: datetime,
    elevation_feet: float,
) -> dict[str, Any]:
    distance_meters = 0.0
    duration_seconds = 0
    calories = 0.0
    gap_weighted_speed = 0.0
    gap_total_seconds = 0

    for activity in activities:
        if not _is_run(activity):
            continue

        start_time = _parse_datetime(activity)
        if (
            start_time is None
            or start_time < start_utc
            or start_time >= end_utc_exclusive
        ):
            continue

        distance = float(activity.get("distance", 0) or 0)
        distance_meters += distance
        moving_time = int(activity.get("moving_time", 0) or 0)
        duration_seconds += moving_time
        calories += _calories_for_activity(activity)

        speed = get_gap_speed_mps(activity)
        if speed and moving_time > 0:
            gap_weighted_speed += speed * moving_time
            gap_total_seconds += moving_time

    average_gap_speed = (gap_weighted_speed / gap_total_seconds) if gap_total_seconds > 0 else None
    return {
        "gap": mps_to_pace(average_gap_speed),
        "distance": distance_meters / 1609.34,
        "elevation": float(elevation_feet),
        "duration": _format_duration(duration_seconds),
        "beers_earned": round(calories / 150.0, 1),
    }


def get_period_stats(
    strava_activities: list[dict[str, Any]],
    smashrun_elevation_totals: dict[str, float],
    now_utc: datetime | None = None,
    timezone_name: str = "UTC",
) -> dict[str, dict[str, Any]]:
    now = now_utc or datetime.now(timezone.utc)
    try:
        local_tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        local_tz = ZoneInfo("UTC")

    local_today = now.astimezone(local_tz).date()
    week_start_date = local_today - timedelta(days=6)
    month_start_date = local_today - timedelta(days=29)
    year_start_date = date(local_today.year, 1, 1)

    week_start = datetime.combine(week_start_date, datetime.min.time(), tzinfo=local_tz).astimezone(timezone.utc)
    month_start = datetime.combine(month_start_date, datetime.min.time(), tzinfo=local_tz).astimezone(timezone.utc)
    year_start = datetime.combine(year_start_date, datetime.min.time(), tzinfo=local_tz).astimezone(timezone.utc)
    end_exclusive = datetime.combine(
        local_today + timedelta(days=1),
        datetime.min.time(),
        tzinfo=local_tz,
    ).astimezone(timezone.utc)

    week = summarize_period(
        strava_activities,
        week_start,
        end_exclusive,
        smashrun_elevation_totals.get("week", 0.0),
    )
    month = summarize_period(
        strava_activities,
        month_start,
        end_exclusive,
        smashrun_elevation_totals.get("month", 0.0),
    )
    year = summarize_period(
        strava_activities,
        year_start,
        end_exclusive,
        smashrun_elevation_totals.get("year", 0.0),
    )
    return {"week": week, "month": month, "year": year}
