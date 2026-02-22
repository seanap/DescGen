from __future__ import annotations

import concurrent.futures
import logging
import os
import re
import threading
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import Settings
from .dashboard_response_modes import apply_dashboard_response_mode, normalize_dashboard_response_mode
from .stat_modules.intervals_data import get_intervals_dashboard_metrics
from .storage import (
    acquire_runtime_lock,
    read_json,
    release_runtime_lock,
    set_runtime_values,
    write_json,
)
from .strava_client import MAX_ACTIVITY_PAGES, StravaClient


logger = logging.getLogger(__name__)

DEFAULT_DASHBOARD_DATA_FILE = "dashboard_data.json"
DEFAULT_INTERVALS_METRICS_FILE = "intervals_dashboard_metrics.json"
DEFAULT_CACHE_MAX_AGE_SECONDS = 900
DEFAULT_WEEK_START = "sunday"
DEFAULT_UNITS = {"distance": "mi", "elevation": "ft"}
DEFAULT_OTHER_BUCKET = "OtherSports"
DEFAULT_HISTORY_START = datetime(1970, 1, 1, tzinfo=timezone.utc)
DEFAULT_REFRESH_LOCK_TTL_SECONDS = 300
DEFAULT_INTERVALS_INCREMENTAL_OVERLAP_HOURS = 48
DEFAULT_STRAVA_INCREMENTAL_OVERLAP_HOURS = 48
INTERVALS_CACHE_SCHEMA_VERSION = 1
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
_PAYLOAD_MEMORY_CACHE_GUARD = threading.Lock()
_PAYLOAD_MEMORY_CACHE: dict[str, dict[str, Any]] = {}


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


def _dashboard_payload_cache_key(data_path: Path) -> str:
    try:
        return str(data_path.resolve())
    except OSError:
        return str(data_path)


def _dashboard_payload_file_marker(data_path: Path) -> tuple[int, int, int, int] | None:
    try:
        stat = data_path.stat()
    except OSError:
        return None
    return int(stat.st_mtime_ns), int(stat.st_size), int(stat.st_ctime_ns), int(stat.st_ino)


def _load_dashboard_payload_cached(data_path: Path) -> dict[str, Any] | None:
    cache_key = _dashboard_payload_cache_key(data_path)
    marker = _dashboard_payload_file_marker(data_path)
    with _PAYLOAD_MEMORY_CACHE_GUARD:
        if marker is None:
            _PAYLOAD_MEMORY_CACHE.pop(cache_key, None)
        else:
            entry = _PAYLOAD_MEMORY_CACHE.get(cache_key)
            if isinstance(entry, dict) and entry.get("marker") == marker:
                payload = entry.get("payload")
                if isinstance(payload, dict):
                    return dict(payload)

    payload = read_json(data_path)
    if not isinstance(payload, dict):
        with _PAYLOAD_MEMORY_CACHE_GUARD:
            _PAYLOAD_MEMORY_CACHE.pop(cache_key, None)
        return None

    current_marker = _dashboard_payload_file_marker(data_path)
    if current_marker is not None:
        with _PAYLOAD_MEMORY_CACHE_GUARD:
            _PAYLOAD_MEMORY_CACHE[cache_key] = {
                "marker": current_marker,
                "payload": dict(payload),
            }
    return payload


def _persist_dashboard_payload_cached(data_path: Path, payload: dict[str, Any]) -> None:
    write_json(data_path, payload)
    cache_key = _dashboard_payload_cache_key(data_path)
    marker = _dashboard_payload_file_marker(data_path)
    with _PAYLOAD_MEMORY_CACHE_GUARD:
        if marker is None:
            _PAYLOAD_MEMORY_CACHE.pop(cache_key, None)
            return
        _PAYLOAD_MEMORY_CACHE[cache_key] = {
            "marker": marker,
            "payload": dict(payload),
        }


def intervals_metrics_cache_path(settings: Settings) -> Path:
    filename = (
        str(os.getenv("DASHBOARD_INTERVALS_METRICS_FILE", DEFAULT_INTERVALS_METRICS_FILE)).strip()
        or DEFAULT_INTERVALS_METRICS_FILE
    )
    return settings.state_dir / filename


def _intervals_incremental_overlap_hours() -> int:
    raw = str(
        os.getenv("DASHBOARD_INTERVALS_INCREMENTAL_OVERLAP_HOURS", DEFAULT_INTERVALS_INCREMENTAL_OVERLAP_HOURS)
    ).strip()
    try:
        value = int(raw)
    except ValueError:
        value = DEFAULT_INTERVALS_INCREMENTAL_OVERLAP_HOURS
    return max(1, min(336, value))


def _strava_incremental_overlap_hours() -> int:
    raw = str(
        os.getenv("DASHBOARD_STRAVA_INCREMENTAL_OVERLAP_HOURS", DEFAULT_STRAVA_INCREMENTAL_OVERLAP_HOURS)
    ).strip()
    try:
        value = int(raw)
    except ValueError:
        value = DEFAULT_STRAVA_INCREMENTAL_OVERLAP_HOURS
    return max(1, min(336, value))


def _as_utc_datetime(value: datetime | str | None, *, fallback: datetime) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    parsed = _parse_iso_datetime(value) if isinstance(value, str) else None
    if parsed is not None:
        return parsed
    return fallback.astimezone(timezone.utc)


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


def _as_optional_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _iso_minute_key(raw_value: object) -> str | None:
    parsed = _parse_iso_datetime(raw_value)
    if parsed is None:
        return None
    return parsed.replace(second=0, microsecond=0).isoformat()


def _index_intervals_metrics(
    records: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_id: dict[str, dict[str, Any]] = {}
    by_minute: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        activity_id = str(record.get("strava_activity_id") or "").strip()
        minute_key = _iso_minute_key(record.get("start_date"))
        if activity_id:
            by_id[activity_id] = record
        if minute_key:
            by_minute[minute_key] = record
    return by_id, by_minute


def _sanitize_intervals_record(record: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(record, dict):
        return None
    activity_id_text = str(record.get("strava_activity_id") or "").strip()
    minute_key = _iso_minute_key(record.get("start_date"))
    start_date_raw = str(record.get("start_date") or "").strip()
    pace = _as_optional_float(record.get("avg_pace_mps"))
    efficiency = _as_optional_float(record.get("avg_efficiency_factor"))
    fitness = _as_optional_float(record.get("avg_fitness"))
    fatigue = _as_optional_float(record.get("avg_fatigue"))
    moving_time_seconds = _as_optional_float(record.get("moving_time_seconds"))
    if (
        pace is None
        and efficiency is None
        and fitness is None
        and fatigue is None
    ):
        return None
    if not activity_id_text and not minute_key:
        return None
    sanitized: dict[str, Any] = {
        "strava_activity_id": activity_id_text or None,
        "start_date": start_date_raw or (minute_key or ""),
    }
    if pace is not None and pace > 0:
        sanitized["avg_pace_mps"] = pace
    if efficiency is not None and efficiency > 0:
        sanitized["avg_efficiency_factor"] = efficiency
    if fitness is not None:
        sanitized["avg_fitness"] = fitness
    if fatigue is not None:
        sanitized["avg_fatigue"] = fatigue
    if moving_time_seconds is not None and moving_time_seconds > 0:
        sanitized["moving_time_seconds"] = moving_time_seconds
    return sanitized


def _intervals_record_cache_key(record: dict[str, Any]) -> str | None:
    activity_id = str(record.get("strava_activity_id") or "").strip()
    if activity_id:
        return f"id:{activity_id}"
    minute_key = _iso_minute_key(record.get("start_date"))
    if minute_key:
        return f"minute:{minute_key}"
    return None


def _merge_intervals_records(
    base_records: list[dict[str, Any]],
    incoming_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for record in [*base_records, *incoming_records]:
        sanitized = _sanitize_intervals_record(record)
        if sanitized is None:
            continue
        key = _intervals_record_cache_key(sanitized)
        if not key:
            continue
        merged[key] = sanitized
    return list(merged.values())


def _load_intervals_cache_records(
    cache_payload: dict[str, Any] | None,
    *,
    history_start: datetime,
) -> tuple[list[dict[str, Any]], datetime | None]:
    if not isinstance(cache_payload, dict):
        return ([], None)
    schema_version = int(cache_payload.get("schema_version") or 0)
    cached_history_start = _as_utc_datetime(
        cache_payload.get("history_start"),
        fallback=history_start,
    )
    if schema_version != INTERVALS_CACHE_SCHEMA_VERSION or cached_history_start != history_start:
        return ([], None)
    raw_records = cache_payload.get("records")
    records = raw_records if isinstance(raw_records, list) else []
    latest_sync_at = _parse_iso_datetime(cache_payload.get("latest_sync_at"))
    return (_merge_intervals_records([], records), latest_sync_at)


def _persist_intervals_cache_records(
    path: Path,
    *,
    history_start: datetime,
    latest_sync_at: datetime,
    last_fetch_oldest: datetime,
    mode: str,
    records: list[dict[str, Any]],
) -> None:
    payload = {
        "schema_version": INTERVALS_CACHE_SCHEMA_VERSION,
        "history_start": history_start.isoformat(),
        "latest_sync_at": latest_sync_at.isoformat(),
        "last_fetch_oldest": last_fetch_oldest.isoformat(),
        "last_fetch_mode": mode,
        "records": records,
    }
    write_json(path, payload)


def _get_intervals_records_incremental(
    settings: Settings,
    *,
    oldest: datetime | str | None,
    newest: datetime | str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    now_utc = datetime.now(timezone.utc)
    newest_dt = _as_utc_datetime(newest, fallback=now_utc)
    oldest_dt = _as_utc_datetime(oldest, fallback=DEFAULT_HISTORY_START)
    if oldest_dt > newest_dt:
        oldest_dt = newest_dt

    cache_path = intervals_metrics_cache_path(settings)
    cached_payload = read_json(cache_path)
    cached_records, last_sync_at = _load_intervals_cache_records(cached_payload, history_start=oldest_dt)
    mode = "incremental" if cached_records else "seed"

    current_year_start = datetime(newest_dt.year, 1, 1, tzinfo=timezone.utc)
    overlap = timedelta(hours=_intervals_incremental_overlap_hours())
    if mode == "seed":
        fetch_oldest = oldest_dt
    else:
        fetch_oldest = current_year_start
        if last_sync_at is not None:
            overlap_start = last_sync_at - overlap
            if overlap_start > fetch_oldest:
                fetch_oldest = overlap_start
        if fetch_oldest < oldest_dt:
            fetch_oldest = oldest_dt

    incoming = get_intervals_dashboard_metrics(
        settings.intervals_user_id,
        settings.intervals_api_key,
        oldest=fetch_oldest,
        newest=newest_dt,
    )
    merged_records = _merge_intervals_records(cached_records, incoming)
    _persist_intervals_cache_records(
        cache_path,
        history_start=oldest_dt,
        latest_sync_at=newest_dt,
        last_fetch_oldest=fetch_oldest,
        mode=mode,
        records=merged_records,
    )
    return (
        merged_records,
        {
            "mode": mode,
            "fetched_records": int(len(incoming)),
            "cached_records": int(len(merged_records)),
            "fetch_oldest": fetch_oldest.isoformat(),
            "latest_sync_at": newest_dt.isoformat(),
        },
    )


def _new_intervals_rollup() -> dict[str, float]:
    return {
        "_eff_weighted_sum": 0.0,
        "_eff_weight_seconds": 0.0,
        "_fitness_sum": 0.0,
        "_fitness_count": 0.0,
        "_fatigue_sum": 0.0,
        "_fatigue_count": 0.0,
    }


def _accumulate_intervals_rollup(
    rollup: dict[str, Any],
    *,
    efficiency: float | None,
    fitness: float | None,
    fatigue: float | None,
    weight_seconds: float,
) -> None:
    if efficiency is not None and efficiency > 0 and weight_seconds > 0:
        rollup["_eff_weighted_sum"] += efficiency * weight_seconds
        rollup["_eff_weight_seconds"] += weight_seconds
    if fitness is not None:
        rollup["_fitness_sum"] += fitness
        rollup["_fitness_count"] += 1
    if fatigue is not None:
        rollup["_fatigue_sum"] += fatigue
        rollup["_fatigue_count"] += 1


def _finalize_intervals_rollup(rollup: dict[str, Any]) -> None:
    eff_weight = _as_optional_float(rollup.get("_eff_weight_seconds")) or 0.0
    if eff_weight > 0:
        rollup["avg_efficiency_factor"] = (float(rollup.get("_eff_weighted_sum") or 0.0) / eff_weight)
    fitness_count = _as_optional_float(rollup.get("_fitness_count")) or 0.0
    if fitness_count > 0:
        rollup["avg_fitness"] = float(rollup.get("_fitness_sum") or 0.0) / fitness_count
    fatigue_count = _as_optional_float(rollup.get("_fatigue_count")) or 0.0
    if fatigue_count > 0:
        rollup["avg_fatigue"] = float(rollup.get("_fatigue_sum") or 0.0) / fatigue_count

    for key in (
        "_eff_weighted_sum",
        "_eff_weight_seconds",
        "_fitness_sum",
        "_fitness_count",
        "_fatigue_sum",
        "_fatigue_count",
    ):
        rollup.pop(key, None)


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
        "_start_minute_key": parsed_start.replace(second=0, microsecond=0).isoformat(),
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


def _activity_id_from_url(url: object) -> str | None:
    text = str(url or "").strip()
    if not text:
        return None
    match = re.search(r"/activities/(\d+)$", text)
    if not match:
        return None
    return match.group(1)


def _normalize_cached_activity(item: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    raw_id = item.get("id")
    activity_id = str(raw_id).strip() if raw_id not in {None, ""} else ""
    if not activity_id:
        activity_id = str(_activity_id_from_url(item.get("url")) or "").strip()
    if not activity_id:
        return None

    parsed_start = _parse_iso_datetime(item.get("start_date_local"))
    if parsed_start is None:
        return None

    type_name = _canonical_type(item.get("type") or item.get("raw_type"))
    raw_type = str(item.get("raw_type") or item.get("type") or type_name)
    normalized: dict[str, Any] = {
        "id": activity_id,
        "date": parsed_start.strftime("%Y-%m-%d"),
        "year": int(parsed_start.year),
        "type": type_name,
        "raw_type": raw_type,
        "start_date_local": str(item.get("start_date_local") or ""),
        "_start_minute_key": parsed_start.replace(second=0, microsecond=0).isoformat(),
        "hour": int(item.get("hour")) if isinstance(item.get("hour"), int) else int(parsed_start.hour),
        "distance": _as_float(item.get("distance")),
        "moving_time": _as_float(item.get("moving_time")),
        "elevation_gain": _as_float(item.get("elevation_gain")),
        "url": str(item.get("url") or _activity_url(activity_id)),
    }
    name = str(item.get("name") or "").strip()
    if name:
        normalized["name"] = name
    for metric_key in ("avg_pace_mps", "avg_efficiency_factor", "avg_fitness", "avg_fatigue"):
        metric_value = _as_optional_float(item.get(metric_key))
        if metric_value is not None:
            normalized[metric_key] = metric_value
    moving_time_seconds = _as_optional_float(item.get("_intervals_moving_time_seconds"))
    if moving_time_seconds is not None and moving_time_seconds > 0:
        normalized["_intervals_moving_time_seconds"] = moving_time_seconds
    return normalized


def _cached_activities_support_incremental(cached_payload: dict[str, Any]) -> bool:
    activities_raw = cached_payload.get("activities")
    if not isinstance(activities_raw, list):
        return False
    if not activities_raw:
        return True
    first = activities_raw[0]
    if not isinstance(first, dict):
        return False
    required = {"start_date_local", "distance", "moving_time", "elevation_gain"}
    return required.issubset(first.keys())


def _normalized_activities_from_payload(cached_payload: dict[str, Any]) -> list[dict[str, Any]] | None:
    if not _cached_activities_support_incremental(cached_payload):
        return None
    activities_raw = cached_payload.get("activities")
    if not isinstance(activities_raw, list):
        return None
    deduped_by_id: dict[str, dict[str, Any]] = {}
    for item in activities_raw:
        normalized = _normalize_cached_activity(item) if isinstance(item, dict) else None
        if normalized is None:
            return None
        deduped_by_id[normalized["id"]] = normalized
    return sorted(
        deduped_by_id.values(),
        key=lambda value: (str(value["date"]), str(value["id"])),
    )


def _build_payload_from_activities(
    settings: Settings,
    activities: list[dict[str, Any]],
    *,
    marker: tuple[str | None, str | None],
    history_truncated: bool = False,
) -> dict[str, Any]:
    activities_copy = [dict(item) for item in activities]

    intervals_records: list[dict[str, Any]] = []
    intervals_sync: dict[str, Any] = {}
    intervals_matches = 0
    after_dt = _dashboard_history_start()
    if (
        settings.enable_intervals
        and isinstance(settings.intervals_user_id, str)
        and settings.intervals_user_id.strip()
        and isinstance(settings.intervals_api_key, str)
        and settings.intervals_api_key.strip()
    ):
        intervals_records, intervals_sync = _get_intervals_records_incremental(
            settings,
            oldest=after_dt,
            newest=datetime.now(timezone.utc),
        )
    intervals_by_id, intervals_by_minute = _index_intervals_metrics(intervals_records)
    if intervals_by_id or intervals_by_minute:
        for activity in activities_copy:
            matched = intervals_by_id.get(str(activity["id"])) or intervals_by_minute.get(
                str(activity.get("_start_minute_key") or "")
            )
            if not isinstance(matched, dict):
                continue
            efficiency = _as_optional_float(matched.get("avg_efficiency_factor"))
            fitness = _as_optional_float(matched.get("avg_fitness"))
            fatigue = _as_optional_float(matched.get("avg_fatigue"))
            moving_time_seconds = _as_optional_float(matched.get("moving_time_seconds"))
            if (
                efficiency is None
                and fitness is None
                and fatigue is None
            ):
                continue
            intervals_matches += 1
            if efficiency is not None and efficiency > 0:
                activity["avg_efficiency_factor"] = efficiency
            if fitness is not None:
                activity["avg_fitness"] = fitness
            if fatigue is not None:
                activity["avg_fatigue"] = fatigue
            if moving_time_seconds is not None and moving_time_seconds > 0:
                activity["_intervals_moving_time_seconds"] = moving_time_seconds

    aggregates: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    intervals_year_type_metrics: dict[str, dict[str, dict[str, Any]]] = {}
    type_totals: dict[str, int] = defaultdict(int)
    years_seen: set[int] = set()

    for activity in activities_copy:
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
                **_new_intervals_rollup(),
            },
        )
        entry["count"] += 1
        entry["distance"] += float(activity["distance"])
        entry["moving_time"] += float(activity["moving_time"])
        entry["elevation_gain"] += float(activity["elevation_gain"])
        entry["activity_ids"].append(str(activity["id"]))
        type_totals[type_name] += 1

        year_intervals_bucket = intervals_year_type_metrics.setdefault(year_key, {})
        type_intervals_totals = year_intervals_bucket.setdefault(type_name, _new_intervals_rollup())
        weight_seconds = (
            _as_optional_float(activity.get("_intervals_moving_time_seconds"))
            or _as_optional_float(activity.get("moving_time"))
            or 0.0
        )
        _accumulate_intervals_rollup(
            entry,
            efficiency=_as_optional_float(activity.get("avg_efficiency_factor")),
            fitness=_as_optional_float(activity.get("avg_fitness")),
            fatigue=_as_optional_float(activity.get("avg_fatigue")),
            weight_seconds=weight_seconds,
        )
        _accumulate_intervals_rollup(
            type_intervals_totals,
            efficiency=_as_optional_float(activity.get("avg_efficiency_factor")),
            fitness=_as_optional_float(activity.get("avg_fitness")),
            fatigue=_as_optional_float(activity.get("avg_fatigue")),
            weight_seconds=weight_seconds,
        )

    for year_bucket in aggregates.values():
        for type_bucket in year_bucket.values():
            for entry in type_bucket.values():
                entry["activity_ids"] = sorted(set(entry["activity_ids"]))
                moving_time_total = float(entry.get("moving_time") or 0.0)
                distance_total = float(entry.get("distance") or 0.0)
                if moving_time_total > 0 and distance_total > 0:
                    entry["avg_pace_mps"] = distance_total / moving_time_total
                _finalize_intervals_rollup(entry)

    for year_bucket in intervals_year_type_metrics.values():
        for totals_entry in year_bucket.values():
            _finalize_intervals_rollup(totals_entry)

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
                "id": item["id"],
                "date": item["date"],
                "year": item["year"],
                "type": item["type"],
                "raw_type": item["raw_type"],
                "start_date_local": item["start_date_local"],
                "hour": item["hour"],
                "distance": float(item.get("distance") or 0.0),
                "moving_time": float(item.get("moving_time") or 0.0),
                "elevation_gain": float(item.get("elevation_gain") or 0.0),
                "url": item["url"],
                **({"name": item["name"]} if "name" in item else {}),
                **({"avg_pace_mps": item["avg_pace_mps"]} if "avg_pace_mps" in item else {}),
                **(
                    {"avg_efficiency_factor": item["avg_efficiency_factor"]}
                    if "avg_efficiency_factor" in item
                    else {}
                ),
                **({"avg_fitness": item["avg_fitness"]} if "avg_fitness" in item else {}),
                **({"avg_fatigue": item["avg_fatigue"]} if "avg_fatigue" in item else {}),
                **(
                    {"_intervals_moving_time_seconds": item["_intervals_moving_time_seconds"]}
                    if "_intervals_moving_time_seconds" in item
                    else {}
                ),
            }
            for item in activities_copy
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

    if history_truncated:
        payload["history_truncated"] = True

    payload["intervals"] = {
        "enabled": bool(settings.enable_intervals),
        "records": int(len(intervals_records)),
        "matched_activities": int(intervals_matches),
        **({"sync_mode": intervals_sync.get("mode")} if intervals_sync.get("mode") else {}),
        **(
            {"fetched_records": int(intervals_sync.get("fetched_records") or 0)}
            if "fetched_records" in intervals_sync
            else {}
        ),
        **(
            {"cached_records": int(intervals_sync.get("cached_records") or 0)}
            if "cached_records" in intervals_sync
            else {}
        ),
        **({"fetch_oldest": intervals_sync.get("fetch_oldest")} if intervals_sync.get("fetch_oldest") else {}),
        **({"latest_sync_at": intervals_sync.get("latest_sync_at")} if intervals_sync.get("latest_sync_at") else {}),
    }
    payload["intervals_year_type_metrics"] = intervals_year_type_metrics

    return payload


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
    page_cap = MAX_ACTIVITY_PAGES * 200
    return _build_payload_from_activities(
        settings,
        activities,
        marker=marker,
        history_truncated=len(raw_activities) >= page_cap,
    )


def _build_incremental_payload_from_cache(
    settings: Settings,
    cached_payload: dict[str, Any],
    *,
    latest_marker: tuple[str | None, str | None],
) -> dict[str, Any] | None:
    cached_activities = _normalized_activities_from_payload(cached_payload)
    if cached_activities is None:
        return None

    latest_id, latest_start = latest_marker
    latest_start_dt = _parse_iso_datetime(latest_start)
    if latest_start_dt is None:
        return None

    history_start = _dashboard_history_start()
    overlap = timedelta(hours=_strava_incremental_overlap_hours())
    fetch_after = latest_start_dt - overlap
    if fetch_after < history_start:
        fetch_after = history_start

    client = StravaClient(settings)
    raw_recent = client.get_activities_after(fetch_after, per_page=200)
    deduped_by_id: dict[str, dict[str, Any]] = {item["id"]: item for item in cached_activities}
    for raw in raw_recent:
        if not isinstance(raw, dict):
            continue
        normalized = _normalize_activity(raw)
        if normalized is None:
            continue
        deduped_by_id[normalized["id"]] = normalized

    if latest_id and latest_id not in deduped_by_id:
        return None

    merged_activities = sorted(
        deduped_by_id.values(),
        key=lambda value: (str(value["date"]), str(value["id"])),
    )
    history_truncated = bool(cached_payload.get("history_truncated"))
    payload = _build_payload_from_activities(
        settings,
        merged_activities,
        marker=latest_marker,
        history_truncated=history_truncated,
    )
    payload["sync_mode"] = "incremental"
    payload["sync_fetch_after"] = fetch_after.isoformat()
    payload["sync_fetched_records"] = int(len(raw_recent))
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
        "intervals": {
            "enabled": False,
            "records": 0,
            "matched_activities": 0,
        },
        "intervals_year_type_metrics": {},
    }
    if error:
        payload["error"] = error
    return payload


def _normalize_dashboard_payload(payload: dict[str, Any], settings: Settings) -> dict[str, Any]:
    normalized = dict(payload)

    types_raw = normalized.get("types")
    types: list[str] = []
    if isinstance(types_raw, list):
        for item in types_raw:
            if not isinstance(item, str):
                continue
            cleaned = item.strip()
            if cleaned and cleaned not in types:
                types.append(cleaned)
    normalized["types"] = types

    type_meta_raw = normalized.get("type_meta")
    incoming_type_meta = type_meta_raw if isinstance(type_meta_raw, dict) else {}
    canonical_type_meta = _type_meta(types)
    normalized_type_meta: dict[str, dict[str, Any]] = {}
    for type_name in types:
        incoming_meta = incoming_type_meta.get(type_name)
        incoming_meta_dict = incoming_meta if isinstance(incoming_meta, dict) else {}
        canonical_meta = canonical_type_meta.get(type_name, {"label": _prettify_type(type_name), "accent": "#3fa8ff"})
        label = incoming_meta_dict.get("label")
        accent = incoming_meta_dict.get("accent")
        normalized_entry: dict[str, Any] = dict(incoming_meta_dict)
        normalized_entry["label"] = str(label).strip() if isinstance(label, str) and label.strip() else canonical_meta["label"]
        normalized_entry["accent"] = str(accent).strip() if isinstance(accent, str) and accent.strip() else canonical_meta["accent"]
        normalized_type_meta[type_name] = normalized_entry
    normalized["type_meta"] = normalized_type_meta

    intervals_raw = normalized.get("intervals")
    intervals = dict(intervals_raw) if isinstance(intervals_raw, dict) else {}
    intervals["enabled"] = bool(settings.enable_intervals)
    intervals.setdefault("records", 0)
    intervals.setdefault("matched_activities", 0)
    normalized["intervals"] = intervals
    intervals_year_type_metrics = normalized.get("intervals_year_type_metrics")
    normalized["intervals_year_type_metrics"] = (
        intervals_year_type_metrics if isinstance(intervals_year_type_metrics, dict) else {}
    )
    return normalized


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
    payload = _normalize_dashboard_payload(build_dashboard_payload(settings, latest_marker=latest_marker), settings)
    _persist_dashboard_payload_cached(data_path, payload)
    return payload


def _smart_revalidate_payload(settings: Settings, data_path: Path, cached_payload: dict[str, Any]) -> dict[str, Any]:
    latest_marker = _fetch_latest_activity_marker(settings)
    if _cache_is_current_for_latest_activity(cached_payload, latest_marker):
        touched = _touch_cached_payload_validation(cached_payload, latest_marker)
        _persist_dashboard_payload_cached(data_path, touched)
        return touched
    incremental = _build_incremental_payload_from_cache(
        settings,
        cached_payload,
        latest_marker=latest_marker,
    )
    if isinstance(incremental, dict):
        _persist_dashboard_payload_cached(data_path, incremental)
        return incremental
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
        cached = _load_dashboard_payload_cached(data_path)
        set_runtime_values(
            settings.processed_log_file,
            {
                "dashboard.refresh.state": "running",
                "dashboard.refresh.reason": reason,
                "dashboard.refresh.started_at_utc": _now_iso(),
            },
        )

        if isinstance(cached, dict):
            refreshed = _smart_revalidate_payload(settings, data_path, cached)
            latest_id, _latest_start = _payload_latest_marker(refreshed)
            set_runtime_values(
                settings.processed_log_file,
                {
                    "dashboard.refresh.result": (
                        "validated_unchanged" if latest_id and latest_id == _payload_latest_marker(cached)[0] else "rebuilt"
                    )
                },
            )
        else:
            _build_and_persist_payload(settings, data_path)
            set_runtime_values(settings.processed_log_file, {"dashboard.refresh.result": "rebuilt"})
        set_runtime_values(
            settings.processed_log_file,
            {
                "dashboard.refresh.last_success_at_utc": _now_iso(),
                "dashboard.refresh.last_error": "",
            },
        )
    except Exception as exc:
        set_runtime_values(
            settings.processed_log_file,
            {
                "dashboard.refresh.last_error": str(exc),
                "dashboard.refresh.last_error_at_utc": _now_iso(),
            },
        )
        logger.warning("Background dashboard refresh failed (%s): %s", reason, exc)
    finally:
        set_runtime_values(
            settings.processed_log_file,
            {
                "dashboard.refresh.state": "idle",
                "dashboard.refresh.finished_at_utc": _now_iso(),
            },
        )
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
    cached = _load_dashboard_payload_cached(data_path)
    if isinstance(cached, dict):
        return _normalize_dashboard_payload(cached, settings)
    try:
        return _build_and_persist_payload(settings, data_path)
    except Exception:
        logger.exception("Dashboard warmup failed; serving empty payload.")
        return _normalize_dashboard_payload(_empty_payload(error="dashboard_warmup_failed"), settings)


def get_dashboard_payload(
    settings: Settings,
    *,
    force_refresh: bool = False,
    max_age_seconds: int | None = None,
    allow_async_refresh: bool = True,
    response_mode: str = "full",
    response_year: int | str | None = None,
) -> dict[str, Any]:
    data_path = dashboard_data_path(settings)
    age_limit = _cache_max_age_seconds() if max_age_seconds is None else max(0, int(max_age_seconds))
    mode = normalize_dashboard_response_mode(response_mode)

    cached = _load_dashboard_payload_cached(data_path)
    if force_refresh:
        try:
            rebuilt = _build_and_persist_payload(settings, data_path)
            return apply_dashboard_response_mode(
                _normalize_dashboard_payload(rebuilt, settings),
                response_mode=mode,
                response_year=response_year,
            )
        except Exception:
            if isinstance(cached, dict):
                logger.exception("Forced dashboard rebuild failed; serving stale cached payload.")
                return apply_dashboard_response_mode(
                    _normalize_dashboard_payload(cached, settings),
                    response_mode=mode,
                    response_year=response_year,
                )
            logger.exception("Forced dashboard rebuild failed with no cache; serving empty payload.")
            return apply_dashboard_response_mode(
                _normalize_dashboard_payload(_empty_payload(error="dashboard_build_failed"), settings),
                response_mode=mode,
                response_year=response_year,
            )

    if isinstance(cached, dict):
        if _is_payload_fresh(cached, max_age_seconds=age_limit):
            return apply_dashboard_response_mode(
                _normalize_dashboard_payload(cached, settings),
                response_mode=mode,
                response_year=response_year,
            )
        revalidating = _schedule_background_refresh(settings, reason="stale_cached_request") if allow_async_refresh else False
        stale_response = dict(cached)
        stale_response["cache_state"] = "stale_revalidating" if revalidating else "stale"
        stale_response["revalidating"] = revalidating
        return apply_dashboard_response_mode(
            _normalize_dashboard_payload(stale_response, settings),
            response_mode=mode,
            response_year=response_year,
        )

    try:
        rebuilt = _build_and_persist_payload(settings, data_path)
        return apply_dashboard_response_mode(
            _normalize_dashboard_payload(rebuilt, settings),
            response_mode=mode,
            response_year=response_year,
        )
    except Exception:
        if isinstance(cached, dict):
            logger.exception("Dashboard rebuild failed; serving stale cached payload.")
            return apply_dashboard_response_mode(
                _normalize_dashboard_payload(cached, settings),
                response_mode=mode,
                response_year=response_year,
            )
        logger.exception("Dashboard rebuild failed with no cache; serving empty payload.")
        return apply_dashboard_response_mode(
            _normalize_dashboard_payload(_empty_payload(error="dashboard_build_failed"), settings),
            response_mode=mode,
            response_year=response_year,
        )
