from __future__ import annotations

import logging
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import Settings
from storage import read_json, write_json
from strava_client import MAX_ACTIVITY_PAGES, StravaClient


logger = logging.getLogger(__name__)

DEFAULT_DASHBOARD_DATA_FILE = "dashboard_data.json"
DEFAULT_CACHE_MAX_AGE_SECONDS = 900
DEFAULT_WEEK_START = "sunday"
DEFAULT_UNITS = {"distance": "mi", "elevation": "ft"}
DEFAULT_OTHER_BUCKET = "OtherSports"
DEFAULT_HISTORY_START = datetime(1970, 1, 1, tzinfo=timezone.utc)

TYPE_LABEL_OVERRIDES = {
    "HighIntensityIntervalTraining": "HITT",
    "Workout": "Other Workout",
}

TYPE_ACCENT_OVERRIDES = {
    "Run": "#01cdfe",
    "Ride": "#05ffa1",
    "Walk": "#d6ff6b",
    "Hike": "#d6ff6b",
    "WeightTraining": "#ff71ce",
    "Workout": "#ff8a5b",
}

FALLBACK_ACCENTS = [
    "#f15bb5",
    "#fee440",
    "#00bbf9",
    "#00f5d4",
    "#9b5de5",
    "#fb5607",
    "#ffbe0b",
    "#72efdd",
]


def _to_bool(value: object) -> bool:
    normalized = str(value or "").strip().lower()
    return normalized in {"1", "true", "yes", "y", "on"}


def _parse_iso_datetime(raw_value: object) -> datetime | None:
    if not isinstance(raw_value, str):
        return None
    value = raw_value.strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_week_start(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"monday", "mon"}:
        return "monday"
    return DEFAULT_WEEK_START


def _normalize_distance_unit(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"km", "kilometer", "kilometers"}:
        return "km"
    return "mi"


def _normalize_elevation_unit(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"m", "meter", "meters"}:
        return "m"
    return "ft"


def _cache_max_age_seconds() -> int:
    raw = str(os.getenv("DASHBOARD_CACHE_MAX_AGE_SECONDS", DEFAULT_CACHE_MAX_AGE_SECONDS)).strip()
    try:
        value = int(raw)
    except ValueError:
        value = DEFAULT_CACHE_MAX_AGE_SECONDS
    return max(0, value)


def _dashboard_history_start() -> datetime:
    start_date_raw = str(os.getenv("DASHBOARD_START_DATE", "")).strip()
    if start_date_raw:
        try:
            return datetime.strptime(start_date_raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            logger.warning("Invalid DASHBOARD_START_DATE '%s'; expected YYYY-MM-DD.", start_date_raw)

    lookback_raw = str(os.getenv("DASHBOARD_LOOKBACK_YEARS", "")).strip()
    if lookback_raw:
        try:
            lookback_years = max(1, int(lookback_raw))
            now = datetime.now(timezone.utc)
            target_year = max(1970, now.year - lookback_years + 1)
            return datetime(target_year, 1, 1, tzinfo=timezone.utc)
        except ValueError:
            logger.warning("Invalid DASHBOARD_LOOKBACK_YEARS '%s'; expected integer.", lookback_raw)

    return DEFAULT_HISTORY_START


def dashboard_data_path(settings: Settings) -> Path:
    filename = str(os.getenv("DASHBOARD_DATA_FILE", DEFAULT_DASHBOARD_DATA_FILE)).strip() or DEFAULT_DASHBOARD_DATA_FILE
    return settings.state_dir / filename


def _is_payload_fresh(payload: dict[str, Any], *, max_age_seconds: int) -> bool:
    if max_age_seconds <= 0:
        return False
    generated_at = _parse_iso_datetime(payload.get("generated_at"))
    if generated_at is None:
        return False
    age_seconds = (datetime.now(timezone.utc) - generated_at).total_seconds()
    return age_seconds <= max_age_seconds


def _canonical_type(raw_type: object) -> str:
    text = str(raw_type or "").strip()
    if not text:
        return "Workout"
    collapsed = re.sub(r"[^A-Za-z0-9]+", "", text)
    if collapsed:
        return collapsed
    return "Workout"


def _prettify_type(type_name: str) -> str:
    override = TYPE_LABEL_OVERRIDES.get(type_name)
    if override:
        return override
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(type_name or "").strip())
    if not spaced:
        return "Other"
    return spaced[0].upper() + spaced[1:]


def _type_meta(types: list[str]) -> dict[str, dict[str, str]]:
    meta: dict[str, dict[str, str]] = {}
    for idx, type_name in enumerate(types):
        accent = TYPE_ACCENT_OVERRIDES.get(type_name) or FALLBACK_ACCENTS[idx % len(FALLBACK_ACCENTS)]
        meta[type_name] = {
            "label": _prettify_type(type_name),
            "accent": accent,
        }
    return meta


def _activity_url(activity_id: str) -> str:
    return f"https://www.strava.com/activities/{activity_id}"


def _as_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _normalize_activity(item: dict[str, Any]) -> dict[str, Any] | None:
    raw_id = item.get("id")
    if raw_id in {None, ""}:
        return None
    activity_id = str(raw_id).strip()
    if not activity_id:
        return None

    parsed_start = _parse_iso_datetime(item.get("start_date_local")) or _parse_iso_datetime(item.get("start_date"))
    if parsed_start is None:
        return None

    type_name = _canonical_type(item.get("sport_type") or item.get("type"))
    raw_type = str(item.get("sport_type") or item.get("type") or type_name)
    date_key = parsed_start.strftime("%Y-%m-%d")

    normalized: dict[str, Any] = {
        "id": activity_id,
        "date": date_key,
        "year": int(parsed_start.year),
        "type": type_name,
        "raw_type": raw_type,
        "start_date_local": str(item.get("start_date_local") or item.get("start_date") or ""),
        "hour": int(parsed_start.hour),
        "distance": _as_float(item.get("distance")),
        "moving_time": _as_float(item.get("moving_time")),
        "elevation_gain": _as_float(item.get("total_elevation_gain")),
        "url": _activity_url(activity_id),
    }

    name = str(item.get("name") or "").strip()
    if name:
        normalized["name"] = name
    return normalized


def build_dashboard_payload(settings: Settings) -> dict[str, Any]:
    client = StravaClient(settings)
    after_dt = _dashboard_history_start()
    raw_activities = client.get_activities_after(after_dt, per_page=200)

    deduped_by_id: dict[str, dict[str, Any]] = {}
    for raw in raw_activities:
        if not isinstance(raw, dict):
            continue
        normalized = _normalize_activity(raw)
        if normalized is None:
            continue
        deduped_by_id[normalized["id"]] = normalized

    activities = sorted(
        deduped_by_id.values(),
        key=lambda item: (str(item["date"]), str(item["id"])),
    )

    aggregates: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    type_totals: dict[str, int] = defaultdict(int)
    years_seen: set[int] = set()

    for activity in activities:
        year = int(activity["year"])
        years_seen.add(year)
        year_key = str(year)
        type_name = str(activity["type"])
        date_key = str(activity["date"])

        year_bucket = aggregates.setdefault(year_key, {})
        type_bucket = year_bucket.setdefault(type_name, {})
        entry = type_bucket.setdefault(
            date_key,
            {
                "count": 0,
                "distance": 0.0,
                "moving_time": 0.0,
                "elevation_gain": 0.0,
                "activity_ids": [],
            },
        )
        entry["count"] += 1
        entry["distance"] += float(activity["distance"])
        entry["moving_time"] += float(activity["moving_time"])
        entry["elevation_gain"] += float(activity["elevation_gain"])
        entry["activity_ids"].append(str(activity["id"]))
        type_totals[type_name] += 1

    for year_bucket in aggregates.values():
        for type_bucket in year_bucket.values():
            for entry in type_bucket.values():
                entry["activity_ids"] = sorted(set(entry["activity_ids"]))

    types = sorted(type_totals.keys(), key=lambda name: (-type_totals[name], name))

    current_year = datetime.now(timezone.utc).year
    start_year = min(years_seen) if years_seen else current_year
    years = list(range(start_year, current_year + 1))

    week_start = _normalize_week_start(os.getenv("DASHBOARD_WEEK_START", DEFAULT_WEEK_START))
    units = {
        "distance": _normalize_distance_unit(os.getenv("DASHBOARD_DISTANCE_UNIT", DEFAULT_UNITS["distance"])),
        "elevation": _normalize_elevation_unit(os.getenv("DASHBOARD_ELEVATION_UNIT", DEFAULT_UNITS["elevation"])),
    }

    payload: dict[str, Any] = {
        "source": "strava",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "years": years,
        "types": types,
        "other_bucket": DEFAULT_OTHER_BUCKET,
        "type_meta": _type_meta(types),
        "aggregates": aggregates,
        "units": units,
        "week_start": week_start,
        "activities": [
            {
                "date": item["date"],
                "year": item["year"],
                "type": item["type"],
                "raw_type": item["raw_type"],
                "start_date_local": item["start_date_local"],
                "hour": item["hour"],
                "url": item["url"],
                **({"name": item["name"]} if "name" in item else {}),
            }
            for item in activities
        ],
    }

    profile_url = str(os.getenv("DASHBOARD_STRAVA_PROFILE_URL", "")).strip()
    if profile_url:
        payload["profile_url"] = profile_url
        payload["strava_profile_url"] = profile_url

    repo = str(os.getenv("DASHBOARD_REPO") or os.getenv("GITHUB_REPOSITORY") or "").strip()
    if repo and "/" in repo:
        payload["repo"] = repo

    page_cap = MAX_ACTIVITY_PAGES * 200
    if len(raw_activities) >= page_cap:
        payload["history_truncated"] = True

    return payload


def _empty_payload(*, error: str | None = None) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "source": "strava",
        "generated_at": now.isoformat(),
        "years": [now.year],
        "types": [],
        "other_bucket": DEFAULT_OTHER_BUCKET,
        "type_meta": {},
        "aggregates": {},
        "units": dict(DEFAULT_UNITS),
        "week_start": DEFAULT_WEEK_START,
        "activities": [],
    }
    if error:
        payload["error"] = error
    return payload


def get_dashboard_payload(
    settings: Settings,
    *,
    force_refresh: bool = False,
    max_age_seconds: int | None = None,
) -> dict[str, Any]:
    data_path = dashboard_data_path(settings)
    age_limit = _cache_max_age_seconds() if max_age_seconds is None else max(0, int(max_age_seconds))

    cached = read_json(data_path)
    if isinstance(cached, dict) and not force_refresh and _is_payload_fresh(cached, max_age_seconds=age_limit):
        return cached

    try:
        payload = build_dashboard_payload(settings)
    except Exception:
        if isinstance(cached, dict):
            logger.exception("Dashboard rebuild failed; serving stale cached payload.")
            return cached
        logger.exception("Dashboard rebuild failed with no cache; serving empty payload.")
        return _empty_payload(error="dashboard_build_failed")

    write_json(data_path, payload)
    return payload
