from __future__ import annotations

import concurrent.futures
import logging
import os
import re
import threading
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Settings
from .storage import (
    acquire_runtime_lock,
    read_json,
    release_runtime_lock,
    set_runtime_value,
    write_json,
)
from .strava_client import MAX_ACTIVITY_PAGES, StravaClient


logger = logging.getLogger(__name__)

DEFAULT_DASHBOARD_DATA_FILE = "dashboard_data.json"
DEFAULT_CACHE_MAX_AGE_SECONDS = 900
DEFAULT_WEEK_START = "sunday"
DEFAULT_UNITS = {"distance": "mi", "elevation": "ft"}
DEFAULT_OTHER_BUCKET = "OtherSports"
DEFAULT_HISTORY_START = datetime(1970, 1, 1, tzinfo=timezone.utc)
DEFAULT_REFRESH_LOCK_TTL_SECONDS = 300
REFRESH_LOCK_NAME = "dashboard.refresh"

TYPE_LABEL_OVERRIDES = {
    "HighIntensityIntervalTraining": "HITT",
    "Workout": "Other Workout",
}

TYPE_ACCENT_OVERRIDES = {
    "Run": "#3fa8ff",
    "Ride": "#39d98a",
    "Walk": "#ffd166",
    "Hike": "#8ecae6",
    "WeightTraining": "#b392f0",
    "Workout": "#ff7aa2",
}

FALLBACK_ACCENTS = [
    "#3fa8ff",
    "#39d98a",
    "#ffd166",
    "#b392f0",
    "#ff7aa2",
    "#7bdff2",
    "#95d5b2",
    "#cdb4db",
]

_REFRESH_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="dashboard-refresh")
_REFRESH_FUTURE: concurrent.futures.Future | None = None
_REFRESH_GUARD = threading.Lock()


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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _payload_latest_marker(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    latest_id_raw = payload.get("latest_activity_id")
    latest_date_raw = payload.get("latest_activity_start_date")
    latest_id = str(latest_id_raw).strip() if latest_id_raw is not None else ""
    latest_date = str(latest_date_raw).strip() if latest_date_raw is not None else ""
    return (latest_id or None, latest_date or None)


def _fetch_latest_activity_marker(settings: Settings) -> tuple[str | None, str | None]:
    client = StravaClient(settings)
    activities = client.get_recent_activities(per_page=1)
    if not activities:
        return (None, None)
    first = activities[0] if isinstance(activities[0], dict) else {}
    latest_id_raw = first.get("id")
    latest_id = str(latest_id_raw).strip() if latest_id_raw is not None else ""
    latest_start_raw = first.get("start_date") or first.get("start_date_local")
    latest_start = str(latest_start_raw).strip() if latest_start_raw is not None else ""
    return (latest_id or None, latest_start or None)


def _cache_is_current_for_latest_activity(cached_payload: dict[str, Any], marker: tuple[str | None, str | None]) -> bool:
    cached_marker = _payload_latest_marker(cached_payload)
    marker_id, _marker_start = marker
    cached_id, _cached_start = cached_marker
    return bool(marker_id and cached_id and marker_id == cached_id)


def _touch_cached_payload_validation(
    cached_payload: dict[str, Any],
    marker: tuple[str | None, str | None] | None = None,
) -> dict[str, Any]:
    payload = dict(cached_payload)
    payload["validated_at"] = _now_iso()
    marker_value = marker if marker is not None else _payload_latest_marker(payload)
    latest_id, latest_start = marker_value
    if latest_id:
        payload["latest_activity_id"] = latest_id
    if latest_start:
        payload["latest_activity_start_date"] = latest_start
    return payload


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
    freshness_anchor = _parse_iso_datetime(payload.get("validated_at")) or _parse_iso_datetime(
        payload.get("generated_at")
    )
    if freshness_anchor is None:
        return False
    age_seconds = (datetime.now(timezone.utc) - freshness_anchor).total_seconds()
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


def build_dashboard_payload(
    settings: Settings,
    *,
    latest_marker: tuple[str | None, str | None] | None = None,
) -> dict[str, Any]:
    client = StravaClient(settings)
    after_dt = _dashboard_history_start()
    raw_activities = client.get_activities_after(after_dt, per_page=200)
    marker = latest_marker
    if marker is None:
        derived_id: str | None = None
        derived_start: str | None = None
        if raw_activities and isinstance(raw_activities[0], dict):
            first = raw_activities[0]
            raw_id = first.get("id")
            derived_id = str(raw_id).strip() if raw_id is not None else None
            raw_start = first.get("start_date") or first.get("start_date_local")
            derived_start = str(raw_start).strip() if raw_start is not None else None
        marker = (derived_id or None, derived_start or None)
        if marker == (None, None):
            marker = _fetch_latest_activity_marker(settings)

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

    generated_at_iso = _now_iso()
    payload: dict[str, Any] = {
        "source": "strava",
        "generated_at": generated_at_iso,
        "validated_at": generated_at_iso,
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

    latest_activity_id, latest_activity_start_date = marker
    if latest_activity_id:
        payload["latest_activity_id"] = latest_activity_id
    if latest_activity_start_date:
        payload["latest_activity_start_date"] = latest_activity_start_date

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
    now_iso = now.isoformat()
    payload: dict[str, Any] = {
        "source": "strava",
        "generated_at": now_iso,
        "validated_at": now_iso,
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


def _refresh_lock_ttl_seconds() -> int:
    raw = str(os.getenv("DASHBOARD_REFRESH_LOCK_TTL_SECONDS", DEFAULT_REFRESH_LOCK_TTL_SECONDS)).strip()
    try:
        ttl = int(raw)
    except ValueError:
        ttl = DEFAULT_REFRESH_LOCK_TTL_SECONDS
    return max(30, ttl)


def _build_and_persist_payload(
    settings: Settings,
    data_path: Path,
    *,
    latest_marker: tuple[str | None, str | None] | None = None,
) -> dict[str, Any]:
    payload = build_dashboard_payload(settings, latest_marker=latest_marker)
    write_json(data_path, payload)
    return payload


def _smart_revalidate_payload(settings: Settings, data_path: Path, cached_payload: dict[str, Any]) -> dict[str, Any]:
    latest_marker = _fetch_latest_activity_marker(settings)
    if _cache_is_current_for_latest_activity(cached_payload, latest_marker):
        touched = _touch_cached_payload_validation(cached_payload, latest_marker)
        write_json(data_path, touched)
        return touched
    return _build_and_persist_payload(settings, data_path, latest_marker=latest_marker)


def _run_background_refresh(settings: Settings, *, reason: str) -> None:
    owner = f"dashboard-refresh:{uuid.uuid4().hex}"
    lock_ttl = _refresh_lock_ttl_seconds()
    lock_acquired = acquire_runtime_lock(
        settings.processed_log_file,
        lock_name=REFRESH_LOCK_NAME,
        owner=owner,
        ttl_seconds=lock_ttl,
    )
    if not lock_acquired:
        return

    try:
        data_path = dashboard_data_path(settings)
        cached = read_json(data_path)
        set_runtime_value(settings.processed_log_file, "dashboard.refresh.state", "running")
        set_runtime_value(settings.processed_log_file, "dashboard.refresh.reason", reason)
        set_runtime_value(settings.processed_log_file, "dashboard.refresh.started_at_utc", _now_iso())

        if isinstance(cached, dict):
            refreshed = _smart_revalidate_payload(settings, data_path, cached)
            latest_id, _latest_start = _payload_latest_marker(refreshed)
            set_runtime_value(
                settings.processed_log_file,
                "dashboard.refresh.result",
                "validated_unchanged" if latest_id and latest_id == _payload_latest_marker(cached)[0] else "rebuilt",
            )
        else:
            _build_and_persist_payload(settings, data_path)
            set_runtime_value(settings.processed_log_file, "dashboard.refresh.result", "rebuilt")
        set_runtime_value(settings.processed_log_file, "dashboard.refresh.last_success_at_utc", _now_iso())
        set_runtime_value(settings.processed_log_file, "dashboard.refresh.last_error", "")
    except Exception as exc:
        set_runtime_value(settings.processed_log_file, "dashboard.refresh.last_error", str(exc))
        set_runtime_value(settings.processed_log_file, "dashboard.refresh.last_error_at_utc", _now_iso())
        logger.warning("Background dashboard refresh failed (%s): %s", reason, exc)
    finally:
        set_runtime_value(settings.processed_log_file, "dashboard.refresh.state", "idle")
        set_runtime_value(settings.processed_log_file, "dashboard.refresh.finished_at_utc", _now_iso())
        release_runtime_lock(
            settings.processed_log_file,
            lock_name=REFRESH_LOCK_NAME,
            owner=owner,
        )


def _schedule_background_refresh(settings: Settings, *, reason: str) -> bool:
    global _REFRESH_FUTURE
    with _REFRESH_GUARD:
        if _REFRESH_FUTURE is not None and not _REFRESH_FUTURE.done():
            return False
        _REFRESH_FUTURE = _REFRESH_EXECUTOR.submit(_run_background_refresh, settings, reason=reason)
    return True


def ensure_dashboard_cache_warm(settings: Settings) -> dict[str, Any]:
    data_path = dashboard_data_path(settings)
    cached = read_json(data_path)
    if isinstance(cached, dict):
        return cached
    try:
        return _build_and_persist_payload(settings, data_path)
    except Exception:
        logger.exception("Dashboard warmup failed; serving empty payload.")
        return _empty_payload(error="dashboard_warmup_failed")


def get_dashboard_payload(
    settings: Settings,
    *,
    force_refresh: bool = False,
    max_age_seconds: int | None = None,
    allow_async_refresh: bool = True,
) -> dict[str, Any]:
    data_path = dashboard_data_path(settings)
    age_limit = _cache_max_age_seconds() if max_age_seconds is None else max(0, int(max_age_seconds))

    cached = read_json(data_path)
    if force_refresh:
        try:
            return _build_and_persist_payload(settings, data_path)
        except Exception:
            if isinstance(cached, dict):
                logger.exception("Forced dashboard rebuild failed; serving stale cached payload.")
                return cached
            logger.exception("Forced dashboard rebuild failed with no cache; serving empty payload.")
            return _empty_payload(error="dashboard_build_failed")

    if isinstance(cached, dict):
        if _is_payload_fresh(cached, max_age_seconds=age_limit):
            return cached
        revalidating = _schedule_background_refresh(settings, reason="stale_cached_request") if allow_async_refresh else False
        stale_response = dict(cached)
        stale_response["cache_state"] = "stale_revalidating" if revalidating else "stale"
        stale_response["revalidating"] = revalidating
        return stale_response

    try:
        return _build_and_persist_payload(settings, data_path)
    except Exception:
        if isinstance(cached, dict):
            logger.exception("Dashboard rebuild failed; serving stale cached payload.")
            return cached
        logger.exception("Dashboard rebuild failed with no cache; serving empty payload.")
        return _empty_payload(error="dashboard_build_failed")
