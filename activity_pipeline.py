from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import time
import uuid
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config import Settings
from numeric_utils import (
    as_float as _shared_as_float,
    meters_to_feet_int as _shared_meters_to_feet_int,
    mps_to_mph as _shared_mps_to_mph,
)
from stat_modules import beers_earned, period_stats
from stat_modules.crono_api import format_crono_line, get_crono_summary_for_activity
from stat_modules.intervals_data import get_intervals_activity_data
from stat_modules.misery_index import (
    get_misery_index_details_for_activity,
    get_misery_index_for_activity,
)
from stat_modules.smashrun import (
    aggregate_elevation_totals,
    get_activity_record,
    get_activity_elevation_feet,
    get_activities as get_smashrun_activities,
    get_badges as get_smashrun_badges,
    get_notables,
    get_stats as get_smashrun_stats,
)
from stat_modules.garmin_metrics import default_metrics as default_garmin_metrics
from stat_modules.garmin_metrics import fetch_training_status_and_scores
from storage import (
    acquire_runtime_lock,
    delete_runtime_value,
    get_runtime_lock_owner,
    get_runtime_value,
    is_activity_processed,
    mark_activity_processed,
    release_runtime_lock,
    set_runtime_value,
    write_json,
)
from template_profiles import list_template_profiles
from template_rendering import render_with_active_template
from strava_client import StravaClient, get_gap_speed_mps, mps_to_pace


logger = logging.getLogger(__name__)


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


def _record_cycle_status(
    settings: Settings,
    *,
    status: str,
    error: str | None = None,
    activity_id: int | None = None,
) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    set_runtime_value(settings.processed_log_file, "cycle.last_status", status)
    set_runtime_value(settings.processed_log_file, "cycle.last_status_at_utc", now_iso)
    if activity_id is not None:
        set_runtime_value(settings.processed_log_file, "cycle.last_activity_id", activity_id)
    if status in {"updated", "already_processed", "no_activities"}:
        set_runtime_value(settings.processed_log_file, "cycle.last_success_at_utc", now_iso)
        if error:
            set_runtime_value(settings.processed_log_file, "cycle.last_error", error)
        else:
            delete_runtime_value(settings.processed_log_file, "cycle.last_error")
    elif error:
        set_runtime_value(settings.processed_log_file, "cycle.last_error", error)
        set_runtime_value(settings.processed_log_file, "cycle.last_error_at_utc", now_iso)


def _persist_cycle_service_state(settings: Settings, service_state: dict[str, Any] | None) -> None:
    if not isinstance(service_state, dict):
        return
    snapshot = dict(service_state)
    snapshot["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    set_runtime_value(settings.processed_log_file, "cycle.service_calls", snapshot)


def _service_key(service_name: str, suffix: str) -> str:
    return f"service.{service_name}.{suffix}"


def _new_cycle_service_state(settings: Settings) -> dict[str, Any]:
    total_budget = max(0, int(settings.max_optional_service_calls_per_cycle))
    return {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "budget_enabled": bool(settings.enable_service_call_budget),
        "budget_total_optional_calls": total_budget,
        "budget_remaining_optional_calls": total_budget,
        "budget_skipped_optional_calls": 0,
        "optional_calls_executed": 0,
        "optional_cache_hits": 0,
        "required_calls_executed": 0,
        "services": {},
    }


def _service_cycle_bucket(service_state: dict[str, Any] | None, service_name: str) -> dict[str, Any]:
    if not isinstance(service_state, dict):
        return {}
    services = service_state.setdefault("services", {})
    bucket = services.get(service_name)
    if isinstance(bucket, dict):
        return bucket
    bucket = {
        "optional_calls": 0,
        "required_calls": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "skipped_budget": 0,
        "skipped_cooldown": 0,
        "errors": 0,
        "last_duration_ms": None,
        "last_status": None,
        "last_status_at_utc": None,
    }
    services[service_name] = bucket
    return bucket


def _service_counter_inc(settings: Settings, service_name: str, key_suffix: str, by: int = 1) -> None:
    runtime_key = _service_key(service_name, key_suffix)
    current = get_runtime_value(settings.processed_log_file, runtime_key, 0)
    try:
        current_val = int(current)
    except (TypeError, ValueError):
        current_val = 0
    set_runtime_value(settings.processed_log_file, runtime_key, current_val + int(by))


def _record_service_status(
    settings: Settings,
    service_name: str,
    *,
    status: str,
    duration_ms: int | None = None,
    error: str | None = None,
) -> None:
    _service_counter_inc(settings, service_name, "events_total", 1)
    _service_counter_inc(settings, service_name, f"events.{status}", 1)
    set_runtime_value(
        settings.processed_log_file,
        _service_key(service_name, "last_status"),
        status,
    )
    now_iso = datetime.now(timezone.utc).isoformat()
    set_runtime_value(
        settings.processed_log_file,
        _service_key(service_name, "last_status_at_utc"),
        now_iso,
    )
    if duration_ms is not None:
        duration_value = max(0, int(duration_ms))
        _service_counter_inc(settings, service_name, "duration_count", 1)
        _service_counter_inc(settings, service_name, "duration_total_ms", duration_value)
        set_runtime_value(
            settings.processed_log_file,
            _service_key(service_name, "last_duration_ms"),
            duration_value,
        )
    if error:
        set_runtime_value(
            settings.processed_log_file,
            _service_key(service_name, "last_error"),
            error,
        )
        set_runtime_value(
            settings.processed_log_file,
            _service_key(service_name, "last_error_at_utc"),
            now_iso,
        )


def _service_cache_runtime_key(service_name: str, cache_key: str) -> str:
    digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()[:24]
    return _service_key(service_name, f"cache.{digest}")


def _service_cache_get(
    settings: Settings,
    service_name: str,
    cache_key: str,
    ttl_seconds: int,
) -> tuple[bool, Any]:
    if ttl_seconds <= 0:
        return False, None
    runtime_key = _service_cache_runtime_key(service_name, cache_key)
    cached = get_runtime_value(settings.processed_log_file, runtime_key)
    if not isinstance(cached, dict):
        return False, None
    cached_at_raw = cached.get("cached_at_utc")
    if not isinstance(cached_at_raw, str):
        return False, None
    try:
        cached_at = datetime.fromisoformat(cached_at_raw.replace("Z", "+00:00"))
    except ValueError:
        return False, None
    if cached_at.tzinfo is None:
        cached_at = cached_at.replace(tzinfo=timezone.utc)
    age_seconds = (datetime.now(timezone.utc) - cached_at.astimezone(timezone.utc)).total_seconds()
    if age_seconds > max(0, int(ttl_seconds)):
        delete_runtime_value(settings.processed_log_file, runtime_key)
        return False, None
    return True, cached.get("value")


def _service_cache_set(
    settings: Settings,
    service_name: str,
    cache_key: str,
    ttl_seconds: int,
    value: Any,
) -> None:
    if ttl_seconds <= 0:
        return
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return
    runtime_key = _service_cache_runtime_key(service_name, cache_key)
    payload = {
        "cached_at_utc": datetime.now(timezone.utc).isoformat(),
        "ttl_seconds": int(ttl_seconds),
        "cache_key": cache_key,
        "value": value,
    }
    set_runtime_value(settings.processed_log_file, runtime_key, payload)


def _service_in_cooldown(settings: Settings, service_name: str) -> tuple[bool, str | None]:
    cooldown_until = get_runtime_value(
        settings.processed_log_file,
        _service_key(service_name, "cooldown_until_utc"),
    )
    if not isinstance(cooldown_until, str):
        return False, None
    try:
        expires = datetime.fromisoformat(cooldown_until.replace("Z", "+00:00"))
    except ValueError:
        return False, None
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    expires_utc = expires.astimezone(timezone.utc)
    now_utc = datetime.now(timezone.utc)
    if expires_utc > now_utc:
        return True, expires_utc.isoformat()
    return False, None


def _set_service_cooldown(settings: Settings, service_name: str, failure_count: int) -> int:
    delay = min(
        settings.service_cooldown_base_seconds * (2 ** max(0, failure_count - 1)),
        settings.service_cooldown_max_seconds,
    )
    cooldown_until = datetime.now(timezone.utc).timestamp() + delay
    set_runtime_value(
        settings.processed_log_file,
        _service_key(service_name, "cooldown_until_utc"),
        datetime.fromtimestamp(cooldown_until, tz=timezone.utc).isoformat(),
    )
    return delay


def _reset_service_cooldown(settings: Settings, service_name: str) -> None:
    delete_runtime_value(settings.processed_log_file, _service_key(service_name, "cooldown_until_utc"))
    set_runtime_value(settings.processed_log_file, _service_key(service_name, "failures"), 0)
    set_runtime_value(settings.processed_log_file, _service_key(service_name, "last_success_utc"), datetime.now(timezone.utc).isoformat())


def _run_service_call(
    settings: Settings,
    service_name: str,
    fn: Any,
    *args: Any,
    service_state: dict[str, Any] | None = None,
    cache_key: str | None = None,
    cache_ttl_seconds: int | None = None,
    **kwargs: Any,
) -> Any:
    cycle_bucket = _service_cycle_bucket(service_state, service_name)

    cache_ttl = int(cache_ttl_seconds if isinstance(cache_ttl_seconds, int) else settings.service_cache_ttl_seconds)
    cache_text = str(cache_key or "").strip()
    cache_enabled = bool(settings.enable_service_result_cache) and bool(cache_text) and cache_ttl > 0
    if cache_enabled:
        cache_hit, cached_value = _service_cache_get(
            settings,
            service_name,
            cache_text,
            cache_ttl,
        )
        if cache_hit:
            _record_service_status(settings, service_name, status="cache_hit")
            if cycle_bucket:
                cycle_bucket["cache_hits"] = int(cycle_bucket.get("cache_hits", 0) or 0) + 1
                cycle_bucket["last_status"] = "cache_hit"
                cycle_bucket["last_status_at_utc"] = datetime.now(timezone.utc).isoformat()
            if isinstance(service_state, dict):
                service_state["optional_cache_hits"] = int(service_state.get("optional_cache_hits", 0) or 0) + 1
            return cached_value
        _record_service_status(settings, service_name, status="cache_miss")
        if cycle_bucket:
            cycle_bucket["cache_misses"] = int(cycle_bucket.get("cache_misses", 0) or 0) + 1

    budget_enabled = bool(settings.enable_service_call_budget) and isinstance(service_state, dict)
    if budget_enabled:
        remaining = int(service_state.get("budget_remaining_optional_calls", 0) or 0)
        if remaining <= 0:
            logger.warning("Skipping %s call due to optional call budget exhaustion.", service_name)
            _record_service_status(settings, service_name, status="skipped_budget")
            if cycle_bucket:
                cycle_bucket["skipped_budget"] = int(cycle_bucket.get("skipped_budget", 0) or 0) + 1
                cycle_bucket["last_status"] = "skipped_budget"
                cycle_bucket["last_status_at_utc"] = datetime.now(timezone.utc).isoformat()
            service_state["budget_skipped_optional_calls"] = int(service_state.get("budget_skipped_optional_calls", 0) or 0) + 1
            return None
        service_state["budget_remaining_optional_calls"] = remaining - 1
        service_state["optional_calls_executed"] = int(service_state.get("optional_calls_executed", 0) or 0) + 1
        if cycle_bucket:
            cycle_bucket["optional_calls"] = int(cycle_bucket.get("optional_calls", 0) or 0) + 1

    in_cooldown, until = _service_in_cooldown(settings, service_name)
    if in_cooldown:
        logger.warning("Skipping %s call due to cooldown until %s", service_name, until)
        _record_service_status(settings, service_name, status="skipped_cooldown")
        if cycle_bucket:
            cycle_bucket["skipped_cooldown"] = int(cycle_bucket.get("skipped_cooldown", 0) or 0) + 1
            cycle_bucket["last_status"] = "skipped_cooldown"
            cycle_bucket["last_status_at_utc"] = datetime.now(timezone.utc).isoformat()
        if budget_enabled:
            # Refund budget when call is skipped for cooldown.
            service_state["budget_remaining_optional_calls"] = int(service_state.get("budget_remaining_optional_calls", 0) or 0) + 1
            service_state["optional_calls_executed"] = max(
                0,
                int(service_state.get("optional_calls_executed", 0) or 0) - 1,
            )
            if cycle_bucket:
                cycle_bucket["optional_calls"] = max(0, int(cycle_bucket.get("optional_calls", 0) or 0) - 1)
        return None

    attempts = max(1, settings.service_retry_count + 1)
    last_exc: Exception | None = None
    started = time.monotonic()
    for attempt in range(1, attempts + 1):
        try:
            result = fn(*args, **kwargs)
            _reset_service_cooldown(settings, service_name)
            duration_ms = int((time.monotonic() - started) * 1000)
            _record_service_status(
                settings,
                service_name,
                status="success",
                duration_ms=duration_ms,
            )
            if cycle_bucket:
                cycle_bucket["last_duration_ms"] = duration_ms
                cycle_bucket["last_status"] = "success"
                cycle_bucket["last_status_at_utc"] = datetime.now(timezone.utc).isoformat()
            if cache_enabled:
                _service_cache_set(settings, service_name, cache_text, cache_ttl, result)
            return result
        except Exception as exc:
            last_exc = exc
            if attempt < attempts:
                sleep_seconds = settings.service_retry_backoff_seconds * attempt
                logger.warning(
                    "%s call failed (%s/%s): %s. Retrying in %ss.",
                    service_name,
                    attempt,
                    attempts,
                    exc,
                    sleep_seconds,
                )
                time.sleep(sleep_seconds)

    failures = int(
        get_runtime_value(settings.processed_log_file, _service_key(service_name, "failures"), 0) or 0
    ) + 1
    set_runtime_value(settings.processed_log_file, _service_key(service_name, "failures"), failures)
    set_runtime_value(
        settings.processed_log_file,
        _service_key(service_name, "last_error"),
        str(last_exc) if last_exc else "unknown",
    )
    delay = _set_service_cooldown(settings, service_name, failures)
    duration_ms = int((time.monotonic() - started) * 1000)
    _record_service_status(
        settings,
        service_name,
        status="error",
        duration_ms=duration_ms,
        error=str(last_exc) if last_exc else "unknown",
    )
    if cycle_bucket:
        cycle_bucket["errors"] = int(cycle_bucket.get("errors", 0) or 0) + 1
        cycle_bucket["last_duration_ms"] = duration_ms
        cycle_bucket["last_status"] = "error"
        cycle_bucket["last_status_at_utc"] = datetime.now(timezone.utc).isoformat()
    logger.error(
        "%s failed after %s attempts. Cooling down for %ss. Last error: %s",
        service_name,
        attempts,
        delay,
        last_exc,
    )
    return None


def _run_required_call(
    settings: Settings,
    service_name: str,
    fn: Any,
    *args: Any,
    service_state: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    cycle_bucket = _service_cycle_bucket(service_state, service_name)
    if isinstance(service_state, dict):
        service_state["required_calls_executed"] = int(service_state.get("required_calls_executed", 0) or 0) + 1
    if cycle_bucket:
        cycle_bucket["required_calls"] = int(cycle_bucket.get("required_calls", 0) or 0) + 1

    attempts = max(1, settings.service_retry_count + 1)
    last_exc: Exception | None = None
    started = time.monotonic()
    for attempt in range(1, attempts + 1):
        try:
            result = fn(*args, **kwargs)
            duration_ms = int((time.monotonic() - started) * 1000)
            _record_service_status(
                settings,
                service_name,
                status="required_success",
                duration_ms=duration_ms,
            )
            if cycle_bucket:
                cycle_bucket["last_duration_ms"] = duration_ms
                cycle_bucket["last_status"] = "required_success"
                cycle_bucket["last_status_at_utc"] = datetime.now(timezone.utc).isoformat()
            return result
        except Exception as exc:
            last_exc = exc
            if attempt < attempts:
                sleep_seconds = settings.service_retry_backoff_seconds * attempt
                logger.warning(
                    "%s call failed (%s/%s): %s. Retrying in %ss.",
                    service_name,
                    attempt,
                    attempts,
                    exc,
                    sleep_seconds,
                )
                time.sleep(sleep_seconds)
    duration_ms = int((time.monotonic() - started) * 1000)
    _record_service_status(
        settings,
        service_name,
        status="required_error",
        duration_ms=duration_ms,
        error=str(last_exc) if last_exc else "unknown",
    )
    if cycle_bucket:
        cycle_bucket["errors"] = int(cycle_bucket.get("errors", 0) or 0) + 1
        cycle_bucket["last_duration_ms"] = duration_ms
        cycle_bucket["last_status"] = "required_error"
        cycle_bucket["last_status_at_utc"] = datetime.now(timezone.utc).isoformat()
    raise RuntimeError(f"{service_name} failed after {attempts} attempts: {last_exc}") from last_exc


def _format_activity_time(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    remaining = seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02}:{remaining:02}"
    return f"{minutes}:{remaining:02}"


def _display_number(value: Any, decimals: int = 1) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.{decimals}f}"
    return "N/A"


def _as_float(value: Any) -> float | None:
    return _shared_as_float(value)


def _mps_to_mph_display(speed_mps: Any) -> str:
    return _shared_mps_to_mph(speed_mps, include_unit=True)


def _mph_display(speed_mph: Any) -> str:
    parsed = _as_float(speed_mph)
    if parsed is None or parsed < 0:
        return "N/A"
    return f"{parsed:.1f} mph"


def _meters_to_feet_int(value_meters: Any) -> int | str:
    return _shared_meters_to_feet_int(value_meters)


def _temperature_f_display(value: Any) -> str:
    parsed = _as_float(value)
    if parsed is None:
        return "N/A"
    return f"{parsed:.1f}F"


def _local_datetime_display(
    start_date_local: Any,
    start_date_utc: Any,
    local_tz: timezone | ZoneInfo,
) -> tuple[str, str]:
    local_display = "N/A"
    utc_display = "N/A"

    if isinstance(start_date_utc, str) and start_date_utc.strip():
        try:
            dt_utc = datetime.fromisoformat(start_date_utc.replace("Z", "+00:00"))
            if dt_utc.tzinfo is None:
                dt_utc = dt_utc.replace(tzinfo=timezone.utc)
            dt_utc = dt_utc.astimezone(timezone.utc)
            utc_display = dt_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
            local_display = dt_utc.astimezone(local_tz).strftime("%Y-%m-%d %I:%M %p")
        except ValueError:
            pass

    if local_display == "N/A" and isinstance(start_date_local, str) and start_date_local.strip():
        try:
            dt_local = datetime.fromisoformat(start_date_local.replace("Z", "+00:00"))
            if dt_local.tzinfo is None:
                dt_local = dt_local.replace(tzinfo=local_tz)
            local_display = dt_local.astimezone(local_tz).strftime("%Y-%m-%d %I:%M %p")
            utc_display = dt_local.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        except ValueError:
            pass

    return local_display, utc_display


def _normalize_weather_context(
    weather_payload: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not isinstance(weather_payload, dict):
        return {}, {}, {}
    weather_core = weather_payload.get("weather")
    if not isinstance(weather_core, dict):
        weather_core = {}
    misery_components = weather_payload.get("misery_components")
    if not isinstance(misery_components, dict):
        misery_components = {}
    misery_payload = weather_payload.get("misery")
    if not isinstance(misery_payload, dict):
        misery_payload = {}
    return weather_core, misery_components, misery_payload


def _to_int(value: Any) -> int | str:
    parsed = _as_float(value)
    if parsed is None:
        return "N/A"
    return int(round(parsed))


def _to_pct(value: Any) -> str:
    parsed = _as_float(value)
    if parsed is None:
        return "N/A"
    return f"{int(round(parsed))}%"


def _to_temp_f(value: Any) -> str:
    parsed = _as_float(value)
    if parsed is None:
        return "N/A"
    return f"{parsed:.1f}F"


def _to_mph(value: Any) -> str:
    parsed = _as_float(value)
    if parsed is None:
        return "N/A"
    return f"{parsed:.1f} mph"


def _smashrun_datetime_local(value: Any, local_tz: timezone | ZoneInfo) -> str:
    if isinstance(value, str) and value.strip():
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=local_tz)
            return dt.astimezone(local_tz).strftime("%Y-%m-%d %I:%M %p")
        except ValueError:
            return value
    return "N/A"


def _normalize_smashrun_activity(
    activity: dict[str, Any] | None,
    *,
    local_tz: timezone | ZoneInfo,
) -> dict[str, Any]:
    if not isinstance(activity, dict):
        return {}

    distance_meters = _as_float(activity.get("distance"))
    distance_miles = (
        f"{(distance_meters / 1609.34):.2f}"
        if distance_meters is not None and distance_meters > 0
        else "N/A"
    )
    duration_seconds = _to_int(activity.get("duration"))
    pace = "N/A"
    if isinstance(duration_seconds, int) and isinstance(distance_meters, (int, float)) and distance_meters > 0:
        speed_mps = distance_meters / duration_seconds if duration_seconds > 0 else None
        pace = mps_to_pace(speed_mps)

    return {
        "activity_id": _to_int(activity.get("activityId")),
        "activity_type": str(activity.get("activityType") or "N/A"),
        "start_local": _smashrun_datetime_local(activity.get("startDateTimeLocal"), local_tz),
        "distance_miles": distance_miles,
        "duration": _format_activity_time(duration_seconds) if isinstance(duration_seconds, int) else "N/A",
        "pace": pace,
        "calories": _to_int(activity.get("calories")),
        "elevation_gain_feet": _to_int(activity.get("elevationGain")),
        "elevation_loss_feet": _to_int(activity.get("elevationLoss")),
        "elevation_ascent_feet": _to_int(activity.get("elevationAscent")),
        "elevation_descent_feet": _to_int(activity.get("elevationDescent")),
        "elevation_max_feet": _to_int(activity.get("elevationMax")),
        "elevation_min_feet": _to_int(activity.get("elevationMin")),
        "average_hr": _to_int(activity.get("heartRateAverage")),
        "max_hr": _to_int(activity.get("heartRateMax")),
        "cadence_average": _to_int(activity.get("cadenceAverage")),
        "cadence_max": _to_int(activity.get("cadenceMax")),
        "temperature_f": _to_temp_f(activity.get("temperature")),
        "apparent_temp_f": _to_temp_f(activity.get("temperatureApparent")),
        "wind_chill_f": _to_temp_f(activity.get("temperatureWindChill")),
        "humidity_pct": _to_pct(activity.get("humidity")),
        "wind_mph": _to_mph(activity.get("windSpeed")),
        "weather_type": str(activity.get("weatherType") or "N/A"),
        "terrain": str(activity.get("terrain") or "N/A"),
        "is_race": bool(activity.get("isRace")),
        "is_treadmill": bool(activity.get("isTreadmill")),
        "how_felt": str(activity.get("howFelt") or "N/A"),
        "source": str(activity.get("source") or "N/A"),
    }


def _normalize_smashrun_stats(stats: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(stats, dict):
        return {}

    return {
        "run_count": _to_int(stats.get("runCount")),
        "longest_streak": _to_int(stats.get("longestStreak")),
        "longest_streak_date": str(stats.get("longestStreakDate") or "N/A"),
        "average_days_run_per_week": (
            f"{(_as_float(stats.get('averageDaysRunPerWeek')) or 0.0):.1f}"
            if _as_float(stats.get("averageDaysRunPerWeek")) is not None
            else "N/A"
        ),
        "total_distance": (
            f"{(_as_float(stats.get('totalDistance')) or 0.0):.1f}"
            if _as_float(stats.get("totalDistance")) is not None
            else "N/A"
        ),
        "average_run_length": (
            f"{(_as_float(stats.get('averageRunLength')) or 0.0):.2f}"
            if _as_float(stats.get("averageRunLength")) is not None
            else "N/A"
        ),
        "average_distance_per_day": (
            f"{(_as_float(stats.get('averageDistancePerDay')) or 0.0):.2f}"
            if _as_float(stats.get("averageDistancePerDay")) is not None
            else "N/A"
        ),
        "average_speed": (
            f"{(_as_float(stats.get('averageSpeed')) or 0.0):.2f}"
            if _as_float(stats.get("averageSpeed")) is not None
            else "N/A"
        ),
        "average_pace": str(stats.get("averagePace") or "N/A"),
        "longest_run": (
            f"{(_as_float(stats.get('longestRun')) or 0.0):.1f}"
            if _as_float(stats.get("longestRun")) is not None
            else "N/A"
        ),
        "longest_run_when": str(stats.get("longestRunWhen") or "N/A"),
        "longest_break_between_runs_days": _to_int(stats.get("longestBreakBetweenRuns")),
        "longest_break_between_runs_date": str(stats.get("longestBreakBetweenRunsDate") or "N/A"),
        "most_often_run_day": str(stats.get("mostOftenRunOnDay") or "N/A"),
        "least_often_run_day": str(stats.get("leastOftenRunOnDay") or "N/A"),
    }


def _segment_rank_label(rank: int) -> str:
    if rank == 1:
        return "PR"
    if rank == 2:
        return "2nd"
    if rank == 3:
        return "3rd"
    return f"#{rank}"


def _coerce_string_list(value: Any, *, max_items: int = 25) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
        if len(normalized) >= max_items:
            break
    return normalized


def _extract_strava_segment_notables(activity: dict[str, Any], *, max_items: int = 20) -> list[str]:
    efforts = activity.get("segment_efforts")
    if not isinstance(efforts, list):
        return []

    selected: dict[str, tuple[int, int | None, str]] = {}
    for effort in efforts:
        if not isinstance(effort, dict):
            continue
        rank = _to_int(effort.get("pr_rank"))
        if not isinstance(rank, int):
            achievements = effort.get("achievements")
            if isinstance(achievements, list):
                for achievement in achievements:
                    if not isinstance(achievement, dict):
                        continue
                    ach_rank = _to_int(achievement.get("rank"))
                    if isinstance(ach_rank, int) and ach_rank in (1, 2, 3):
                        rank = ach_rank
                        break
        if not isinstance(rank, int) or rank not in (1, 2, 3):
            continue

        segment = effort.get("segment")
        segment_name = ""
        segment_id = ""
        if isinstance(segment, dict):
            segment_name = str(segment.get("name") or "").strip()
            segment_id = str(segment.get("id") or "").strip()
        if not segment_name:
            segment_name = str(effort.get("name") or "Unknown Segment").strip()
        if not segment_id:
            segment_id = segment_name.lower()

        elapsed_seconds = _to_int(effort.get("elapsed_time"))
        time_display = _format_activity_time(elapsed_seconds) if isinstance(elapsed_seconds, int) else "N/A"
        line = f"Strava {_segment_rank_label(rank)}: {segment_name} ({time_display})"

        existing = selected.get(segment_id)
        if existing is None:
            selected[segment_id] = (rank, elapsed_seconds if isinstance(elapsed_seconds, int) else None, line)
            continue
        current_rank, current_seconds, _ = existing
        better_rank = rank < current_rank
        better_time = (
            rank == current_rank
            and isinstance(elapsed_seconds, int)
            and (current_seconds is None or elapsed_seconds < current_seconds)
        )
        if better_rank or better_time:
            selected[segment_id] = (rank, elapsed_seconds if isinstance(elapsed_seconds, int) else None, line)

    ordered = sorted(selected.values(), key=lambda item: (item[0], item[1] if item[1] is not None else 10**9, item[2]))
    return [item[2] for item in ordered[:max_items]]


def _extract_strava_badges(
    activity: dict[str, Any],
    *,
    segment_notables: list[str],
    max_items: int = 20,
) -> list[str]:
    badges: list[str] = []
    seen: set[str] = set()

    def _add_badge(line: str) -> None:
        if not line or line in seen:
            return
        seen.add(line)
        badges.append(line)

    efforts = activity.get("segment_efforts")
    if isinstance(efforts, list):
        for effort in efforts:
            if not isinstance(effort, dict):
                continue
            achievements = effort.get("achievements")
            if not isinstance(achievements, list):
                continue

            segment_name = ""
            segment = effort.get("segment")
            if isinstance(segment, dict):
                segment_name = str(segment.get("name") or "").strip()
            if not segment_name:
                segment_name = str(effort.get("name") or "Unknown Segment").strip()

            for achievement in achievements:
                if not isinstance(achievement, dict):
                    continue
                ach_type = str(achievement.get("type") or "achievement").strip().replace("_", " ").title()
                rank = _to_int(achievement.get("rank"))
                if isinstance(rank, int) and rank in (1, 2, 3):
                    _add_badge(f"Strava: {ach_type} {_segment_rank_label(rank)} - {segment_name}")
                elif isinstance(rank, int):
                    _add_badge(f"Strava: {ach_type} #{rank} - {segment_name}")
                else:
                    _add_badge(f"Strava: {ach_type} - {segment_name}")
                if len(badges) >= max_items:
                    return badges[:max_items]

    for notable in segment_notables:
        _add_badge(notable)
        if len(badges) >= max_items:
            return badges[:max_items]

    achievement_count = _to_int(activity.get("achievement_count"))
    if isinstance(achievement_count, int) and achievement_count > 0 and not badges:
        _add_badge(f"Strava: {achievement_count} achievement(s)")
    return badges[:max_items]


def _normalize_smashrun_badges(payload: Any, *, max_items: int = 20) -> list[str]:
    if not isinstance(payload, list):
        return []

    badges: list[str] = []
    seen: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue

        earned_flags = [item.get("earned"), item.get("isEarned"), item.get("isAwarded")]
        explicit_flags = [flag for flag in earned_flags if isinstance(flag, bool)]
        if explicit_flags and not any(explicit_flags):
            continue

        title = str(
            item.get("badgeName")
            or item.get("badgeTypeName")
            or item.get("name")
            or item.get("title")
            or ""
        ).strip()
        if not title:
            continue

        level = _to_int(item.get("badgeLevel") or item.get("level") or item.get("currentLevel"))
        suffix = f" (L{level})" if isinstance(level, int) and level > 0 else ""
        line = f"Smashrun: {title}{suffix}"
        if line in seen:
            continue
        seen.add(line)
        badges.append(line)
        if len(badges) >= max_items:
            break
    return badges


def _merge_badge_lists(*badge_lists: list[str], max_items: int = 30) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for items in badge_lists:
        for item in items:
            line = str(item or "").strip()
            if not line or line in seen:
                continue
            seen.add(line)
            merged.append(line)
            if len(merged) >= max_items:
                return merged
    return merged


def _is_treadmill(activity: dict[str, Any]) -> bool:
    sport_type = str(activity.get("sport_type") or activity.get("type") or "").strip().lower()
    if sport_type == "virtualrun":
        return True
    return bool(activity.get("trainer")) and not activity.get("start_latlng")


def _distance_miles(activity: dict[str, Any]) -> float:
    return float(activity.get("distance", 0.0) or 0.0) / 1609.34


def _elevation_gain_feet(activity: dict[str, Any]) -> float:
    meters = _as_float(activity.get("total_elevation_gain")) or 0.0
    return meters * 3.28084


def _start_latlng(activity: dict[str, Any]) -> tuple[float, float] | None:
    start = activity.get("start_latlng")
    if not isinstance(start, (list, tuple)) or len(start) < 2:
        return None
    lat = _as_float(start[0])
    lon = _as_float(start[1])
    if lat is None or lon is None:
        return None
    return lat, lon


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_miles = 3958.7613
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_miles * c


def _text_blob(activity: dict[str, Any]) -> str:
    parts = [
        str(activity.get("name") or ""),
        str(activity.get("description") or ""),
        str(activity.get("private_note") or ""),
    ]
    return " ".join(parts).strip().lower()


def _profile_match_reasons(
    profile_id: str,
    activity: dict[str, Any],
    settings: Settings,
) -> list[str]:
    workout_type = _to_int(activity.get("workout_type"))
    sport_type = str(activity.get("sport_type") or activity.get("type") or "").strip().lower()
    treadmill = _is_treadmill(activity)
    distance = _distance_miles(activity)
    gain_ft = _elevation_gain_feet(activity)
    gain_per_mile = gain_ft / distance if distance > 0 else 0.0
    text = _text_blob(activity)
    start = _start_latlng(activity)

    reasons: list[str] = []
    if profile_id == "treadmill":
        if treadmill:
            reasons.append("trainer/no-gps or VirtualRun")
        return reasons

    if profile_id == "race":
        if workout_type == 1:
            reasons.append("workout_type=1")
        if any(keyword in text for keyword in (" race", "5k", "10k", "half", "marathon", "ultra")):
            reasons.append("race keyword")
        return reasons

    if profile_id == "commute":
        if bool(activity.get("commute")):
            reasons.append("commute=true")
        return reasons

    if profile_id == "trail":
        if sport_type == "trailrun":
            reasons.append("sport_type=TrailRun")
        if distance >= 3.0 and gain_per_mile >= settings.profile_trail_gain_per_mile_ft:
            reasons.append(
                f"gain_per_mile={gain_per_mile:.0f}ft >= {settings.profile_trail_gain_per_mile_ft:.0f}ft"
            )
        return reasons

    if profile_id == "long_run":
        if workout_type == 2:
            reasons.append("workout_type=2")
        if distance >= settings.profile_long_run_miles:
            reasons.append(f"distance={distance:.2f}mi >= {settings.profile_long_run_miles:.2f}mi")
        return reasons

    if profile_id == "pet":
        if any(keyword in text for keyword in ("dog", "with dog", "canicross", "🐕")):
            reasons.append("pet keyword")
        return reasons

    if profile_id in {"home", "away"}:
        if start is None:
            return reasons
        if settings.home_latitude is None or settings.home_longitude is None:
            return reasons
        radius = settings.home_radius_miles
        dist = _haversine_miles(start[0], start[1], settings.home_latitude, settings.home_longitude)
        if profile_id == "home" and dist <= radius:
            reasons.append(f"{dist:.2f}mi <= home_radius {radius:.2f}mi")
        if profile_id == "away" and dist > radius:
            reasons.append(f"{dist:.2f}mi > home_radius {radius:.2f}mi")
        return reasons

    return reasons


def _select_activity_profile(settings: Settings, detailed_activity: dict[str, Any]) -> dict[str, Any]:
    profiles = [
        profile
        for profile in list_template_profiles(settings)
        if bool(profile.get("enabled"))
    ]
    profiles.sort(key=lambda item: int(item.get("priority", 0)), reverse=True)
    default_profile = next(
        (
            profile for profile in profiles
            if str(profile.get("profile_id") or "").strip().lower() == "default"
        ),
        None,
    )

    for profile in profiles:
        profile_id = str(profile.get("profile_id") or "").strip().lower()
        if profile_id == "default":
            continue
        reasons = _profile_match_reasons(profile_id, detailed_activity, settings)
        if reasons:
            return {
                "profile_id": profile_id,
                "profile_label": str(profile.get("label") or profile_id.title()),
                "reasons": reasons,
            }

    if default_profile is not None:
        return {
            "profile_id": "default",
            "profile_label": str(default_profile.get("label") or "Default"),
            "reasons": ["fallback"],
        }

    return {"profile_id": "default", "profile_label": "Default", "reasons": ["fallback"]}


def _profile_activity_update_payload(profile_id: str, detailed_activity: dict[str, Any], description: str) -> dict[str, Any]:
    payload: dict[str, Any] = {"description": description}
    if profile_id == "treadmill":
        speed_mps = _as_float(detailed_activity.get("average_speed")) or 0.0
        speed_mph = speed_mps * 2.23694
        is_walk = speed_mph < 4.0
        payload["type"] = "Walk" if is_walk else "Run"
        payload["name"] = "Max Incline Treadmill Walk" if is_walk else "Max Incline Treadmill Run"
    return payload


def _get_garmin_client(settings: Settings) -> Any | None:
    if not settings.enable_garmin:
        return None
    if not settings.garmin_email or not settings.garmin_password:
        logger.warning("Garmin is enabled but credentials are missing. Using N/A values.")
        return None

    try:
        from garminconnect import Garmin

        client = Garmin(settings.garmin_email, settings.garmin_password)
        client.login()
        return client
    except Exception as exc:
        logger.error("Garmin login failed: %s", exc)
        return None


def _get_garmin_metrics(client: Any | None) -> dict[str, Any]:
    if client is None:
        return default_garmin_metrics()
    try:
        return fetch_training_status_and_scores(client)
    except Exception as exc:
        logger.error("Garmin data fetch failed: %s", exc)
        return default_garmin_metrics()


def _merge_hr_cadence_from_strava(training: dict[str, Any], detailed_activity: dict[str, Any]) -> tuple[Any, Any]:
    average_hr = training.get("average_hr", "N/A")
    running_cadence = training.get("running_cadence", "N/A")

    strava_hr = detailed_activity.get("average_heartrate")
    if average_hr == "N/A" and isinstance(strava_hr, (int, float)):
        average_hr = int(round(strava_hr))

    strava_cadence = detailed_activity.get("average_cadence")
    if running_cadence == "N/A" and isinstance(strava_cadence, (int, float)):
        running_cadence = int(round(strava_cadence * 2 if strava_cadence < 130 else strava_cadence))

    return average_hr, running_cadence


def _build_description(
    detailed_activity: dict[str, Any],
    training: dict[str, Any],
    intervals_payload: dict[str, Any] | None,
    week: dict[str, Any],
    month: dict[str, Any],
    year: dict[str, Any],
    longest_streak: int | None,
    notables: list[str],
    latest_elevation_feet: float | None,
    misery_index: float | None,
    misery_index_description: str | None,
    air_quality_index: int | None,
    aqi_description: str | None,
    crono_line: str | None = None,
) -> str:
    achievements = intervals_payload.get("achievements", []) if intervals_payload else []
    norm_power = intervals_payload.get("norm_power", "N/A") if intervals_payload else "N/A"
    work = intervals_payload.get("work", "N/A") if intervals_payload else "N/A"
    efficiency = intervals_payload.get("efficiency", "N/A") if intervals_payload else "N/A"
    icu_summary = intervals_payload.get("icu_summary", "N/A") if intervals_payload else "N/A"
    icu_fitness = intervals_payload.get("fitness", "N/A") if intervals_payload else "N/A"
    icu_fatigue = intervals_payload.get("fatigue", "N/A") if intervals_payload else "N/A"
    icu_load = intervals_payload.get("load", intervals_payload.get("training_load", "N/A")) if intervals_payload else "N/A"
    icu_ramp = intervals_payload.get("ramp_display", intervals_payload.get("ramp", "N/A")) if intervals_payload else "N/A"
    icu_form_percent = intervals_payload.get("form_percent_display", "N/A") if intervals_payload else "N/A"
    icu_form_class = intervals_payload.get("form_class", "N/A") if intervals_payload else "N/A"
    icu_form_emoji = intervals_payload.get("form_class_emoji", "⚪") if intervals_payload else "⚪"

    distance_miles = round(float(detailed_activity.get("distance", 0) or 0) / 1609.34, 2)
    elapsed_seconds = int(
        detailed_activity.get("moving_time")
        or detailed_activity.get("elapsed_time")
        or 0
    )
    activity_time = _format_activity_time(elapsed_seconds)
    beers = beers_earned.calculate_beers(detailed_activity)

    gap_speed = get_gap_speed_mps(detailed_activity)
    if gap_speed is None:
        garmin_gap_speed = training.get("avg_grade_adjusted_speed")
        if isinstance(garmin_gap_speed, (int, float)) and garmin_gap_speed > 0:
            gap_speed = float(garmin_gap_speed)
    if gap_speed is None:
        average_speed = detailed_activity.get("average_speed")
        if isinstance(average_speed, (int, float)) and average_speed > 0:
            gap_speed = float(average_speed)
    gap_pace = mps_to_pace(gap_speed)

    elevation_feet = latest_elevation_feet
    if elevation_feet is None:
        strava_elevation_m = detailed_activity.get("total_elevation_gain")
        if isinstance(strava_elevation_m, (int, float)):
            elevation_feet = float(strava_elevation_m) * 3.28084

    average_hr, running_cadence = _merge_hr_cadence_from_strava(training, detailed_activity)

    misery_display = misery_index if misery_index is not None else "N/A"
    misery_desc_display = misery_index_description or ""
    aqi_display = air_quality_index if air_quality_index is not None else "N/A"
    aqi_desc_display = aqi_description or ""

    vo2_value = training.get("vo2max")
    vo2_display = _display_number(vo2_value, decimals=1) if isinstance(vo2_value, (int, float)) else str(vo2_value)

    description = ""
    description += f"🏆 {longest_streak if longest_streak is not None else 'N/A'} days in a row\n"

    if notables:
        description += "\n".join([f"🏅 {notable}" for notable in notables]) + "\n"

    if achievements:
        description += "\n".join([f"🏅 {achievement}" for achievement in achievements]) + "\n"

    description += f"🌤️🌡️ Misery Index: {misery_display} {misery_desc_display} | 🏭 AQI: {aqi_display}{aqi_desc_display}\n"
    if crono_line:
        description += f"{crono_line}\n"
    description += (
        f"🌤️🚦 Training Readiness: {training.get('training_readiness_score', 'N/A')} "
        f"{training.get('training_readiness_emoji', '⚪')} | "
        f"💗 {training.get('resting_hr', 'N/A')} | 💤 {training.get('sleep_score', 'N/A')}\n"
    )

    description += (
        f"👟🏃 {gap_pace} | 🗺️ {distance_miles} | "
        f"🏔️ {int(round(elevation_feet)) if elevation_feet is not None else 'N/A'}' | "
        f"🕓 {activity_time} | 🍺 {beers:.1f}\n"
    )

    description += (
        f"👟👣 {running_cadence if running_cadence != 'N/A' else 'N/A'}spm | "
        f"💼 {work} | ⚡ {norm_power} | "
        f"💓 {average_hr if average_hr != 'N/A' else 'N/A'} | ⚙️{efficiency}\n"
    )

    description += (
        f"🚄 {training.get('training_status_emoji', '⚪')} {training.get('training_status_key', 'N/A')} | "
        f"{training.get('aerobic_training_effect', 'N/A')} : {training.get('anaerobic_training_effect', 'N/A')} - "
        f"{training.get('training_effect_label', 'N/A')}\n"
    )

    description += f"🚄 {icu_summary}\n"
    description += (
        f"🚄 🏋️ {icu_fitness} | 💦 {icu_fatigue} | 🎯 {icu_load} | 📈 {icu_ramp} | "
        f"🗿 {icu_form_percent} - {icu_form_class} {icu_form_emoji}\n"
    )

    description += (
        f"❤️‍🔥 {vo2_display} | ♾ Endur: {training.get('endurance_overall_score', 'N/A')} | "
        f"🗻 Hill: {training.get('hill_overall_score', 'N/A')}\n\n"
    )

    description += "7️⃣ Past 7 days:\n"
    description += (
        f"🏃 {week['gap']} | 🗺️ {week['distance']:.1f} | "
        f"🏔️ {int(round(week['elevation']))}' | 🕓 {week['duration']} | "
        f"🍺 {week['beers_earned']:.0f}\n"
    )

    description += "📅 Past 30 days:\n"
    description += (
        f"🏃 {month['gap']} | 🗺️ {month['distance']:.0f} | "
        f"🏔️ {int(round(month['elevation']))}' | 🕓 {month['duration']} | "
        f"🍺 {month['beers_earned']:.0f}\n"
    )

    description += "🌍 This Year:\n"
    description += (
        f"🏃 {year['gap']} | 🗺️ {year['distance']:.0f} | "
        f"🏔️ {int(round(year['elevation']))}' | 🕓 {year['duration']} | "
        f"🍺 {year['beers_earned']:.0f}\n"
    )

    return description


def _build_description_context(
    *,
    detailed_activity: dict[str, Any],
    training: dict[str, Any],
    intervals_payload: dict[str, Any] | None,
    week: dict[str, Any],
    month: dict[str, Any],
    year: dict[str, Any],
    longest_streak: int | None,
    notables: list[str],
    latest_elevation_feet: float | None,
    misery_index: float | None,
    misery_index_description: str | None,
    air_quality_index: int | None,
    aqi_description: str | None,
    crono_line: str | None = None,
    crono_summary: dict[str, Any] | None = None,
    weather_payload: dict[str, Any] | None = None,
    timezone_name: str = "UTC",
    smashrun_activity: dict[str, Any] | None = None,
    smashrun_stats: dict[str, Any] | None = None,
    smashrun_badges: list[dict[str, Any]] | None = None,
    garmin_period_fallback: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    intervals_payload = intervals_payload or {}
    achievements = intervals_payload.get("achievements", [])
    norm_power = intervals_payload.get("norm_power", "N/A")
    work = intervals_payload.get("work", "N/A")
    efficiency = intervals_payload.get("efficiency", "N/A")
    icu_summary = intervals_payload.get("icu_summary", "N/A")
    weather_core, weather_components, misery_payload = _normalize_weather_context(weather_payload)

    try:
        local_tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        local_tz = timezone.utc

    smashrun_activity = smashrun_activity or {}
    smashrun_stats = smashrun_stats or {}
    smashrun_badges = smashrun_badges or []
    garmin_period_fallback = garmin_period_fallback or {}
    smashrun_activity_context = _normalize_smashrun_activity(smashrun_activity, local_tz=local_tz)
    smashrun_stats_context = _normalize_smashrun_stats(smashrun_stats)
    strava_segment_notables = _extract_strava_segment_notables(detailed_activity)
    garmin_segment_notables = _coerce_string_list(training.get("garmin_segment_notables"), max_items=20)
    segment_notables = _merge_badge_lists(strava_segment_notables, garmin_segment_notables, max_items=25)
    strava_badges = _extract_strava_badges(detailed_activity, segment_notables=strava_segment_notables)
    garmin_badges = _coerce_string_list(training.get("garmin_badges"), max_items=20)
    smashrun_badges_lines = _normalize_smashrun_badges(smashrun_badges)
    badges = _merge_badge_lists(strava_badges, garmin_badges, smashrun_badges_lines, max_items=30)

    distance_miles = round(float(detailed_activity.get("distance", 0) or 0) / 1609.34, 2)
    moving_seconds = int(detailed_activity.get("moving_time") or 0)
    elapsed_seconds = int(detailed_activity.get("elapsed_time") or moving_seconds or 0)
    activity_time = _format_activity_time(moving_seconds or elapsed_seconds)
    beers = beers_earned.calculate_beers(detailed_activity)
    treadmill_incline_percent = 15
    treadmill_elevation_feet_15pct = int(round(distance_miles * 5280 * (treadmill_incline_percent / 100.0)))
    activity_type = str(detailed_activity.get("type") or "N/A")
    sport_type = str(detailed_activity.get("sport_type") or activity_type)
    workout_type = _to_int(detailed_activity.get("workout_type"))
    start_latlng = detailed_activity.get("start_latlng")
    has_gps = bool(_start_latlng(detailed_activity))

    calories = detailed_activity.get("calories")
    calories_display = (
        int(round(float(calories)))
        if isinstance(calories, (int, float))
        else "N/A"
    )
    start_local_display, start_utc_display = _local_datetime_display(
        detailed_activity.get("start_date_local"),
        detailed_activity.get("start_date"),
        local_tz,
    )

    gap_speed = get_gap_speed_mps(detailed_activity)
    if gap_speed is None:
        garmin_gap_speed = training.get("avg_grade_adjusted_speed")
        if isinstance(garmin_gap_speed, (int, float)) and garmin_gap_speed > 0:
            gap_speed = float(garmin_gap_speed)
    if gap_speed is None:
        average_speed = detailed_activity.get("average_speed")
        if isinstance(average_speed, (int, float)) and average_speed > 0:
            gap_speed = float(average_speed)
    gap_pace = mps_to_pace(gap_speed)

    elevation_feet = latest_elevation_feet
    if elevation_feet is None:
        strava_elevation_m = detailed_activity.get("total_elevation_gain")
        if isinstance(strava_elevation_m, (int, float)):
            elevation_feet = float(strava_elevation_m) * 3.28084

    elev_high_feet = _meters_to_feet_int(detailed_activity.get("elev_high"))
    elev_low_feet = _meters_to_feet_int(detailed_activity.get("elev_low"))
    average_pace_raw = mps_to_pace(detailed_activity.get("average_speed"))
    average_pace = f"{average_pace_raw}/mi" if average_pace_raw != "N/A" else "N/A"
    average_speed_mph = _mps_to_mph_display(detailed_activity.get("average_speed"))
    max_speed_mph = _mps_to_mph_display(detailed_activity.get("max_speed"))
    average_temp_f = _temperature_f_display(detailed_activity.get("average_temp"))

    average_hr, running_cadence = _merge_hr_cadence_from_strava(training, detailed_activity)
    max_hr = (
        int(round(float(detailed_activity.get("max_heartrate"))))
        if isinstance(detailed_activity.get("max_heartrate"), (int, float))
        else "N/A"
    )

    chronic_load = training.get("chronic_load")
    acute_load = training.get("acute_load")
    if isinstance(chronic_load, (int, float)) and isinstance(acute_load, (int, float)) and chronic_load != 0:
        load_ratio = round(acute_load / chronic_load, 1)
    else:
        load_ratio = "N/A"

    misery_display = misery_index if misery_index is not None else "N/A"
    misery_desc_display = misery_index_description or ""
    aqi_display = air_quality_index if air_quality_index is not None else "N/A"
    aqi_desc_display = aqi_description or ""
    misery_index_payload = misery_payload.get("index")
    if not isinstance(misery_index_payload, dict):
        misery_index_payload = {}
    misery_index_value = misery_index_payload.get("value")
    if not isinstance(misery_index_value, (int, float)):
        misery_index_value = misery_index if isinstance(misery_index, (int, float)) else None
    misery_emoji = misery_index_payload.get("emoji")
    if not isinstance(misery_emoji, str):
        misery_emoji = (
            misery_desc_display.split(" ", 1)[0]
            if isinstance(misery_desc_display, str) and misery_desc_display.strip()
            else "N/A"
        )
    misery_polarity = misery_index_payload.get("polarity")
    if not isinstance(misery_polarity, str):
        misery_polarity = "neutral"
    misery_severity = misery_index_payload.get("severity")
    if not isinstance(misery_severity, str):
        misery_severity = "unknown"
    misery_description = misery_index_payload.get("description")
    if not isinstance(misery_description, str):
        misery_description = misery_desc_display
    hot_load = misery_index_payload.get("hot_load")
    cold_load = misery_index_payload.get("cold_load")
    delta_hot_cold = misery_index_payload.get("delta")

    vo2_value = training.get("vo2max")
    vo2_display = _display_number(vo2_value, decimals=1) if isinstance(vo2_value, (int, float)) else str(vo2_value)
    crono_summary = crono_summary or {}

    weather_humidity_pct = (
        int(round(float(weather_core.get("humidity"))))
        if isinstance(weather_core.get("humidity"), (int, float))
        else "N/A"
    )
    weather_cloud_pct = (
        int(round(float(weather_core.get("cloud"))))
        if isinstance(weather_core.get("cloud"), (int, float))
        else "N/A"
    )
    weather_chance_rain_pct = (
        int(round(float(weather_core.get("chance_of_rain"))))
        if isinstance(weather_core.get("chance_of_rain"), (int, float))
        else "N/A"
    )
    weather_chance_snow_pct = (
        int(round(float(weather_core.get("chance_of_snow"))))
        if isinstance(weather_core.get("chance_of_snow"), (int, float))
        else "N/A"
    )
    weather_precip_in = (
        f"{float(weather_core.get('precip_in')):.2f}in"
        if isinstance(weather_core.get("precip_in"), (int, float))
        else "N/A"
    )
    weather_condition = (
        str(weather_core.get("condition_text")).strip().title()
        if isinstance(weather_core.get("condition_text"), str) and weather_core.get("condition_text")
        else "N/A"
    )

    return {
        "streak_days": longest_streak if longest_streak is not None else "N/A",
        "notables": notables,
        "achievements": achievements,
        "badges": badges,
        "strava_badges": strava_badges,
        "garmin_badges": garmin_badges,
        "smashrun_badges": smashrun_badges_lines,
        "segment_notables": segment_notables,
        "strava_segment_notables": strava_segment_notables,
        "garmin_segment_notables": garmin_segment_notables,
        "crono": {
            "line": crono_line,
            "date": crono_summary.get("date"),
            "average_net_kcal_per_day": crono_summary.get("average_net_kcal_per_day"),
            "average_status": crono_summary.get("average_status"),
            "protein_g": crono_summary.get("protein_g"),
            "carbs_g": crono_summary.get("carbs_g"),
        },
        "misery": {
            "index": {
                "value": round(float(misery_index_value), 1) if isinstance(misery_index_value, (int, float)) else "N/A",
                "emoji": misery_emoji,
                "polarity": misery_polarity,
                "severity": misery_severity,
                "description": misery_description,
                "hot_load": hot_load if isinstance(hot_load, (int, float)) else "N/A",
                "cold_load": cold_load if isinstance(cold_load, (int, float)) else "N/A",
                "delta": delta_hot_cold if isinstance(delta_hot_cold, (int, float)) else "N/A",
            },
            "emoji": misery_emoji,
            "polarity": misery_polarity,
            "severity": misery_severity,
            "description": misery_description,
        },
        "weather": {
            "misery_index": misery_display,
            "misery_description": misery_desc_display,
            "aqi": aqi_display,
            "aqi_description": aqi_desc_display,
            "temp_f": _temperature_f_display(weather_core.get("temp_f")),
            "dewpoint_f": _temperature_f_display(weather_core.get("dewpoint_f")),
            "humidity_pct": weather_humidity_pct,
            "wind_mph": _mph_display(weather_core.get("wind_mph")),
            "cloud_pct": weather_cloud_pct,
            "precip_in": weather_precip_in,
            "chance_rain_pct": weather_chance_rain_pct,
            "chance_snow_pct": weather_chance_snow_pct,
            "condition": weather_condition,
            "is_day": weather_core.get("is_day") if isinstance(weather_core.get("is_day"), bool) else None,
            "heatindex_f": _temperature_f_display(weather_core.get("heatindex_f")),
            "windchill_f": _temperature_f_display(weather_core.get("windchill_f")),
            "tz_id": weather_core.get("tz_id") or "N/A",
            "apparent_temp_f": _temperature_f_display(weather_components.get("apparent_temp_f")),
            "details": weather_core,
            "components": weather_components,
        },
        "training": {
            "readiness_score": training.get("training_readiness_score", "N/A"),
            "readiness_emoji": training.get("training_readiness_emoji", "⚪"),
            "readiness_level": training.get("readiness_level", "N/A"),
            "readiness_feedback": training.get("readiness_feedback", "N/A"),
            "recovery_time_hours": training.get("recovery_time_hours", "N/A"),
            "readiness_factors": training.get("readiness_factors", {}),
            "resting_hr": training.get("resting_hr", "N/A"),
            "sleep_score": training.get("sleep_score", "N/A"),
            "status_emoji": training.get("training_status_emoji", "⚪"),
            "status_key": training.get("training_status_key", "N/A"),
            "aerobic_te": training.get("aerobic_training_effect", "N/A"),
            "anaerobic_te": training.get("anaerobic_training_effect", "N/A"),
            "te_label": training.get("training_effect_label", "N/A"),
            "chronic_load": training.get("chronic_load", "N/A"),
            "acute_load": training.get("acute_load", "N/A"),
            "load_ratio": load_ratio,
            "acwr_status": training.get("acwr_status", "N/A"),
            "acwr_status_emoji": training.get("acwr_status_emoji", "⚪"),
            "acwr_percent": training.get("acwr_percent", "N/A"),
            "daily_acwr_ratio": training.get("daily_acwr_ratio", "N/A"),
            "load_tunnel_min": training.get("load_tunnel_min", "N/A"),
            "load_tunnel_max": training.get("load_tunnel_max", "N/A"),
            "weekly_training_load": training.get("weekly_training_load", "N/A"),
            "fitness_trend": training.get("fitness_trend", "N/A"),
            "load_level_trend": training.get("load_level_trend", "N/A"),
            "vo2": vo2_display,
            "endurance_score": training.get("endurance_overall_score", "N/A"),
            "hill_score": training.get("hill_overall_score", "N/A"),
            "fitness_age": training.get("fitness_age", "N/A"),
            "fitness_age_details": training.get("fitness_age_details", {}),
        },
        "activity": {
            "id": int(round(float(detailed_activity.get("id")))) if isinstance(detailed_activity.get("id"), (int, float)) else "N/A",
            "name": str(detailed_activity.get("name") or "N/A"),
            "type": activity_type,
            "sport_type": sport_type,
            "workout_type": workout_type if workout_type is not None else "N/A",
            "commute": bool(detailed_activity.get("commute")),
            "trainer": bool(detailed_activity.get("trainer")),
            "has_gps": has_gps,
            "start_latlng": start_latlng if isinstance(start_latlng, (list, tuple)) else [],
            "gap_pace": gap_pace,
            "average_pace": average_pace,
            "distance_miles": f"{distance_miles:.2f}",
            "elevation_feet": int(round(elevation_feet)) if elevation_feet is not None else "N/A",
            "elev_high_feet": elev_high_feet,
            "elev_low_feet": elev_low_feet,
            "time": activity_time,
            "moving_time": _format_activity_time(moving_seconds),
            "elapsed_time": _format_activity_time(elapsed_seconds),
            "beers": f"{beers:.1f}",
            "calories": calories_display,
            "average_speed_mph": average_speed_mph,
            "max_speed_mph": max_speed_mph,
            "average_temp_f": average_temp_f,
            "start_local": start_local_display,
            "start_utc": start_utc_display,
            "cadence_spm": running_cadence if running_cadence != "N/A" else "N/A",
            "work": work,
            "norm_power": norm_power,
            "average_hr": average_hr if average_hr != "N/A" else "N/A",
            "max_hr": max_hr,
            "efficiency": efficiency,
            "treadmill_incline_percent": treadmill_incline_percent,
            "treadmill_elevation_feet_15pct": treadmill_elevation_feet_15pct,
            "social": {
                "kudos": int(round(_as_float(detailed_activity.get("kudos_count")) or 0)),
                "comments": int(round(_as_float(detailed_activity.get("comment_count")) or 0)),
                "achievements": int(round(_as_float(detailed_activity.get("achievement_count")) or 0)),
            },
            "segment_notables": strava_segment_notables,
        },
        "intervals": {
            "summary": icu_summary,
            "ctl": intervals_payload.get("ctl", "N/A"),
            "atl": intervals_payload.get("atl", "N/A"),
            "fitness": intervals_payload.get("fitness", intervals_payload.get("ctl", "N/A")),
            "fatigue": intervals_payload.get("fatigue", intervals_payload.get("atl", "N/A")),
            "training_load": intervals_payload.get("training_load", "N/A"),
            "load": intervals_payload.get("load", intervals_payload.get("training_load", "N/A")),
            "ramp": intervals_payload.get("ramp", "N/A"),
            "ramp_display": intervals_payload.get("ramp_display", "N/A"),
            "form_percent": intervals_payload.get("form_percent", "N/A"),
            "form_percent_display": intervals_payload.get("form_percent_display", "N/A"),
            "form_class": intervals_payload.get("form_class", "N/A"),
            "form_class_emoji": intervals_payload.get("form_class_emoji", "⚪"),
            "strain_score": intervals_payload.get("strain_score", "N/A"),
            "pace_load": intervals_payload.get("pace_load", "N/A"),
            "hr_load": intervals_payload.get("hr_load", "N/A"),
            "power_load": intervals_payload.get("power_load", "N/A"),
            "avg_pace": intervals_payload.get("avg_pace", "N/A"),
            "avg_speed_mph": intervals_payload.get("avg_speed_mph", "N/A"),
            "max_speed_mph": intervals_payload.get("max_speed_mph", "N/A"),
            "distance_miles": intervals_payload.get("distance_miles", "N/A"),
            "moving_time": intervals_payload.get("moving_time", "N/A"),
            "elapsed_time": intervals_payload.get("elapsed_time", "N/A"),
            "average_hr": intervals_payload.get("average_hr", "N/A"),
            "max_hr": intervals_payload.get("max_hr", "N/A"),
            "elevation_gain_feet": intervals_payload.get("elevation_gain_feet", "N/A"),
            "elevation_loss_feet": intervals_payload.get("elevation_loss_feet", "N/A"),
            "average_temp_f": intervals_payload.get("average_temp_f", "N/A"),
            "max_temp_f": intervals_payload.get("max_temp_f", "N/A"),
            "min_temp_f": intervals_payload.get("min_temp_f", "N/A"),
            "zone_summary": intervals_payload.get("zone_summary", "N/A"),
            "hr_zone_summary": intervals_payload.get("hr_zone_summary", "N/A"),
            "pace_zone_summary": intervals_payload.get("pace_zone_summary", "N/A"),
            "gap_zone_summary": intervals_payload.get("gap_zone_summary", "N/A"),
        },
        "garmin": {
            "badges": garmin_badges,
            "segment_notables": garmin_segment_notables,
            "last_activity": training.get("garmin_last_activity", {}),
            "readiness": {
                "score": training.get("training_readiness_score", "N/A"),
                "level": training.get("readiness_level", "N/A"),
                "emoji": training.get("training_readiness_emoji", "⚪"),
                "sleep_score": training.get("sleep_score", "N/A"),
                "feedback": training.get("readiness_feedback", "N/A"),
                "recovery_time_hours": training.get("recovery_time_hours", "N/A"),
                "factors": training.get("readiness_factors", {}),
            },
            "status": {
                "key": training.get("training_status_key", "N/A"),
                "emoji": training.get("training_status_emoji", "⚪"),
                "fitness_trend": training.get("fitness_trend", "N/A"),
                "load_level_trend": training.get("load_level_trend", "N/A"),
                "weekly_training_load": training.get("weekly_training_load", "N/A"),
                "load_tunnel_min": training.get("load_tunnel_min", "N/A"),
                "load_tunnel_max": training.get("load_tunnel_max", "N/A"),
                "daily_acwr_ratio": training.get("daily_acwr_ratio", "N/A"),
                "acwr_percent": training.get("acwr_percent", "N/A"),
            },
            "fitness_age": training.get("fitness_age_details", {}),
        },
        "smashrun": {
            "badges": smashrun_badges_lines,
            "latest_activity": smashrun_activity_context,
            "stats": smashrun_stats_context,
        },
        "periods": {
            "week": {
                "gap": week["gap"],
                "distance_miles": f"{week['distance']:.1f}",
                "elevation_feet": int(round(week["elevation"])),
                "duration": week["duration"],
                "beers": f"{week['beers_earned']:.0f}",
                "calories": int(round(float(week.get("calories", 0.0) or 0.0))),
                "run_count": int(round(float(week.get("run_count", 0) or 0))),
            },
            "month": {
                "gap": month["gap"],
                "distance_miles": f"{month['distance']:.0f}",
                "elevation_feet": int(round(month["elevation"])),
                "duration": month["duration"],
                "beers": f"{month['beers_earned']:.0f}",
                "calories": int(round(float(month.get("calories", 0.0) or 0.0))),
                "run_count": int(round(float(month.get("run_count", 0) or 0))),
            },
            "year": {
                "gap": year["gap"],
                "distance_miles": f"{year['distance']:.0f}",
                "elevation_feet": int(round(year["elevation"])),
                "duration": year["duration"],
                "beers": f"{year['beers_earned']:.0f}",
                "calories": int(round(float(year.get("calories", 0.0) or 0.0))),
                "run_count": int(round(float(year.get("run_count", 0) or 0))),
            },
        },
        "raw": {
            "activity": detailed_activity,
            "training": training,
            "intervals": intervals_payload,
            "week": week,
            "month": month,
            "year": year,
            "weather": weather_payload or {},
            "smashrun": {
                "activity": smashrun_activity,
                "stats": smashrun_stats,
                "badges": smashrun_badges,
            },
            "garmin_period_fallback": garmin_period_fallback,
        },
    }


def _resolve_cycle_time_context(settings: Settings) -> tuple[timezone | ZoneInfo, datetime, datetime, datetime]:
    try:
        local_tz = ZoneInfo(settings.timezone)
    except ZoneInfoNotFoundError:
        logger.warning("Unknown timezone '%s'. Falling back to UTC.", settings.timezone)
        local_tz = timezone.utc
    now_local = datetime.now(local_tz)
    now_utc = now_local.astimezone(timezone.utc)
    year_start_utc = datetime(now_local.year, 1, 1, tzinfo=local_tz).astimezone(timezone.utc)
    return local_tz, now_local, now_utc, year_start_utc


def _select_strava_activity(
    settings: Settings,
    activities: list[dict[str, Any]],
    *,
    force_update: bool,
    activity_id: int | None,
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
    latest = activities[0]
    if activity_id is not None:
        target_activity_id = int(activity_id)
        selected = next(
            (activity for activity in activities if int(activity["id"]) == target_activity_id),
            {"id": target_activity_id},
        )
        return latest, selected, None

    if force_update:
        return latest, latest, None

    selected = next(
        (
            activity
            for activity in activities
            if not is_activity_processed(
                settings.processed_log_file,
                int(activity["id"]),
            )
        ),
        None,
    )
    if selected is None:
        return latest, None, {"status": "already_processed", "activity_id": int(latest["id"])}
    return latest, selected, None


def _collect_smashrun_context(
    settings: Settings,
    detailed_activity: dict[str, Any],
    *,
    selected_activity_id: int,
    latest_activity_id: int,
    now_utc: datetime,
    service_state: dict[str, Any] | None,
) -> dict[str, Any]:
    context: dict[str, Any] = {
        "longest_streak": None,
        "notables": [],
        "latest_elevation_feet": None,
        "smashrun_elevation_totals": {"week": 0.0, "month": 0.0, "year": 0.0},
        "smashrun_activity_record": None,
        "smashrun_stats": None,
        "smashrun_badges": [],
    }

    if not (settings.enable_smashrun and settings.smashrun_access_token):
        return context

    smashrun_activities = _run_service_call(
        settings,
        "smashrun.activities",
        get_smashrun_activities,
        settings.smashrun_access_token,
        service_state=service_state,
        cache_key="smashrun.activities:default",
        cache_ttl_seconds=settings.service_cache_ttl_seconds,
    )

    if smashrun_activities:
        context["smashrun_activity_record"] = get_activity_record(smashrun_activities, detailed_activity)
        context["latest_elevation_feet"] = get_activity_elevation_feet(smashrun_activities, detailed_activity)
        context["smashrun_elevation_totals"] = aggregate_elevation_totals(
            smashrun_activities,
            now_utc,
            timezone_name=settings.timezone,
        )
        if selected_activity_id == latest_activity_id:
            latest_smashrun_activity_id = smashrun_activities[0].get("activityId") if smashrun_activities else None
            notables_payload = _run_service_call(
                settings,
                "smashrun.notables",
                get_notables,
                settings.smashrun_access_token,
                latest_activity_id=latest_smashrun_activity_id,
                service_state=service_state,
                cache_key=f"smashrun.notables:{latest_smashrun_activity_id or 'latest'}",
                cache_ttl_seconds=settings.service_cache_ttl_seconds,
            )
            if isinstance(notables_payload, list):
                context["notables"] = [str(item) for item in notables_payload if str(item).strip()]
        else:
            logger.info("Skipping Smashrun notables because selected activity is not latest.")

    smashrun_stats_payload = _run_service_call(
        settings,
        "smashrun.stats",
        get_smashrun_stats,
        settings.smashrun_access_token,
        service_state=service_state,
        cache_key="smashrun.stats:default",
        cache_ttl_seconds=settings.service_cache_ttl_seconds,
    )
    if isinstance(smashrun_stats_payload, dict):
        context["smashrun_stats"] = smashrun_stats_payload
        streak_numeric = _as_float(smashrun_stats_payload.get("longestStreak"))
        if streak_numeric is not None:
            context["longest_streak"] = int(round(streak_numeric))

    smashrun_badges_payload = _run_service_call(
        settings,
        "smashrun.badges",
        get_smashrun_badges,
        settings.smashrun_access_token,
        service_state=service_state,
        cache_key="smashrun.badges:default",
        cache_ttl_seconds=settings.service_cache_ttl_seconds,
    )
    if isinstance(smashrun_badges_payload, list):
        context["smashrun_badges"] = [item for item in smashrun_badges_payload if isinstance(item, dict)]

    return context


def _collect_weather_context(
    settings: Settings,
    detailed_activity: dict[str, Any],
    *,
    selected_activity_id: int,
    service_state: dict[str, Any] | None,
) -> dict[str, Any]:
    context = {
        "weather_details": None,
        "misery_index": None,
        "misery_desc": None,
        "aqi": None,
        "aqi_desc": None,
    }
    if not settings.enable_weather:
        return context

    weather_details = _run_service_call(
        settings,
        "weather.details",
        get_misery_index_details_for_activity,
        detailed_activity,
        settings.weather_api_key,
        service_state=service_state,
        cache_key=f"weather.details:{selected_activity_id}",
        cache_ttl_seconds=settings.service_cache_ttl_seconds,
    )
    context["weather_details"] = weather_details
    if weather_details:
        context["misery_index"] = weather_details.get("misery_index")
        context["misery_desc"] = weather_details.get("misery_description")
        context["aqi"] = weather_details.get("aqi")
        context["aqi_desc"] = weather_details.get("aqi_description")
        return context

    fallback_weather = _run_service_call(
        settings,
        "weather.fallback",
        get_misery_index_for_activity,
        detailed_activity,
        settings.weather_api_key,
        service_state=service_state,
        cache_key=f"weather.fallback:{selected_activity_id}",
        cache_ttl_seconds=settings.service_cache_ttl_seconds,
    )
    if isinstance(fallback_weather, tuple) and len(fallback_weather) == 4:
        context["misery_index"], context["misery_desc"], context["aqi"], context["aqi_desc"] = fallback_weather
    return context


def _collect_crono_context(
    settings: Settings,
    detailed_activity: dict[str, Any],
    *,
    selected_activity_id: int,
    service_state: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, str | None]:
    if not settings.enable_crono_api:
        return None, None
    crono_summary = _run_service_call(
        settings,
        "crono.summary",
        get_crono_summary_for_activity,
        service_state=service_state,
        cache_key=f"crono.summary:{selected_activity_id}:{settings.timezone}:7",
        cache_ttl_seconds=settings.service_cache_ttl_seconds,
        activity=detailed_activity,
        timezone_name=settings.timezone,
        base_url=settings.crono_api_base_url,
        api_key=settings.crono_api_key,
        days=7,
    )
    return crono_summary, format_crono_line(crono_summary)


def run_once(force_update: bool = False, activity_id: int | None = None) -> dict[str, Any]:
    settings = Settings.from_env()
    settings.validate()
    settings.ensure_state_paths()

    _configure_logging(settings.log_level)
    lock_owner = f"{uuid.uuid4()}:{int(time.time())}"
    lock_name = "run_once"
    selected_activity_id: int | None = None
    service_state = _new_cycle_service_state(settings)

    if not acquire_runtime_lock(
        settings.processed_log_file,
        lock_name=lock_name,
        owner=lock_owner,
        ttl_seconds=settings.run_lock_ttl_seconds,
    ):
        current_owner = get_runtime_lock_owner(settings.processed_log_file, lock_name)
        logger.info("Skipping update cycle because another run is in progress (owner=%s).", current_owner)
        _record_cycle_status(
            settings,
            status="locked",
            error=f"another run in progress (owner={current_owner})",
        )
        service_state["lock_status"] = "locked"
        service_state["lock_owner"] = current_owner
        _persist_cycle_service_state(settings, service_state)
        return {"status": "locked", "lock_owner": current_owner}

    try:
        logger.info("Starting update cycle.")
        strava_client = StravaClient(settings)

        activities = _run_required_call(
            settings,
            "strava.get_recent_activities",
            strava_client.get_recent_activities,
            service_state=service_state,
            per_page=5,
        )
        if not activities:
            logger.info("No Strava activities found.")
            result = {"status": "no_activities"}
            _record_cycle_status(settings, status=result["status"])
            return result

        latest, selected, selection_result = _select_strava_activity(
            settings,
            activities,
            force_update=force_update,
            activity_id=activity_id,
        )
        if selection_result is not None:
            logger.info("No unprocessed activities in latest %s items.", len(activities))
            _record_cycle_status(
                settings,
                status=selection_result["status"],
                activity_id=selection_result["activity_id"],
            )
            return selection_result
        if selected is None:
            raise RuntimeError("Failed to resolve target activity.")

        selected_activity_id = int(selected["id"])
        detailed_activity = _run_required_call(
            settings,
            "strava.get_activity_details",
            strava_client.get_activity_details,
            selected_activity_id,
            service_state=service_state,
        )
        selected.setdefault("start_date", detailed_activity.get("start_date"))

        if selected_activity_id != int(latest["id"]):
            logger.info(
                "Selected activity %s (latest is %s).",
                selected_activity_id,
                int(latest["id"]),
            )

        _local_tz, now_local, now_utc, year_start = _resolve_cycle_time_context(settings)

        strava_activities = _run_required_call(
            settings,
            "strava.get_activities_after",
            strava_client.get_activities_after,
            year_start,
            service_state=service_state,
        )

        smashrun_context = _collect_smashrun_context(
            settings,
            detailed_activity,
            selected_activity_id=selected_activity_id,
            latest_activity_id=int(latest["id"]),
            now_utc=now_utc,
            service_state=service_state,
        )
        longest_streak = smashrun_context["longest_streak"]
        notables = smashrun_context["notables"]
        latest_elevation_feet = smashrun_context["latest_elevation_feet"]
        smashrun_elevation_totals = smashrun_context["smashrun_elevation_totals"]
        smashrun_activity_record = smashrun_context["smashrun_activity_record"]
        smashrun_stats = smashrun_context["smashrun_stats"]
        smashrun_badges = smashrun_context["smashrun_badges"]

        garmin_client = _get_garmin_client(settings)
        training = _get_garmin_metrics(garmin_client)
        garmin_period_fallback = _run_service_call(
            settings,
            "garmin.period_fallback",
            period_stats.get_garmin_period_fallback,
            garmin_client,
            now_utc=now_utc,
            timezone_name=settings.timezone,
            service_state=service_state,
            cache_key=f"garmin.period_fallback:{now_local.date().isoformat()}:{settings.timezone}",
            cache_ttl_seconds=settings.service_cache_ttl_seconds,
        )

        period_summaries = period_stats.get_period_stats(
            strava_activities,
            smashrun_elevation_totals,
            now_utc,
            timezone_name=settings.timezone,
            garmin_period_fallback=garmin_period_fallback,
        )

        intervals_payload = None
        if settings.enable_intervals:
            intervals_payload = _run_service_call(
                settings,
                "intervals.activity",
                get_intervals_activity_data,
                settings.intervals_user_id,
                settings.intervals_api_key,
                service_state=service_state,
                cache_key=f"intervals.activity:{selected_activity_id}",
                cache_ttl_seconds=settings.service_cache_ttl_seconds,
            )

        weather_context = _collect_weather_context(
            settings,
            detailed_activity,
            selected_activity_id=selected_activity_id,
            service_state=service_state,
        )
        weather_details = weather_context["weather_details"]
        misery_index = weather_context["misery_index"]
        misery_desc = weather_context["misery_desc"]
        aqi = weather_context["aqi"]
        aqi_desc = weather_context["aqi_desc"]

        crono_summary, crono_line = _collect_crono_context(
            settings,
            detailed_activity,
            selected_activity_id=selected_activity_id,
            service_state=service_state,
        )

        description_context = _build_description_context(
            detailed_activity=detailed_activity,
            training=training,
            intervals_payload=intervals_payload,
            week=period_summaries["week"],
            month=period_summaries["month"],
            year=period_summaries["year"],
            longest_streak=longest_streak,
            notables=notables,
            latest_elevation_feet=latest_elevation_feet,
            misery_index=misery_index,
            misery_index_description=misery_desc,
            air_quality_index=aqi,
            aqi_description=aqi_desc,
            crono_line=crono_line,
            crono_summary=crono_summary,
            weather_payload=weather_details,
            timezone_name=settings.timezone,
            smashrun_activity=smashrun_activity_record,
            smashrun_stats=smashrun_stats,
            smashrun_badges=smashrun_badges,
            garmin_period_fallback=garmin_period_fallback,
        )

        selected_profile = _select_activity_profile(settings, detailed_activity)
        profile_id = str(selected_profile.get("profile_id") or "default")
        description_context["profile"] = {
            "id": profile_id,
            "label": str(selected_profile.get("profile_label") or profile_id.title()),
            "reasons": selected_profile.get("reasons") or [],
        }

        render_result = render_with_active_template(
            settings,
            description_context,
            profile_id=profile_id,
        )
        if render_result["ok"]:
            description = str(render_result["description"])
        else:
            logger.error("Template render failed: %s", render_result.get("error"))
            description = _build_description(
                detailed_activity=detailed_activity,
                training=training,
                intervals_payload=intervals_payload,
                week=period_summaries["week"],
                month=period_summaries["month"],
                year=period_summaries["year"],
                longest_streak=longest_streak,
                notables=notables,
                latest_elevation_feet=latest_elevation_feet,
                misery_index=misery_index,
                misery_index_description=misery_desc,
                air_quality_index=aqi,
                aqi_description=aqi_desc,
                crono_line=crono_line,
            )

        _run_required_call(
            settings,
            "strava.update_activity",
            strava_client.update_activity,
            selected_activity_id,
            _profile_activity_update_payload(profile_id, detailed_activity, description),
            service_state=service_state,
        )

        payload = {
            "updated_at_utc": now_utc.isoformat(),
            "activity_id": selected_activity_id,
            "activity_start_date": selected.get("start_date"),
            "description": description,
            "source": "standard",
            "period_stats": period_summaries,
            "weather": weather_details,
            "template_context": description_context,
            "service_calls": service_state,
            "profile_match": {
                "profile_id": profile_id,
                "profile_label": str(selected_profile.get("profile_label") or profile_id.title()),
                "reasons": selected_profile.get("reasons") or [],
                "evaluated_at_utc": now_utc.isoformat(),
            },
            "template_render": {
                "ok": render_result.get("ok"),
                "is_custom_template": render_result.get("is_custom_template"),
                "fallback_used": render_result.get("fallback_used"),
                "template_path": render_result.get("template_path"),
                "profile_id": render_result.get("profile_id", profile_id),
                "profile_label": render_result.get("profile_label"),
                "error": render_result.get("error"),
                "fallback_reason": render_result.get("fallback_reason"),
            },
        }
        mark_activity_processed(settings.processed_log_file, selected_activity_id)
        write_json(settings.latest_json_file, payload)

        logger.info("Activity %s updated successfully.", selected_activity_id)
        result = {"status": "updated", "activity_id": selected_activity_id}
        _record_cycle_status(
            settings,
            status=result["status"],
            activity_id=selected_activity_id,
        )
        return result
    except Exception as exc:
        _record_cycle_status(
            settings,
            status="error",
            error=str(exc),
            activity_id=selected_activity_id,
        )
        raise
    finally:
        service_state["ended_at_utc"] = datetime.now(timezone.utc).isoformat()
        _persist_cycle_service_state(settings, service_state)
        release_runtime_lock(
            settings.processed_log_file,
            lock_name=lock_name,
            owner=lock_owner,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Update Strava activity description with stats.")
    parser.add_argument("-f", "--force", action="store_true", help="Force update the most recent activity.")
    parser.add_argument(
        "-a",
        "--activity-id",
        type=int,
        default=None,
        help="Rerun update for a specific Strava activity ID.",
    )
    args = parser.parse_args()
    run_once(force_update=args.force, activity_id=args.activity_id)


if __name__ == "__main__":
    main()
