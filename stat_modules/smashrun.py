from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests


logger = logging.getLogger(__name__)
BASE_URL = "https://api.smashrun.com/v1"
TIMEOUT_SECONDS = 30


def _headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _parse_datetime(raw: str | None) -> datetime | None:
    if not raw or not isinstance(raw, str):
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _extract_elevation_feet(activity: dict[str, Any]) -> float | None:
    for feet_key in ("elevationGainFeet", "climbFeet"):
        value = activity.get(feet_key)
        if isinstance(value, (int, float)):
            return float(value)

    for meters_key in (
        "elevationGain",
        "elevationGainMeters",
        "climb",
        "climbMeters",
        "totalAscent",
    ):
        value = activity.get(meters_key)
        if isinstance(value, (int, float)):
            return float(value) * 3.28084
    return None


def get_activities(access_token: str | None, max_items: int = 600) -> list[dict[str, Any]]:
    if not access_token:
        return []

    activities: list[dict[str, Any]] = []
    seen_ids: set[Any] = set()
    offset = 0
    page_size = 100
    while len(activities) < max_items:
        try:
            response = requests.get(
                f"{BASE_URL}/my/activities",
                headers=_headers(access_token),
                params={"count": page_size, "offset": offset},
                timeout=TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Smashrun activity fetch failed: %s", exc)
            break

        page = response.json()
        if not isinstance(page, list) or not page:
            break
        new_items = 0
        for item in page:
            activity_id = item.get("activityId")
            if activity_id is not None and activity_id in seen_ids:
                continue
            if activity_id is not None:
                seen_ids.add(activity_id)
            activities.append(item)
            new_items += 1
        if new_items == 0:
            break
        if len(page) < page_size:
            break
        offset += page_size

    return activities[:max_items]


def get_notables(access_token: str | None, latest_activity_id: int | None = None) -> list[str]:
    if not access_token:
        return []

    if latest_activity_id is None:
        activities = get_activities(access_token, max_items=1)
        if not activities:
            return []
        latest_activity_id = activities[0].get("activityId")
        if latest_activity_id is None:
            return []

    try:
        response = requests.get(
            f"{BASE_URL}/my/activities/{latest_activity_id}/notables",
            headers=_headers(access_token),
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Smashrun notables fetch failed: %s", exc)
        return []

    notables = response.json()
    if not isinstance(notables, list):
        return []
    return [n.get("description", "").strip() for n in notables if n.get("description")]


def get_longest_streak(access_token: str | None) -> int | None:
    if not access_token:
        return None
    try:
        response = requests.get(
            f"{BASE_URL}/my/stats",
            headers=_headers(access_token),
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        logger.error("Smashrun stats fetch failed: %s", exc)
        return None
    value = payload.get("longestStreak")
    if isinstance(value, int):
        return value
    return None


def get_latest_elevation_feet(activities: list[dict[str, Any]]) -> float | None:
    if not activities:
        return None
    return _extract_elevation_feet(activities[0])


def aggregate_elevation_totals(
    activities: list[dict[str, Any]],
    now_utc: datetime | None = None,
    timezone_name: str = "UTC",
) -> dict[str, float]:
    now = now_utc or datetime.now(timezone.utc)
    try:
        local_tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        local_tz = ZoneInfo("UTC")

    local_today = now.astimezone(local_tz).date()
    week_start_date = local_today - timedelta(days=6)
    month_start_date = local_today - timedelta(days=29)
    year_start_date = date(local_today.year, 1, 1)

    totals = {"week": 0.0, "month": 0.0, "year": 0.0}
    for activity in activities:
        activity_time = _parse_datetime(
            activity.get("startDateTimeUtc")
            or activity.get("startDateTimeLocal")
            or activity.get("startDate")
        )
        if activity_time is None:
            continue

        elevation_feet = _extract_elevation_feet(activity)
        if elevation_feet is None:
            continue

        local_activity_date = activity_time.astimezone(local_tz).date()
        if local_activity_date >= week_start_date:
            totals["week"] += elevation_feet
        if local_activity_date >= month_start_date:
            totals["month"] += elevation_feet
        if local_activity_date >= year_start_date:
            totals["year"] += elevation_feet

    return totals
