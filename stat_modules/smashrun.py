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


def _to_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _parse_datetime(raw: str | None) -> datetime | None:
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(float(raw), tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
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
        value = _to_float(activity.get(feet_key))
        if value is not None:
            return value

    for meters_key in (
        "elevationGain",
        "elevationGainMeters",
        "climb",
        "climbMeters",
        "totalAscent",
        "elevation",
    ):
        value = _to_float(activity.get(meters_key))
        if value is not None:
            return value * 3.28084
    return None


def _get_activities_basic(access_token: str, max_items: int = 600) -> list[dict[str, Any]]:
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
            logger.error("Smashrun activity fetch failed (basic): %s", exc)
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


def get_activities(access_token: str | None, max_items: int = 600) -> list[dict[str, Any]]:
    if not access_token:
        return []

    activities: list[dict[str, Any]] = []
    seen_ids: set[Any] = set()
    page_index = 0
    page_size = 100
    while len(activities) < max_items:
        try:
            response = requests.get(
                f"{BASE_URL}/my/activities/search/extended",
                headers=_headers(access_token),
                params={"count": page_size, "page": page_index},
                timeout=TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Smashrun extended activity fetch failed, falling back to basic endpoint: %s", exc)
            return _get_activities_basic(access_token, max_items=max_items)

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
        page_index += 1

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


def get_stats(access_token: str | None) -> dict[str, Any] | None:
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
    if isinstance(payload, dict):
        return payload
    return None


def get_badges(access_token: str | None) -> list[dict[str, Any]]:
    if not access_token:
        return []
    try:
        response = requests.get(
            f"{BASE_URL}/my/badges",
            headers=_headers(access_token),
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        logger.error("Smashrun badges fetch failed: %s", exc)
        return []

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("badges", "items", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def get_longest_streak(access_token: str | None) -> int | None:
    payload = get_stats(access_token)
    if not payload:
        return None
    value = payload.get("longestStreak")
    if isinstance(value, int):
        return value
    return None


def get_latest_elevation_feet(activities: list[dict[str, Any]]) -> float | None:
    if not activities:
        return None
    return _extract_elevation_feet(activities[0])


def _extract_distance_meters(activity: dict[str, Any]) -> float | None:
    for meters_key in ("distanceMeters", "distance"):
        value = _to_float(activity.get(meters_key))
        if value is not None and value > 0:
            return value

    for miles_key in ("distanceMiles",):
        value = _to_float(activity.get(miles_key))
        if value is not None and value > 0:
            return value * 1609.34

    for km_key in ("distanceKm", "distanceKilometers"):
        value = _to_float(activity.get(km_key))
        if value is not None and value > 0:
            return value * 1000.0
    return None


def _extract_activity_datetime(activity: dict[str, Any]) -> datetime | None:
    return _parse_datetime(
        activity.get("startDateTimeUtc")
        or activity.get("startDateTimeLocal")
        or activity.get("startDateTime")
        or activity.get("startDate")
        or activity.get("date")
    )


def get_activity_record(
    activities: list[dict[str, Any]],
    strava_activity: dict[str, Any],
) -> dict[str, Any] | None:
    if not activities:
        return None

    strava_id = strava_activity.get("id")
    if strava_id is not None:
        for activity in activities:
            for key in ("stravaActivityId", "externalActivityId", "externalId"):
                candidate_id = activity.get(key)
                if candidate_id is None:
                    continue
                if str(candidate_id) == str(strava_id):
                    return activity

    strava_start = _parse_datetime(
        strava_activity.get("start_date")
        or strava_activity.get("start_date_local")
    )
    if strava_start is None:
        return activities[0]

    strava_distance = _to_float(strava_activity.get("distance"))
    best_score = None
    best_activity = None

    for activity in activities:
        activity_time = _extract_activity_datetime(activity)
        if activity_time is None:
            continue

        time_delta_seconds = abs((activity_time - strava_start).total_seconds())
        if time_delta_seconds > 12 * 3600:
            continue

        score = float(time_delta_seconds)
        activity_distance = _extract_distance_meters(activity)
        if strava_distance is not None and activity_distance is not None:
            score += abs(activity_distance - strava_distance) / 10.0

        if best_score is None or score < best_score:
            best_score = score
            best_activity = activity

    if best_activity is not None:
        return best_activity
    return activities[0]


def get_activity_elevation_feet(
    activities: list[dict[str, Any]],
    strava_activity: dict[str, Any],
) -> float | None:
    matched = get_activity_record(activities, strava_activity)
    if matched is None:
        return None
    elevation_feet = _extract_elevation_feet(matched)
    if elevation_feet is not None:
        return elevation_feet
    return get_latest_elevation_feet(activities)


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
        activity_time = _extract_activity_datetime(activity)
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
