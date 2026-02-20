from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..strava_client import get_gap_speed_mps, mps_to_pace


logger = logging.getLogger(__name__)


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
    run_count = 0
    gap_speed_sum = 0.0
    gap_count = 0
    avg_speed_sum = 0.0
    avg_speed_count = 0

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
        run_count += 1
        moving_time = int(activity.get("moving_time", 0) or 0)
        duration_seconds += moving_time
        calories += _calories_for_activity(activity)

        gap_speed = get_gap_speed_mps(activity)
        if isinstance(gap_speed, (int, float)) and gap_speed > 0:
            gap_speed_sum += float(gap_speed)
            gap_count += 1

        avg_speed = activity.get("average_speed")
        if isinstance(avg_speed, (int, float)) and avg_speed > 0:
            avg_speed_sum += float(avg_speed)
            avg_speed_count += 1

    if gap_count > 0:
        gap = mps_to_pace(gap_speed_sum / gap_count)
        gap_source = "strava_gap"
    elif avg_speed_count > 0:
        gap = mps_to_pace(avg_speed_sum / avg_speed_count)
        gap_source = "strava_avg_speed"
    else:
        gap = "N/A"
        gap_source = "none"

    return {
        "gap": gap,
        "distance": distance_meters / 1609.34,
        "elevation": float(elevation_feet),
        "duration": _format_duration(duration_seconds),
        "beers_earned": round(calories / 150.0, 1),
        "calories": round(calories, 1),
        "run_count": run_count,
        "_gap_source": gap_source,
    }


def _parse_garmin_start_utc(activity: dict[str, Any]) -> datetime | None:
    raw = activity.get("startTimeGMT")
    if isinstance(raw, str):
        try:
            return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    raw_iso = activity.get("startTimeLocal")
    if isinstance(raw_iso, str):
        try:
            parsed = datetime.fromisoformat(raw_iso)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    return None


def _is_garmin_run(activity: dict[str, Any]) -> bool:
    type_key = str((activity.get("activityType") or {}).get("typeKey", "")).lower()
    return type_key in {
        "running",
        "track_running",
        "virtual_running",
        "trail_running",
        "treadmill_running",
    }


def _garmin_gap_speed(activity: dict[str, Any]) -> float | None:
    for key in ("avgGradeAdjustedSpeed", "averageGradeAdjustedSpeed"):
        value = activity.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    return None


def get_garmin_period_fallback(
    client: Any | None,
    now_utc: datetime | None = None,
    timezone_name: str = "UTC",
) -> dict[str, dict[str, Any]] | None:
    if client is None:
        return None

    now = now_utc or datetime.now(timezone.utc)
    try:
        local_tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        local_tz = ZoneInfo("UTC")

    local_today = now.astimezone(local_tz).date()
    week_start_date = local_today - timedelta(days=6)
    month_start_date = local_today - timedelta(days=29)
    year_start_date = date(local_today.year, 1, 1)

    try:
        activities = client.get_activities_by_date(
            year_start_date.isoformat(),
            local_today.isoformat(),
        )
    except Exception as exc:  # pragma: no cover - depends on live Garmin API
        logger.error("Garmin period activity fetch failed: %s", exc)
        return None

    if not isinstance(activities, list):
        return None

    buckets: dict[str, dict[str, float | int]] = {
        "week": {"calories": 0.0, "gap_speed_sum": 0.0, "gap_count": 0},
        "month": {"calories": 0.0, "gap_speed_sum": 0.0, "gap_count": 0},
        "year": {"calories": 0.0, "gap_speed_sum": 0.0, "gap_count": 0},
    }

    for activity in activities:
        if not isinstance(activity, dict) or not _is_garmin_run(activity):
            continue

        activity_start = _parse_garmin_start_utc(activity)
        if activity_start is None:
            continue

        local_date = activity_start.astimezone(local_tz).date()
        targets: list[str] = []
        if local_date >= week_start_date:
            targets.append("week")
        if local_date >= month_start_date:
            targets.append("month")
        if local_date >= year_start_date:
            targets.append("year")
        if not targets:
            continue

        calories = activity.get("calories")
        gap_speed = _garmin_gap_speed(activity)

        for target in targets:
            if isinstance(calories, (int, float)) and calories > 0:
                buckets[target]["calories"] += float(calories)
            if isinstance(gap_speed, (int, float)) and gap_speed > 0:
                buckets[target]["gap_speed_sum"] += float(gap_speed)
                buckets[target]["gap_count"] += 1

    fallback: dict[str, dict[str, Any]] = {}
    for period, data in buckets.items():
        gap_count = int(data["gap_count"])
        gap = "N/A"
        if gap_count > 0:
            gap = mps_to_pace(float(data["gap_speed_sum"]) / gap_count)

        calories_total = float(data["calories"])
        fallback[period] = {
            "gap": gap,
            "beers_earned": round(calories_total / 150.0, 1),
            "calories": calories_total,
            "gap_count": gap_count,
        }

    return fallback


def _apply_period_fallback(
    summary: dict[str, Any],
    fallback: dict[str, Any] | None,
) -> dict[str, Any]:
    if fallback:
        source = str(summary.get("_gap_source") or "none")
        fallback_gap = fallback.get("gap")
        if source != "strava_gap" and isinstance(fallback_gap, str) and fallback_gap != "N/A":
            summary["gap"] = fallback_gap
            summary["_gap_source"] = "garmin_gap"

        current_beers = summary.get("beers_earned")
        fallback_beers = fallback.get("beers_earned")
        if (
            isinstance(current_beers, (int, float))
            and current_beers <= 0
            and isinstance(fallback_beers, (int, float))
            and fallback_beers > 0
        ):
            summary["beers_earned"] = round(float(fallback_beers), 1)

    summary.pop("_gap_source", None)
    return summary


def get_period_stats(
    strava_activities: list[dict[str, Any]],
    smashrun_elevation_totals: dict[str, float],
    now_utc: datetime | None = None,
    timezone_name: str = "UTC",
    garmin_period_fallback: dict[str, dict[str, Any]] | None = None,
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

    return {
        "week": _apply_period_fallback(week, (garmin_period_fallback or {}).get("week")),
        "month": _apply_period_fallback(month, (garmin_period_fallback or {}).get("month")),
        "year": _apply_period_fallback(year, (garmin_period_fallback or {}).get("year")),
    }
