from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import Settings
from .pipeline_context_collectors import (
    collect_crono_context as _collect_crono_context_impl,
    collect_smashrun_context as _collect_smashrun_context_impl,
    collect_weather_context as _collect_weather_context_impl,
)
from .numeric_utils import (
    as_float as _shared_as_float,
    meters_to_feet_int as _shared_meters_to_feet_int,
    mps_to_mph as _shared_mps_to_mph,
)
from .stat_modules import beers_earned, period_stats
from .stat_modules.intervals_data import get_intervals_activity_data
from .stat_modules.garmin_metrics import default_metrics as default_garmin_metrics
from .stat_modules.garmin_metrics import fetch_training_status_and_scores
from .stat_modules.garmin_metrics import get_activity_context_for_strava_activity
from .storage import (
    acquire_runtime_lock,
    claim_activity_job,
    complete_activity_job_run,
    delete_runtime_value,
    enqueue_activity_job,
    get_runtime_lock_owner,
    get_runtime_value,
    get_runtime_values,
    is_activity_processed,
    mark_activity_processed,
    record_activity_output,
    register_activity_discovery,
    release_runtime_lock,
    start_activity_job_run,
    set_runtime_value,
    set_runtime_values,
    write_config_snapshot,
    write_json,
)
from .template_profiles import get_template_profile, get_working_template_profile, list_template_profiles
from .template_rendering import render_with_active_template
from .strava_client import StravaClient, get_gap_speed_mps, mps_to_pace


logger = logging.getLogger(__name__)


PERIOD_STATS_ACTIVITIES_CACHE_KEY = "cycle.period_stats.activities_cache"
DEFAULT_STRAVA_PERIOD_STATS_INCREMENTAL_OVERLAP_HOURS = 48


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
    updates: dict[str, Any] = {
        "cycle.last_status": status,
        "cycle.last_status_at_utc": now_iso,
    }
    if activity_id is not None:
        updates["cycle.last_activity_id"] = activity_id
    if status in {"updated", "already_processed", "no_activities"}:
        updates["cycle.last_success_at_utc"] = now_iso
        if error:
            updates["cycle.last_error"] = error
        else:
            delete_runtime_value(settings.processed_log_file, "cycle.last_error")
    elif error:
        updates["cycle.last_error"] = error
        updates["cycle.last_error_at_utc"] = now_iso
    set_runtime_values(settings.processed_log_file, updates)


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
    updates = _service_counter_updates(settings, service_name, {key_suffix: by})
    if updates:
        set_runtime_values(settings.processed_log_file, updates)


def _service_counter_updates(
    settings: Settings,
    service_name: str,
    increments: dict[str, int],
) -> dict[str, int]:
    runtime_increments: dict[str, int] = {}
    for key_suffix, by in increments.items():
        try:
            delta = int(by)
        except (TypeError, ValueError):
            continue
        if delta == 0:
            continue
        runtime_increments[_service_key(service_name, key_suffix)] = delta
    if not runtime_increments:
        return {}

    existing = get_runtime_values(settings.processed_log_file, list(runtime_increments.keys()))
    updates: dict[str, int] = {}
    for runtime_key, delta in runtime_increments.items():
        current = existing.get(runtime_key, 0)
        try:
            current_val = int(current)
        except (TypeError, ValueError):
            current_val = 0
        updates[runtime_key] = current_val + delta
    return updates


def _record_service_status(
    settings: Settings,
    service_name: str,
    *,
    status: str,
    duration_ms: int | None = None,
    error: str | None = None,
) -> None:
    increments: dict[str, int] = {
        "events_total": 1,
        f"events.{status}": 1,
    }
    now_iso = datetime.now(timezone.utc).isoformat()
    updates: dict[str, Any] = {
        _service_key(service_name, "last_status"): status,
        _service_key(service_name, "last_status_at_utc"): now_iso,
    }
    if duration_ms is not None:
        duration_value = max(0, int(duration_ms))
        increments["duration_count"] = 1
        increments["duration_total_ms"] = duration_value
        updates[_service_key(service_name, "last_duration_ms")] = duration_value
    if error:
        updates[_service_key(service_name, "last_error")] = error
        updates[_service_key(service_name, "last_error_at_utc")] = now_iso
    updates.update(_service_counter_updates(settings, service_name, increments))
    set_runtime_values(settings.processed_log_file, updates)


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
    set_runtime_values(
        settings.processed_log_file,
        {
            _service_key(service_name, "cooldown_until_utc"): datetime.fromtimestamp(
                cooldown_until, tz=timezone.utc
            ).isoformat(),
        },
    )
    return delay


def _reset_service_cooldown(settings: Settings, service_name: str) -> None:
    delete_runtime_value(settings.processed_log_file, _service_key(service_name, "cooldown_until_utc"))
    set_runtime_values(
        settings.processed_log_file,
        {
            _service_key(service_name, "failures"): 0,
            _service_key(service_name, "last_success_utc"): datetime.now(timezone.utc).isoformat(),
        },
    )


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


def _coerce_activity_id_str(value: Any) -> str:
    if isinstance(value, bool) or value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        if value.is_integer():
            return str(int(value))
        return str(value).strip()
    text = str(value).strip()
    if not text:
        return ""
    if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
        return str(int(text))
    if text.endswith(".0") and text[:-2].isdigit():
        return str(int(text[:-2]))
    return text


def _coerce_garmin_badge_records(value: Any, *, max_items: int = 250) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        badge_name = str(
            item.get("badgeName")
            or item.get("badgeTypeName")
            or item.get("name")
            or item.get("badge_name")
            or ""
        ).strip()
        if not badge_name:
            continue
        normalized.append(
            {
                "badgeName": badge_name,
                "badgeAssocType": str(item.get("badgeAssocType") or item.get("badge_assoc_type") or "").strip(),
                "badgeAssocDataId": _coerce_activity_id_str(
                    item.get("badgeAssocDataId") or item.get("badge_assoc_data_id")
                ),
            }
        )
        if len(normalized) >= max_items:
            break
    return normalized


def _extract_activity_garmin_badges(
    garmin_badge_records: list[dict[str, Any]],
    *,
    garmin_activity_id: Any,
    max_items: int = 20,
) -> list[str]:
    activity_id = _coerce_activity_id_str(garmin_activity_id)
    if not activity_id:
        return []
    matches: list[str] = []
    seen: set[str] = set()
    for badge in _coerce_garmin_badge_records(garmin_badge_records, max_items=500):
        assoc_type = _normalize_activity_type_key(badge.get("badgeAssocType"))
        assoc_id = _coerce_activity_id_str(badge.get("badgeAssocDataId"))
        if assoc_type != "activityid" or assoc_id != activity_id:
            continue
        badge_name = str(badge.get("badgeName") or "").strip()
        if not badge_name:
            continue
        dedupe_key = badge_name.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        matches.append(badge_name)
        if len(matches) >= max_items:
            break
    return matches


def _smashrun_badge_title(item: dict[str, Any]) -> str:
    return str(
        item.get("badgeName")
        or item.get("badgeTypeName")
        or item.get("name")
        or item.get("title")
        or ""
    ).strip()


def _extract_smashrun_badge_assoc_ids(item: dict[str, Any]) -> set[str]:
    assoc_type = _normalize_activity_type_key(
        item.get("badgeAssocType")
        or item.get("badge_assoc_type")
        or item.get("assocType")
        or item.get("assoc_type")
        or ""
    )
    if assoc_type and assoc_type not in {
        "activity",
        "activityid",
        "run",
        "runid",
        "stravaactivity",
        "stravaactivityid",
        "externalactivity",
        "externalactivityid",
    }:
        return set()

    scalar_keys = (
        "activityId",
        "activity_id",
        "activityID",
        "smashrunActivityId",
        "smashrun_activity_id",
        "stravaActivityId",
        "strava_activity_id",
        "externalActivityId",
        "external_activity_id",
        "runId",
        "run_id",
        "badgeAssocDataId",
        "badge_assoc_data_id",
    )
    list_keys = (
        "activityIds",
        "activity_ids",
        "smashrunActivityIds",
        "smashrun_activity_ids",
        "stravaActivityIds",
        "strava_activity_ids",
        "externalActivityIds",
        "external_activity_ids",
        "runIds",
        "run_ids",
        "activities",
        "runs",
        "badgeActivities",
        "badge_activities",
        "associatedActivities",
        "associated_activities",
    )
    nested_keys = (
        "association",
        "associations",
        "badgeAssociation",
        "badgeAssociations",
        "activity",
        "run",
    )

    assoc_ids: set[str] = set()

    def _add_id(value: Any) -> None:
        normalized = _coerce_activity_id_str(value)
        if normalized:
            assoc_ids.add(normalized)

    def _collect_from_value(value: Any, *, allow_generic_id: bool = False) -> None:
        if isinstance(value, dict):
            for key in scalar_keys:
                if key in value:
                    _add_id(value.get(key))
            if allow_generic_id and "id" in value:
                _add_id(value.get("id"))
            return
        if isinstance(value, (list, tuple, set)):
            for row in value:
                _collect_from_value(row, allow_generic_id=True)
            return
        _add_id(value)

    for key in scalar_keys:
        if key in item:
            _add_id(item.get(key))
    for key in list_keys:
        if key in item:
            _collect_from_value(item.get(key), allow_generic_id=True)
    for key in nested_keys:
        if key in item:
            _collect_from_value(item.get(key), allow_generic_id=True)

    return assoc_ids


def _extract_activity_smashrun_badges(
    smashrun_badge_records: list[dict[str, Any]],
    *,
    smashrun_activity_id: Any,
    strava_activity_id: Any = None,
    max_items: int = 20,
) -> list[str]:
    target_ids = {
        _coerce_activity_id_str(smashrun_activity_id),
        _coerce_activity_id_str(strava_activity_id),
    }
    target_ids.discard("")
    if not target_ids:
        return []

    matches: list[str] = []
    seen: set[str] = set()
    for item in smashrun_badge_records:
        if not isinstance(item, dict):
            continue
        badge_name = _smashrun_badge_title(item)
        if not badge_name:
            continue
        assoc_ids = _extract_smashrun_badge_assoc_ids(item)
        if not assoc_ids or target_ids.isdisjoint(assoc_ids):
            continue
        dedupe_key = badge_name.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        matches.append(badge_name)
        if len(matches) >= max_items:
            break
    return matches


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


def _is_strength_like(activity: dict[str, Any]) -> bool:
    raw_sport_type = str(activity.get("sport_type") or activity.get("type") or "").strip().lower()
    if raw_sport_type in {"weighttraining", "weight training", "workout"}:
        return True

    text = _text_blob(activity)
    has_strength_keyword = any(
        keyword in text for keyword in ("strength", "weight training", "workout", "lifting")
    )
    if not has_strength_keyword:
        return False

    distance = _distance_miles(activity)
    start = _start_latlng(activity)
    no_gps = start is None
    trainer = bool(activity.get("trainer"))
    moving_time_seconds = _as_float(activity.get("moving_time")) or 0.0
    return no_gps and trainer and distance <= 0.2 and moving_time_seconds <= 1800


def _normalize_activity_type_key(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return "".join(ch for ch in raw if ch.isalnum())


def _is_incline_treadmill_named_activity(
    activity: dict[str, Any],
    training: dict[str, Any] | None = None,
) -> bool:
    texts = [_text_blob(activity)]
    garmin_type_key = ""
    if isinstance(training, dict) and bool(training.get("_garmin_activity_aligned")):
        garmin_last = training.get("garmin_last_activity")
        if isinstance(garmin_last, dict):
            texts.append(str(garmin_last.get("activity_name") or "").strip().lower())
            texts.append(str(garmin_last.get("activity_type") or "").strip().lower())
            garmin_type_key = _normalize_activity_type_key(garmin_last.get("activity_type"))

    for text in texts:
        normalized = " ".join(str(text or "").split())
        if "treadmill incline" in normalized or "incline treadmill" in normalized:
            return True

    return garmin_type_key in {"treadmillincline", "inclinetreadmill"}


def _training_indicates_strength(training: dict[str, Any] | None) -> bool:
    def _is_positive_numeric(value: Any) -> bool:
        parsed = _as_float(value)
        return parsed is not None and parsed > 0

    if not isinstance(training, dict):
        return False
    if not bool(training.get("_garmin_activity_aligned")):
        return False

    garmin_last = training.get("garmin_last_activity")
    if not isinstance(garmin_last, dict):
        return False

    activity_type_key = _normalize_activity_type_key(garmin_last.get("activity_type"))
    if activity_type_key in {
        "strength",
        "strengthtraining",
        "weighttraining",
        "weightlifting",
        "strengthworkout",
    }:
        return True

    total_sets = garmin_last.get("total_sets")
    active_sets = garmin_last.get("active_sets")
    total_reps = garmin_last.get("total_reps")
    if any(_is_positive_numeric(value) for value in (total_sets, active_sets, total_reps)):
        return True

    summary_sets = garmin_last.get("strength_summary_sets")
    if isinstance(summary_sets, list) and summary_sets:
        return True

    exercise_sets = garmin_last.get("exercise_sets")
    if isinstance(exercise_sets, list):
        for row in exercise_sets:
            if not isinstance(row, dict):
                continue
            reps = row.get("reps")
            if _is_positive_numeric(reps):
                return True
    return False


def _incline_treadmill_match_reasons(
    activity: dict[str, Any],
    training: dict[str, Any] | None = None,
) -> list[str]:
    raw_sport_type = str(activity.get("sport_type") or activity.get("type") or "").strip()
    sport_type = raw_sport_type.lower()
    if _is_strength_like(activity) or _training_indicates_strength(training):
        return []
    if not _is_incline_treadmill_named_activity(activity, training):
        return []
    text = _text_blob(activity)
    start = _start_latlng(activity)
    no_gps = start is None
    trainer = bool(activity.get("trainer"))
    external_id = str(activity.get("external_id") or "").strip().lower()
    device_name = str(activity.get("device_name") or "").strip().lower()
    distance = _distance_miles(activity)
    moving_time = _to_int(activity.get("moving_time")) or 0

    # Keep this matcher specific enough to avoid reclassifying short non-treadmill trainer sessions.
    meets_indoor_shape = (
        no_gps
        and trainer
        and sport_type in {"run", "walk", "virtualrun"}
        and distance >= 0.25
        and moving_time >= 300
    )
    has_treadmill_hint = "treadmill" in text
    has_device_hint = external_id.startswith("garmin_ping_") or "garmin" in device_name

    reasons: list[str] = []
    reasons.append("incline treadmill activity name")
    if has_treadmill_hint:
        reasons.append("treadmill keyword")
    if sport_type == "virtualrun" and no_gps:
        reasons.append("sport_type=VirtualRun + no GPS")
    if meets_indoor_shape and has_device_hint:
        reasons.append("garmin indoor run/walk + no GPS")
    if meets_indoor_shape and external_id.startswith("garmin_ping_"):
        reasons.append("garmin_ping external_id + no GPS")
    if meets_indoor_shape and _is_treadmill(activity):
        reasons.append("trainer/no-gps treadmill shape")
    return reasons


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


def _duration_to_seconds(value: Any) -> int | None:
    if isinstance(value, (int, float)):
        return max(0, int(value))
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.isdigit():
        return max(0, int(text))
    parts = text.split(":")
    if len(parts) not in {2, 3}:
        return None
    try:
        numbers = [int(part) for part in parts]
    except ValueError:
        return None
    if len(numbers) == 2:
        minutes, seconds = numbers
        if minutes < 0 or seconds < 0:
            return None
        return minutes * 60 + seconds
    hours, minutes, seconds = numbers
    if hours < 0 or minutes < 0 or seconds < 0:
        return None
    return hours * 3600 + minutes * 60 + seconds


def _activity_for_profile_preview(context: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    activity: dict[str, Any] = {}
    training: dict[str, Any] | None = None

    raw = context.get("raw")
    if isinstance(raw, dict):
        raw_activity = raw.get("activity")
        if isinstance(raw_activity, dict):
            activity.update(raw_activity)
        raw_training = raw.get("training")
        if isinstance(raw_training, dict):
            training = raw_training

    context_activity = context.get("activity")
    if isinstance(context_activity, dict):
        for key, value in context_activity.items():
            activity.setdefault(str(key), value)

    if "distance" not in activity:
        distance_miles = _as_float(activity.get("distance_miles"))
        if distance_miles is not None:
            activity["distance"] = distance_miles * 1609.34

    if "total_elevation_gain" not in activity:
        elevation_feet = _as_float(activity.get("elevation_feet"))
        if elevation_feet is not None:
            activity["total_elevation_gain"] = elevation_feet / 3.28084

    moving_seconds = _duration_to_seconds(activity.get("moving_time"))
    if moving_seconds is not None:
        activity["moving_time"] = moving_seconds

    return activity, training


_CRITERIA_META_KEYS = {
    "kind",
    "description",
    "label",
    "name",
    "version",
    "notes",
}


def _criteria_has_executable_rules(criteria: dict[str, Any] | None) -> bool:
    if not isinstance(criteria, dict):
        return False
    for key, value in criteria.items():
        if key in _CRITERIA_META_KEYS:
            continue
        if key in {"all_of", "any_of", "none_of"}:
            if isinstance(value, dict):
                return True
            if isinstance(value, (list, tuple)):
                return any(isinstance(item, dict) for item in value)
            continue
        return True
    return False


def _criteria_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        numeric = int(value)
        if numeric in {0, 1}:
            return bool(numeric)
        return None
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return None


def _criteria_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple)):
        items: list[str] = []
        for item in value:
            text = str(item or "").strip()
            if text:
                items.append(text)
        return items
    return []


def _criteria_clauses(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, (list, tuple)):
        return [item for item in value if isinstance(item, dict)]
    return []


def _criteria_weekdays(value: Any) -> list[int]:
    mapping = {
        "mon": 0,
        "monday": 0,
        "tue": 1,
        "tues": 1,
        "tuesday": 1,
        "wed": 2,
        "wednesday": 2,
        "thu": 3,
        "thur": 3,
        "thurs": 3,
        "thursday": 3,
        "fri": 4,
        "friday": 4,
        "sat": 5,
        "saturday": 5,
        "sun": 6,
        "sunday": 6,
    }
    days: list[int] = []
    for item in _criteria_string_list(value):
        normalized = str(item or "").strip().lower()
        if normalized in mapping and mapping[normalized] not in days:
            days.append(mapping[normalized])
    return days


def _criteria_time_minutes(value: Any) -> int | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    parts = text.split(":")
    if len(parts) != 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return None
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return hour * 60 + minute


def _normalized_strava_tags(activity: dict[str, Any]) -> set[str]:
    tags: set[str] = set()
    sport_type = _normalize_activity_type_key(activity.get("sport_type") or activity.get("type"))
    workout_type = _to_int(activity.get("workout_type"))
    if sport_type:
        tags.add(sport_type)
    if bool(activity.get("commute")):
        tags.add("commute")
    if bool(activity.get("trainer")):
        tags.add("trainer")
    if _is_treadmill(activity):
        tags.add("treadmill")
    if workout_type == 1:
        tags.add("race")
    if workout_type == 2:
        tags.add("long_run")
    if sport_type == "trailrun":
        tags.add("trail")
    if sport_type == "walk":
        tags.add("walk")
    if sport_type in {"weighttraining", "weighttraining", "workout"}:
        tags.add("strength")
    return tags


def _activity_match_datetime(activity: dict[str, Any], settings: Settings) -> datetime | None:
    local_raw = activity.get("start_date_local")
    if isinstance(local_raw, str) and local_raw.strip():
        text = local_raw.strip()
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            parsed = None
        if parsed is not None:
            if parsed.tzinfo is None:
                try:
                    return parsed.replace(tzinfo=ZoneInfo(settings.timezone))
                except ZoneInfoNotFoundError:
                    return parsed.replace(tzinfo=timezone.utc)
            return parsed

    utc_raw = activity.get("start_date")
    if isinstance(utc_raw, str) and utc_raw.strip():
        try:
            parsed_utc = datetime.fromisoformat(utc_raw.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed_utc.tzinfo is None:
            parsed_utc = parsed_utc.replace(tzinfo=timezone.utc)
        try:
            return parsed_utc.astimezone(ZoneInfo(settings.timezone))
        except ZoneInfoNotFoundError:
            return parsed_utc.astimezone(timezone.utc)
    return None


def _criteria_match_reasons(
    criteria: dict[str, Any],
    activity: dict[str, Any],
    settings: Settings,
    training: dict[str, Any] | None = None,
) -> list[str]:
    reasons: list[str] = []
    evaluated = False

    all_of = _criteria_clauses(criteria.get("all_of"))
    if "all_of" in criteria:
        evaluated = True
        if not all_of:
            return []
        for clause in all_of:
            clause_reasons = _criteria_match_reasons(clause, activity, settings, training=training)
            if not clause_reasons:
                return []
            reasons.extend(clause_reasons)

    any_of = _criteria_clauses(criteria.get("any_of"))
    if "any_of" in criteria:
        evaluated = True
        if not any_of:
            return []
        any_reasons: list[str] = []
        for clause in any_of:
            clause_reasons = _criteria_match_reasons(clause, activity, settings, training=training)
            if clause_reasons:
                any_reasons = clause_reasons
                break
        if not any_reasons:
            return []
        reasons.extend(any_reasons)

    none_of = _criteria_clauses(criteria.get("none_of"))
    if "none_of" in criteria:
        evaluated = True
        if not none_of:
            return []
        for clause in none_of:
            clause_reasons = _criteria_match_reasons(clause, activity, settings, training=training)
            if clause_reasons:
                return []
        reasons.append("none_of clauses clear")

    raw_sport_type = str(activity.get("sport_type") or activity.get("type") or "").strip()
    sport_type = _normalize_activity_type_key(raw_sport_type)
    workout_type = _as_float(activity.get("workout_type"))
    treadmill = _is_treadmill(activity)
    strength_like = _is_strength_like(activity) or _training_indicates_strength(training)
    distance = _distance_miles(activity)
    gain_ft = _elevation_gain_feet(activity)
    gain_per_mile = gain_ft / distance if distance > 0 else 0.0
    moving_raw = activity.get("moving_time")
    moving_seconds = _as_float(moving_raw)
    if moving_seconds is None:
        parsed_seconds = _duration_to_seconds(moving_raw)
        moving_seconds = float(parsed_seconds) if parsed_seconds is not None else 0.0
    start = _start_latlng(activity)
    has_gps = bool(activity.get("has_gps")) or start is not None
    text = _text_blob(activity)
    activity_name = str(activity.get("name") or "").strip().lower()
    external_id = str(activity.get("external_id") or "").strip().lower()
    device_name = str(activity.get("device_name") or "").strip().lower()
    strava_tags = _normalized_strava_tags(activity)
    match_dt = _activity_match_datetime(activity, settings)
    match_minutes = (match_dt.hour * 60 + match_dt.minute) if isinstance(match_dt, datetime) else None
    match_weekday = match_dt.weekday() if isinstance(match_dt, datetime) else None

    if "sport_type" in criteria:
        evaluated = True
        expected_types = {
            _normalize_activity_type_key(item)
            for item in _criteria_string_list(criteria.get("sport_type"))
            if item
        }
        if not expected_types or sport_type not in expected_types:
            return []
        reasons.append(f"sport_type={raw_sport_type or 'unknown'}")

    if "workout_type" in criteria:
        evaluated = True
        expected = _as_float(criteria.get("workout_type"))
        if expected is None or workout_type is None or int(round(workout_type)) != int(round(expected)):
            return []
        reasons.append(f"workout_type={int(round(workout_type))}")

    if "trainer" in criteria:
        evaluated = True
        expected = _criteria_bool(criteria.get("trainer"))
        actual = bool(activity.get("trainer"))
        if expected is None or actual != expected:
            return []
        reasons.append(f"trainer={str(actual).lower()}")

    if "commute" in criteria:
        evaluated = True
        expected = _criteria_bool(criteria.get("commute"))
        actual = bool(activity.get("commute"))
        if expected is None or actual != expected:
            return []
        reasons.append(f"commute={str(actual).lower()}")

    if "has_gps" in criteria:
        evaluated = True
        expected = _criteria_bool(criteria.get("has_gps"))
        if expected is None or has_gps != expected:
            return []
        reasons.append(f"has_gps={str(has_gps).lower()}")

    if "treadmill" in criteria:
        evaluated = True
        expected = _criteria_bool(criteria.get("treadmill"))
        if expected is None or treadmill != expected:
            return []
        reasons.append(f"treadmill={str(treadmill).lower()}")

    if "strength_like" in criteria:
        evaluated = True
        expected = _criteria_bool(criteria.get("strength_like"))
        if expected is None or strength_like != expected:
            return []
        reasons.append(f"strength_like={str(strength_like).lower()}")

    if "distance_miles_min" in criteria:
        evaluated = True
        minimum = _as_float(criteria.get("distance_miles_min"))
        if minimum is None or distance < minimum:
            return []
        reasons.append(f"distance={distance:.2f}mi >= {minimum:.2f}mi")

    if "distance_miles_max" in criteria:
        evaluated = True
        maximum = _as_float(criteria.get("distance_miles_max"))
        if maximum is None or distance > maximum:
            return []
        reasons.append(f"distance={distance:.2f}mi <= {maximum:.2f}mi")

    if "moving_time_seconds_min" in criteria:
        evaluated = True
        minimum = _as_float(criteria.get("moving_time_seconds_min"))
        if minimum is None or moving_seconds < minimum:
            return []
        reasons.append(f"moving_time={moving_seconds:.0f}s >= {minimum:.0f}s")

    if "moving_time_seconds_max" in criteria:
        evaluated = True
        maximum = _as_float(criteria.get("moving_time_seconds_max"))
        if maximum is None or moving_seconds > maximum:
            return []
        reasons.append(f"moving_time={moving_seconds:.0f}s <= {maximum:.0f}s")

    if "gain_per_mile_ft_min" in criteria:
        evaluated = True
        minimum = _as_float(criteria.get("gain_per_mile_ft_min"))
        if minimum is None or gain_per_mile < minimum:
            return []
        reasons.append(f"gain_per_mile={gain_per_mile:.0f}ft >= {minimum:.0f}ft")

    if "gain_per_mile_ft_max" in criteria:
        evaluated = True
        maximum = _as_float(criteria.get("gain_per_mile_ft_max"))
        if maximum is None or gain_per_mile > maximum:
            return []
        reasons.append(f"gain_per_mile={gain_per_mile:.0f}ft <= {maximum:.0f}ft")

    if "text_contains" in criteria:
        evaluated = True
        tokens = [token.lower() for token in _criteria_string_list(criteria.get("text_contains"))]
        if not tokens or not all(token in text for token in tokens):
            return []
        reasons.append("text_contains matched")

    if "text_contains_any" in criteria:
        evaluated = True
        tokens = [token.lower() for token in _criteria_string_list(criteria.get("text_contains_any"))]
        if not tokens or not any(token in text for token in tokens):
            return []
        reasons.append("text_contains_any matched")

    if "name_contains" in criteria:
        evaluated = True
        tokens = [token.lower() for token in _criteria_string_list(criteria.get("name_contains"))]
        if not tokens or not all(token in activity_name for token in tokens):
            return []
        reasons.append("name_contains matched")

    if "name_contains_any" in criteria:
        evaluated = True
        tokens = [token.lower() for token in _criteria_string_list(criteria.get("name_contains_any"))]
        if not tokens or not any(token in activity_name for token in tokens):
            return []
        reasons.append("name_contains_any matched")

    if "text_not_contains" in criteria:
        evaluated = True
        tokens = [token.lower() for token in _criteria_string_list(criteria.get("text_not_contains"))]
        if not tokens or any(token in text for token in tokens):
            return []
        reasons.append("text_not_contains clear")

    if "name_not_contains" in criteria:
        evaluated = True
        tokens = [token.lower() for token in _criteria_string_list(criteria.get("name_not_contains"))]
        if not tokens or any(token in activity_name for token in tokens):
            return []
        reasons.append("name_not_contains clear")

    if "external_id_contains" in criteria:
        evaluated = True
        tokens = [token.lower() for token in _criteria_string_list(criteria.get("external_id_contains"))]
        if not tokens or not all(token in external_id for token in tokens):
            return []
        reasons.append("external_id_contains matched")

    if "device_name_contains" in criteria:
        evaluated = True
        tokens = [token.lower() for token in _criteria_string_list(criteria.get("device_name_contains"))]
        if not tokens or not all(token in device_name for token in tokens):
            return []
        reasons.append("device_name_contains matched")

    if "strava_tags_any" in criteria:
        evaluated = True
        expected_tags = {_normalize_activity_type_key(item) for item in _criteria_string_list(criteria.get("strava_tags_any")) if item}
        if not expected_tags or not (strava_tags & expected_tags):
            return []
        reasons.append("strava_tags_any matched")

    if "strava_tags_all" in criteria:
        evaluated = True
        expected_tags = {_normalize_activity_type_key(item) for item in _criteria_string_list(criteria.get("strava_tags_all")) if item}
        if not expected_tags or not expected_tags.issubset(strava_tags):
            return []
        reasons.append("strava_tags_all matched")

    if "moving_time_minutes_min" in criteria:
        evaluated = True
        minimum = _as_float(criteria.get("moving_time_minutes_min"))
        if minimum is None or moving_seconds < minimum * 60.0:
            return []
        reasons.append(f"moving_time={moving_seconds / 60.0:.0f}min >= {minimum:.0f}min")

    if "moving_time_minutes_max" in criteria:
        evaluated = True
        maximum = _as_float(criteria.get("moving_time_minutes_max"))
        if maximum is None or moving_seconds > maximum * 60.0:
            return []
        reasons.append(f"moving_time={moving_seconds / 60.0:.0f}min <= {maximum:.0f}min")

    if "day_of_week_in" in criteria:
        evaluated = True
        expected_days = _criteria_weekdays(criteria.get("day_of_week_in"))
        if match_weekday is None or not expected_days or match_weekday not in expected_days:
            return []
        reasons.append(f"day_of_week={match_weekday}")

    if "time_of_day_after" in criteria:
        evaluated = True
        minimum_minutes = _criteria_time_minutes(criteria.get("time_of_day_after"))
        if minimum_minutes is None or match_minutes is None or match_minutes < minimum_minutes:
            return []
        reasons.append(f"time_of_day={match_minutes} >= {minimum_minutes}")

    if "time_of_day_before" in criteria:
        evaluated = True
        maximum_minutes = _criteria_time_minutes(criteria.get("time_of_day_before"))
        if maximum_minutes is None or match_minutes is None or match_minutes > maximum_minutes:
            return []
        reasons.append(f"time_of_day={match_minutes} <= {maximum_minutes}")

    if "start_geofence" in criteria:
        evaluated = True
        geofence = criteria.get("start_geofence")
        if not isinstance(geofence, dict):
            return []
        if start is None:
            return []
        latitude = _as_float(geofence.get("latitude"))
        longitude = _as_float(geofence.get("longitude"))
        radius_miles = _as_float(geofence.get("radius_miles"))
        mode = str(geofence.get("mode") or "within").strip().lower()
        if latitude is None or longitude is None or radius_miles is None or radius_miles < 0:
            return []
        distance_to_center = _haversine_miles(start[0], start[1], latitude, longitude)
        if mode == "within":
            if distance_to_center > radius_miles:
                return []
            reasons.append(f"start_geofence within {radius_miles:.2f}mi")
        elif mode == "outside":
            if distance_to_center <= radius_miles:
                return []
            reasons.append(f"start_geofence outside {radius_miles:.2f}mi")
        else:
            return []

    if "home_distance_miles_max" in criteria or "home_distance_miles_min" in criteria:
        evaluated = True
        if start is None or settings.home_latitude is None or settings.home_longitude is None:
            return []
        home_distance = _haversine_miles(start[0], start[1], settings.home_latitude, settings.home_longitude)
        if "home_distance_miles_min" in criteria:
            minimum = _as_float(criteria.get("home_distance_miles_min"))
            if minimum is None or home_distance < minimum:
                return []
            reasons.append(f"home_distance={home_distance:.2f}mi >= {minimum:.2f}mi")
        if "home_distance_miles_max" in criteria:
            maximum = _as_float(criteria.get("home_distance_miles_max"))
            if maximum is None or home_distance > maximum:
                return []
            reasons.append(f"home_distance={home_distance:.2f}mi <= {maximum:.2f}mi")

    if "garmin_activity_type_in" in criteria:
        evaluated = True
        garmin_last = training.get("garmin_last_activity") if isinstance(training, dict) else None
        garmin_type = _normalize_activity_type_key(garmin_last.get("activity_type")) if isinstance(garmin_last, dict) else ""
        expected_types = {
            _normalize_activity_type_key(item)
            for item in _criteria_string_list(criteria.get("garmin_activity_type_in"))
            if item
        }
        if not expected_types or garmin_type not in expected_types:
            return []
        reasons.append(f"garmin_activity_type={garmin_type}")

    if "garmin_connectiq_app_ids_any" in criteria:
        evaluated = True
        garmin_last = training.get("garmin_last_activity") if isinstance(training, dict) else None
        actual_app_ids = set()
        if isinstance(garmin_last, dict):
            app_ids = garmin_last.get("connectiq_app_ids")
            if isinstance(app_ids, list):
                actual_app_ids = {
                    str(item).strip().lower()
                    for item in app_ids
                    if isinstance(item, str) and str(item).strip()
                }
        expected_app_ids = {
            str(item).strip().lower()
            for item in _criteria_string_list(criteria.get("garmin_connectiq_app_ids_any"))
            if str(item).strip()
        }
        if not expected_app_ids or not actual_app_ids.intersection(expected_app_ids):
            return []
        reasons.append("garmin_connectiq_app_id match")

    if not evaluated:
        return []
    return reasons or ["criteria matched"]


def _profile_match_reasons(
    profile_id: str,
    activity: dict[str, Any],
    settings: Settings,
    training: dict[str, Any] | None = None,
    criteria: dict[str, Any] | None = None,
) -> list[str]:
    if _criteria_has_executable_rules(criteria):
        return _criteria_match_reasons(criteria or {}, activity, settings, training=training)

    workout_type = _to_int(activity.get("workout_type"))
    raw_sport_type = str(activity.get("sport_type") or activity.get("type") or "").strip()
    sport_type = raw_sport_type.lower()
    treadmill = _is_treadmill(activity)
    distance = _distance_miles(activity)
    gain_ft = _elevation_gain_feet(activity)
    gain_per_mile = gain_ft / distance if distance > 0 else 0.0
    text = _text_blob(activity)
    start = _start_latlng(activity)

    reasons: list[str] = []
    if profile_id == "incline_treadmill":
        return _incline_treadmill_match_reasons(activity, training)

    if profile_id == "walk":
        if _training_indicates_strength(training):
            return reasons
        if sport_type == "walk" and start is not None and not bool(activity.get("trainer")):
            reasons.append("sport_type=Walk + GPS + trainer=false")
        return reasons

    if profile_id == "treadmill":
        if _is_strength_like(activity) or _training_indicates_strength(training):
            return reasons
        if treadmill:
            moving_time_seconds = _as_float(activity.get("moving_time")) or 0.0
            likely_treadmill = (
                sport_type == "virtualrun"
                or "treadmill" in text
                or distance >= 0.25
                or moving_time_seconds >= 600
            )
            if likely_treadmill:
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

    if profile_id == "strength_training":
        if _training_indicates_strength(training):
            reasons.append("garmin activity indicates strength")
            return reasons
        if sport_type in {"weighttraining", "weight training"}:
            reasons.append(f"sport_type={raw_sport_type or 'WeightTraining'}")
            return reasons
        if sport_type == "workout":
            reasons.append("sport_type=Workout")
            return reasons
        if _is_strength_like(activity):
            reasons.append("strength keyword + indoor no-gps shape")
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


def _select_activity_profile(
    settings: Settings,
    detailed_activity: dict[str, Any],
    training: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
    working_profile: dict[str, Any] | None = None
    try:
        candidate = get_working_template_profile(settings)
        if isinstance(candidate, dict):
            working_profile = candidate
    except Exception as exc:
        logger.warning("Failed to resolve working template profile; default fallback will be used: %s", exc)
    working_profile_id = (
        str(working_profile.get("profile_id") or "").strip().lower()
        if isinstance(working_profile, dict)
        else ""
    )

    for profile in profiles:
        profile_id = str(profile.get("profile_id") or "").strip().lower()
        if profile_id == "default":
            continue
        criteria = profile.get("criteria") if isinstance(profile.get("criteria"), dict) else None
        reasons = _profile_match_reasons(
            profile_id,
            detailed_activity,
            settings,
            training=training,
            criteria=criteria,
        )
        if reasons:
            return {
                "profile_id": profile_id,
                "profile_label": str(profile.get("label") or profile_id.title()),
                "reasons": reasons,
                "working_profile_id": working_profile_id or "default",
                "selection_mode": "criteria_match",
            }
    if working_profile_id and working_profile_id != "default":
        return {
            "profile_id": working_profile_id,
            "profile_label": str(working_profile.get("label") or working_profile_id.title()),
            "reasons": ["working_profile_fallback"],
            "working_profile_id": working_profile_id,
            "selection_mode": "working_profile_fallback",
        }

    if default_profile is not None:
        return {
            "profile_id": "default",
            "profile_label": str(default_profile.get("label") or "Default"),
            "reasons": ["fallback"],
            "working_profile_id": working_profile_id or "default",
            "selection_mode": "default_fallback",
        }

    return {
        "profile_id": "default",
        "profile_label": "Default",
        "reasons": ["fallback"],
        "working_profile_id": working_profile_id or "default",
        "selection_mode": "default_fallback",
    }


def preview_profile_match(
    settings: Settings,
    context: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(context, dict):
        raise ValueError("Template context is required.")

    activity, training = _activity_for_profile_preview(context)
    if not isinstance(activity, dict) or not activity:
        raise ValueError("Template context must include activity data for profile preview.")

    selected = _select_activity_profile(settings, activity, training=training)
    profile_id = str(selected.get("profile_id") or "default")
    profile = get_template_profile(settings, profile_id)
    criteria = profile.get("criteria") if isinstance(profile, dict) else {}
    reasons = selected.get("reasons")

    return {
        "profile_id": profile_id,
        "profile_label": str(selected.get("profile_label") or profile_id.title()),
        "reasons": list(reasons) if isinstance(reasons, list) else [],
        "criteria": dict(criteria) if isinstance(criteria, dict) else {},
        "enabled": bool(profile.get("enabled")) if isinstance(profile, dict) else profile_id == "default",
        "priority": int(profile.get("priority", 0)) if isinstance(profile, dict) else 0,
        "working_profile_id": str(selected.get("working_profile_id") or "default"),
        "selection_mode": str(selected.get("selection_mode") or ""),
    }


def preview_specific_profile_match(
    settings: Settings,
    context: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(context, dict):
        raise ValueError("Template context is required.")
    if not isinstance(profile, dict):
        raise ValueError("Profile definition is required.")

    activity, training = _activity_for_profile_preview(context)
    if not isinstance(activity, dict) or not activity:
        raise ValueError("Template context must include activity data for profile preview.")

    profile_id = str(profile.get("profile_id") or "").strip().lower()
    if not profile_id:
        raise ValueError("profile_id is required.")
    criteria = profile.get("criteria") if isinstance(profile.get("criteria"), dict) else {}
    reasons = _profile_match_reasons(
        profile_id,
        activity,
        settings,
        training=training,
        criteria=criteria,
    )
    return {
        "profile_id": profile_id,
        "profile_label": str(profile.get("label") or profile_id.title()),
        "matched": bool(reasons),
        "reasons": list(reasons) if isinstance(reasons, list) else [],
        "criteria": dict(criteria) if isinstance(criteria, dict) else {},
        "enabled": bool(profile.get("enabled")),
        "priority": int(profile.get("priority", 0) or 0),
    }


def build_profile_preview_training(
    settings: Settings,
    activity: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(activity, dict) or not activity:
        raise ValueError("Activity data is required.")

    garmin_client = _get_garmin_client(settings)
    training = _get_garmin_metrics(garmin_client)
    training["_garmin_activity_aligned"] = False
    if garmin_client is not None:
        matched_garmin_context = get_activity_context_for_strava_activity(
            garmin_client,
            activity,
        )
        if isinstance(matched_garmin_context, dict) and matched_garmin_context:
            training["garmin_last_activity"] = matched_garmin_context
            training["_garmin_activity_aligned"] = True
    return training


def preview_specific_profile_against_activity(
    settings: Settings,
    activity: dict[str, Any],
    profile: dict[str, Any],
    *,
    training: dict[str, Any] | None = None,
    enabled_override: bool | None = None,
) -> dict[str, Any]:
    if not isinstance(activity, dict) or not activity:
        raise ValueError("Activity data is required.")
    if not isinstance(profile, dict):
        raise ValueError("Profile definition is required.")

    profile_id = str(profile.get("profile_id") or "").strip().lower()
    if not profile_id:
        raise ValueError("profile_id is required.")
    criteria = profile.get("criteria") if isinstance(profile.get("criteria"), dict) else {}
    effective_training = training if isinstance(training, dict) else None
    reasons = _profile_match_reasons(
        profile_id,
        activity,
        settings,
        training=effective_training,
        criteria=criteria,
    )
    enabled = bool(profile.get("enabled"))
    if enabled_override is not None:
        enabled = bool(enabled_override)
    matched = bool(reasons)
    would_process = enabled and matched
    result_reasons = list(reasons) if isinstance(reasons, list) else []
    if not enabled:
        result_reasons = ["profile disabled", *result_reasons]
    return {
        "profile_id": profile_id,
        "profile_label": str(profile.get("label") or profile_id.title()),
        "matched": matched,
        "would_process": would_process,
        "reasons": result_reasons,
        "criteria": dict(criteria) if isinstance(criteria, dict) else {},
        "enabled": enabled,
        "priority": int(profile.get("priority", 0) or 0),
        "garmin_activity_aligned": bool(effective_training.get("_garmin_activity_aligned")) if isinstance(effective_training, dict) else False,
    }


def _profile_activity_update_payload(profile_id: str, detailed_activity: dict[str, Any], description: str) -> dict[str, Any]:
    payload: dict[str, Any] = {"description": description}
    if profile_id == "strength_training":
        payload["private"] = True
        payload["name"] = "Strength Workout"
        payload["type"] = "Workout"
        return payload
    if profile_id == "onewheel":
        payload["type"] = "EBikeRide"
        payload["name"] = "Onewheel Float 🛹"
        return payload
    if profile_id == "incline_treadmill":
        payload["type"] = "Walk"
        payload["name"] = "Max Incline Treadmill"
        payload["trainer"] = True
        return payload
    if profile_id == "treadmill":
        speed_mps = _as_float(detailed_activity.get("average_speed")) or 0.0
        speed_mph = speed_mps * 2.23694
        is_walk = speed_mph < 4.0
        payload["type"] = "Walk" if is_walk else "Run"
        payload["name"] = "Treadmill Walk" if is_walk else "Treadmill Run"
        payload["trainer"] = True
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
    garmin_last = training.get("garmin_last_activity") if isinstance(training.get("garmin_last_activity"), dict) else {}
    if training.get("_garmin_activity_aligned"):
        garmin_average_hr = garmin_last.get("average_hr")
        if garmin_average_hr not in {None, "", "N/A"}:
            average_hr = garmin_average_hr
        garmin_cadence = garmin_last.get("cadence_spm")
        if garmin_cadence not in {None, "", "N/A"}:
            running_cadence = garmin_cadence

    strava_hr = detailed_activity.get("average_heartrate")
    if average_hr == "N/A" and isinstance(strava_hr, (int, float)):
        average_hr = int(round(strava_hr))

    strava_cadence = detailed_activity.get("average_cadence")
    if running_cadence == "N/A" and isinstance(strava_cadence, (int, float)):
        running_cadence = int(round(strava_cadence * 2 if strava_cadence < 130 else strava_cadence))

    return average_hr, running_cadence


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
    norm_power_source = "intervals"
    if not isinstance(norm_power, str) or norm_power.strip().upper() == "N/A":
        weighted_watts = _as_float(detailed_activity.get("weighted_average_watts"))
        if weighted_watts is None:
            weighted_watts = _as_float(detailed_activity.get("average_watts"))
        if weighted_watts is not None and weighted_watts > 0:
            norm_power = f"{int(round(weighted_watts))}W"
            norm_power_source = "strava"
        else:
            garmin_last = training.get("garmin_last_activity")
            garmin_watts = None
            if isinstance(garmin_last, dict):
                garmin_watts = _as_float(garmin_last.get("norm_power_w"))
            if garmin_watts is not None and garmin_watts > 0:
                norm_power = f"{int(round(garmin_watts))}W"
                norm_power_source = "garmin"
            else:
                norm_power = "N/A"
                norm_power_source = "none"
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
    garmin_badges_raw = _coerce_garmin_badge_records(training.get("garmin_badges_raw"), max_items=250)
    garmin_badges = _coerce_string_list(training.get("garmin_badges"), max_items=20)
    garmin_last_activity = training.get("garmin_last_activity") if isinstance(training.get("garmin_last_activity"), dict) else {}
    garmin_activity_badges = _extract_activity_garmin_badges(
        garmin_badges_raw,
        garmin_activity_id=garmin_last_activity.get("activity_id"),
        max_items=20,
    )
    smashrun_badges_lines = _normalize_smashrun_badges(smashrun_badges)
    smashrun_activity_badges = _extract_activity_smashrun_badges(
        smashrun_badges,
        smashrun_activity_id=smashrun_activity_context.get("activity_id"),
        strava_activity_id=detailed_activity.get("id"),
        max_items=20,
    )
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
        "activity_badges": garmin_activity_badges,
        "smashrun_badges": smashrun_badges_lines,
        "smashrun_activity_badges": smashrun_activity_badges,
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
            "norm_power_source": norm_power_source,
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
            "activity_badges": garmin_activity_badges,
            "segment_notables": garmin_segment_notables,
            "last_activity": garmin_last_activity,
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
            "activity_badges": smashrun_activity_badges,
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


def _strava_period_stats_incremental_overlap_hours() -> int:
    raw = str(
        os.getenv(
            "STRAVA_PERIOD_STATS_INCREMENTAL_OVERLAP_HOURS",
            str(DEFAULT_STRAVA_PERIOD_STATS_INCREMENTAL_OVERLAP_HOURS),
        )
    ).strip()
    try:
        parsed = int(raw)
    except ValueError:
        return DEFAULT_STRAVA_PERIOD_STATS_INCREMENTAL_OVERLAP_HOURS
    return max(1, min(parsed, 24 * 14))


def _parse_utc_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_period_stats_activity(activity: dict[str, Any]) -> dict[str, Any] | None:
    raw_id = activity.get("id")
    if raw_id is None:
        return None
    activity_id = str(raw_id).strip()
    if not activity_id:
        return None

    start_date_raw = activity.get("start_date") or activity.get("start_date_local")
    if not isinstance(start_date_raw, str) or not start_date_raw.strip():
        return None
    start_date = start_date_raw.strip()
    if _parse_utc_datetime(start_date) is None:
        return None

    raw_type = activity.get("sport_type")
    if not isinstance(raw_type, str) or not raw_type.strip():
        raw_type = activity.get("type")
    activity_type = str(raw_type or "Unknown").strip() or "Unknown"

    normalized: dict[str, Any] = {
        "id": activity_id,
        "start_date": start_date,
        "sport_type": activity_type,
        "type": activity_type,
        "distance": float(_as_float(activity.get("distance")) or 0.0),
        "moving_time": float(_as_float(activity.get("moving_time")) or 0.0),
        "calories": float(_as_float(activity.get("calories")) or 0.0),
    }
    average_speed = _as_float(activity.get("average_speed"))
    if average_speed is not None and average_speed > 0:
        normalized["average_speed"] = float(average_speed)
    gap_speed = _as_float(activity.get("average_grade_adjusted_speed"))
    if gap_speed is not None and gap_speed > 0:
        normalized["average_grade_adjusted_speed"] = float(gap_speed)
    legacy_gap_speed = _as_float(activity.get("avgGradeAdjustedSpeed"))
    if legacy_gap_speed is not None and legacy_gap_speed > 0:
        normalized["avgGradeAdjustedSpeed"] = float(legacy_gap_speed)
    return normalized


def _filter_period_stats_history(
    activities: list[dict[str, Any]],
    *,
    year_start_utc: datetime,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for item in activities:
        start_utc = _parse_utc_datetime(item.get("start_date"))
        if start_utc is None or start_utc < year_start_utc:
            continue
        filtered.append(item)
    return sorted(filtered, key=lambda value: (str(value.get("start_date")), str(value.get("id"))))


def _normalize_period_stats_activities(
    raw_activities: list[dict[str, Any]],
    *,
    year_start_utc: datetime,
) -> list[dict[str, Any]]:
    deduped_by_id: dict[str, dict[str, Any]] = {}
    for raw in raw_activities:
        if not isinstance(raw, dict):
            continue
        normalized = _normalize_period_stats_activity(raw)
        if normalized is None:
            continue
        deduped_by_id[normalized["id"]] = normalized
    return _filter_period_stats_history(list(deduped_by_id.values()), year_start_utc=year_start_utc)


def _period_stats_cache_marker(cache_payload: dict[str, Any]) -> tuple[str | None, str | None]:
    raw_id = cache_payload.get("latest_activity_id")
    raw_start = cache_payload.get("latest_activity_start_date")
    marker_id = str(raw_id).strip() if raw_id is not None else ""
    marker_start = str(raw_start).strip() if raw_start is not None else ""
    return marker_id or None, marker_start or None


def _load_period_stats_cached_activities(
    settings: Settings,
    *,
    year_start_utc: datetime,
) -> tuple[list[dict[str, Any]] | None, tuple[str | None, str | None], int]:
    cached = get_runtime_value(settings.processed_log_file, PERIOD_STATS_ACTIVITIES_CACHE_KEY)
    if not isinstance(cached, dict):
        return None, (None, None), 0
    expected_year_start = year_start_utc.isoformat()
    if str(cached.get("year_start_utc") or "").strip() != expected_year_start:
        return None, _period_stats_cache_marker(cached), 0
    activities_raw = cached.get("activities")
    if not isinstance(activities_raw, list):
        return None, _period_stats_cache_marker(cached), 0
    normalized = _normalize_period_stats_activities(activities_raw, year_start_utc=year_start_utc)
    return normalized, _period_stats_cache_marker(cached), len(activities_raw)


def _save_period_stats_cache(
    settings: Settings,
    *,
    year_start_utc: datetime,
    latest_marker: tuple[str | None, str | None],
    activities: list[dict[str, Any]],
) -> None:
    latest_id, latest_start = latest_marker
    payload = {
        "year_start_utc": year_start_utc.isoformat(),
        "latest_activity_id": latest_id or "",
        "latest_activity_start_date": latest_start or "",
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "activities": activities,
    }
    set_runtime_value(settings.processed_log_file, PERIOD_STATS_ACTIVITIES_CACHE_KEY, payload)


def _fetch_period_stats_activities_full(
    settings: Settings,
    strava_client: StravaClient,
    *,
    year_start_utc: datetime,
    latest_marker: tuple[str | None, str | None],
    service_state: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw = _run_required_call(
        settings,
        "strava.get_activities_after",
        strava_client.get_activities_after,
        year_start_utc,
        service_state=service_state,
    )
    activities = _normalize_period_stats_activities(raw, year_start_utc=year_start_utc)
    _save_period_stats_cache(
        settings,
        year_start_utc=year_start_utc,
        latest_marker=latest_marker,
        activities=activities,
    )
    return activities, {
        "mode": "full",
        "fetched_records": int(len(raw)),
        "cached_records": int(len(activities)),
    }


def _get_period_stats_activities(
    settings: Settings,
    strava_client: StravaClient,
    *,
    year_start_utc: datetime,
    latest_marker: tuple[str | None, str | None],
    service_state: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    latest_id, latest_start = latest_marker
    cached_activities, cached_marker, cached_count = _load_period_stats_cached_activities(
        settings,
        year_start_utc=year_start_utc,
    )
    cached_latest_id, _cached_latest_start = cached_marker

    if cached_activities is not None and latest_id and latest_id == cached_latest_id:
        return cached_activities, {
            "mode": "cache_hit",
            "fetched_records": 0,
            "cached_records": int(len(cached_activities)),
        }

    if cached_activities is None:
        return _fetch_period_stats_activities_full(
            settings,
            strava_client,
            year_start_utc=year_start_utc,
            latest_marker=latest_marker,
            service_state=service_state,
        )

    latest_start_utc = _parse_utc_datetime(latest_start)
    if not latest_id or latest_start_utc is None:
        return _fetch_period_stats_activities_full(
            settings,
            strava_client,
            year_start_utc=year_start_utc,
            latest_marker=latest_marker,
            service_state=service_state,
        )

    overlap_hours = _strava_period_stats_incremental_overlap_hours()
    fetch_after = latest_start_utc - timedelta(hours=overlap_hours)
    if fetch_after < year_start_utc:
        fetch_after = year_start_utc

    raw_recent = _run_required_call(
        settings,
        "strava.get_activities_after",
        strava_client.get_activities_after,
        fetch_after,
        service_state=service_state,
    )
    merged_by_id: dict[str, dict[str, Any]] = {item["id"]: dict(item) for item in cached_activities}
    for raw in raw_recent:
        if not isinstance(raw, dict):
            continue
        normalized = _normalize_period_stats_activity(raw)
        if normalized is None:
            continue
        merged_by_id[normalized["id"]] = normalized

    merged_activities = _filter_period_stats_history(
        list(merged_by_id.values()),
        year_start_utc=year_start_utc,
    )
    if latest_id not in merged_by_id:
        full_activities, full_sync = _fetch_period_stats_activities_full(
            settings,
            strava_client,
            year_start_utc=year_start_utc,
            latest_marker=latest_marker,
            service_state=service_state,
        )
        full_sync["fallback_reason"] = "incremental_missing_latest_marker"
        return full_activities, full_sync

    _save_period_stats_cache(
        settings,
        year_start_utc=year_start_utc,
        latest_marker=latest_marker,
        activities=merged_activities,
    )
    return merged_activities, {
        "mode": "incremental",
        "fetch_after": fetch_after.isoformat(),
        "fetched_records": int(len(raw_recent)),
        "cached_records": int(cached_count),
        "merged_records": int(len(merged_activities)),
    }


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
    return _collect_smashrun_context_impl(
        settings,
        detailed_activity,
        selected_activity_id=selected_activity_id,
        latest_activity_id=latest_activity_id,
        now_utc=now_utc,
        service_state=service_state,
        run_service_call=_run_service_call,
        as_float=_as_float,
        logger=logger,
    )


def _collect_weather_context(
    settings: Settings,
    detailed_activity: dict[str, Any],
    *,
    selected_activity_id: int,
    service_state: dict[str, Any] | None,
) -> dict[str, Any]:
    return _collect_weather_context_impl(
        settings,
        detailed_activity,
        selected_activity_id=selected_activity_id,
        service_state=service_state,
        run_service_call=_run_service_call,
    )


def _collect_crono_context(
    settings: Settings,
    detailed_activity: dict[str, Any],
    *,
    selected_activity_id: int,
    service_state: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, str | None]:
    return _collect_crono_context_impl(
        settings,
        detailed_activity,
        selected_activity_id=selected_activity_id,
        service_state=service_state,
        run_service_call=_run_service_call,
    )


def _is_retryable_run_error(exc: Exception) -> bool:
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    text = str(exc).strip().lower()
    if not text:
        return False
    retry_tokens = (
        "timeout",
        "timed out",
        "temporarily unavailable",
        "too many requests",
        "connection reset",
        "connection aborted",
        "connection refused",
        "dns",
        "name resolution",
        "http 429",
        "http 500",
        "http 502",
        "http 503",
        "http 504",
    )
    return any(token in text for token in retry_tokens)


def run_once(force_update: bool = False, activity_id: int | None = None) -> dict[str, Any]:
    settings = Settings.from_env()
    settings.validate()
    settings.ensure_state_paths()

    _configure_logging(settings.log_level)
    lock_owner = f"{uuid.uuid4()}:{int(time.time())}"
    lock_name = "run_once"
    selected_activity_id: int | None = None
    job_id: str | None = None
    run_id: str | None = None
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
        write_config_snapshot(
            settings.processed_log_file,
            "run_once",
            {
                "force_update": bool(force_update),
                "activity_id": int(activity_id) if activity_id is not None else None,
                "timezone": settings.timezone,
                "poll_interval_seconds": settings.poll_interval_seconds,
                "job_max_attempts": settings.job_max_attempts,
                "job_retry_delay_seconds": settings.job_retry_delay_seconds,
            },
        )
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

        for item in activities:
            if not isinstance(item, dict):
                continue
            activity_value = item.get("id")
            if activity_value is None:
                continue
            register_activity_discovery(
                settings.processed_log_file,
                activity_value,
                sport_type=item.get("sport_type") if isinstance(item.get("sport_type"), str) else None,
                start_date_utc=item.get("start_date") if isinstance(item.get("start_date"), str) else None,
            )

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
        job_id = enqueue_activity_job(
            settings.processed_log_file,
            selected_activity_id,
            request_kind=(
                "manual_activity"
                if activity_id is not None
                else ("manual_latest" if force_update else "auto_poll")
            ),
            requested_by="manual" if (force_update or activity_id is not None) else "worker",
            force_update=bool(force_update),
            priority=10 if (force_update or activity_id is not None) else 100,
            max_attempts=settings.job_max_attempts,
        )
        if not job_id:
            raise RuntimeError(f"Failed to enqueue activity job for {selected_activity_id}")
        if not claim_activity_job(
            settings.processed_log_file,
            job_id,
            owner=lock_owner,
            lease_seconds=settings.run_lock_ttl_seconds,
        ):
            raise RuntimeError(f"Failed to claim queued activity job {job_id}")
        started = start_activity_job_run(
            settings.processed_log_file,
            job_id,
            owner=lock_owner,
        )
        if not started:
            raise RuntimeError(f"Failed to start activity job run for {job_id}")
        run_id = str(started["run_id"])

        detailed_activity = _run_required_call(
            settings,
            "strava.get_activity_details",
            strava_client.get_activity_details,
            selected_activity_id,
            service_state=service_state,
        )
        selected.setdefault("start_date", detailed_activity.get("start_date"))
        register_activity_discovery(
            settings.processed_log_file,
            selected_activity_id,
            sport_type=(
                detailed_activity.get("sport_type")
                if isinstance(detailed_activity.get("sport_type"), str)
                else (
                    selected.get("sport_type")
                    if isinstance(selected.get("sport_type"), str)
                    else None
                )
            ),
            start_date_utc=(
                detailed_activity.get("start_date")
                if isinstance(detailed_activity.get("start_date"), str)
                else (
                    selected.get("start_date") if isinstance(selected.get("start_date"), str) else None
                )
            ),
        )

        if selected_activity_id != int(latest["id"]):
            logger.info(
                "Selected activity %s (latest is %s).",
                selected_activity_id,
                int(latest["id"]),
            )

        _local_tz, now_local, now_utc, year_start = _resolve_cycle_time_context(settings)

        latest_marker = (
            str(latest.get("id")).strip() if latest.get("id") is not None else None,
            str(latest.get("start_date") or latest.get("start_date_local") or "").strip() or None,
        )
        strava_activities, period_stats_sync = _get_period_stats_activities(
            settings,
            strava_client,
            year_start_utc=year_start,
            latest_marker=latest_marker,
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
        training["_garmin_activity_aligned"] = False
        if garmin_client is not None:
            matched_garmin_context = _run_service_call(
                settings,
                "garmin.activity_context",
                get_activity_context_for_strava_activity,
                garmin_client,
                detailed_activity,
                service_state=service_state,
                cache_key=f"garmin.activity_context:{selected_activity_id}",
                cache_ttl_seconds=settings.service_cache_ttl_seconds,
            )
            if isinstance(matched_garmin_context, dict) and matched_garmin_context:
                training["garmin_last_activity"] = matched_garmin_context
                training["_garmin_activity_aligned"] = True
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

        selected_profile = _select_activity_profile(settings, detailed_activity, training=training)
        profile_id = str(selected_profile.get("profile_id") or "default")
        description_context["profile"] = {
            "id": profile_id,
            "label": str(selected_profile.get("profile_label") or profile_id.title()),
            "reasons": selected_profile.get("reasons") or [],
            "working_id": str(selected_profile.get("working_profile_id") or "default"),
            "selection_mode": str(selected_profile.get("selection_mode") or ""),
        }

        render_result = render_with_active_template(
            settings,
            description_context,
            profile_id=profile_id,
            allow_seed_fallback=False,
        )
        if render_result["ok"]:
            description = str(render_result["description"])
        else:
            error_text = str(render_result.get("error") or "Unknown template render error")
            logger.error("Template render failed for profile %s: %s", profile_id, error_text)
            raise RuntimeError(f"Template render failed for profile '{profile_id}': {error_text}")

        update_payload = _profile_activity_update_payload(profile_id, detailed_activity, description)
        _run_required_call(
            settings,
            "strava.update_activity",
            strava_client.update_activity,
            selected_activity_id,
            update_payload,
            service_state=service_state,
        )

        payload = {
            "updated_at_utc": now_utc.isoformat(),
            "activity_id": selected_activity_id,
            "activity_start_date": selected.get("start_date"),
            "description": description,
            "source": "standard",
            "period_stats": period_summaries,
            "period_stats_sync": period_stats_sync,
            "weather": weather_details,
            "template_context": description_context,
            "service_calls": service_state,
            "profile_match": {
                "profile_id": profile_id,
                "profile_label": str(selected_profile.get("profile_label") or profile_id.title()),
                "reasons": selected_profile.get("reasons") or [],
                "working_profile_id": str(selected_profile.get("working_profile_id") or "default"),
                "selection_mode": str(selected_profile.get("selection_mode") or ""),
                "evaluated_at_utc": now_utc.isoformat(),
            },
            "template_render": {
                "ok": render_result.get("ok"),
                "is_custom_template": render_result.get("is_custom_template"),
                "fallback_used": render_result.get("fallback_used"),
                "template_path": render_result.get("template_path"),
                "template_hash": render_result.get("template_hash"),
                "template_version": render_result.get("template_version"),
                "template_name": render_result.get("template_name"),
                "template_updated_at_utc": render_result.get("template_updated_at_utc"),
                "profile_id": render_result.get("profile_id", profile_id),
                "profile_label": render_result.get("profile_label"),
                "error": render_result.get("error"),
                "fallback_reason": render_result.get("fallback_reason"),
            },
        }
        mark_activity_processed(settings.processed_log_file, selected_activity_id)
        write_json(settings.latest_json_file, payload)

        logger.info("Activity %s updated successfully.", selected_activity_id)
        result = {
            "status": "updated",
            "activity_id": selected_activity_id,
            "profile_id": profile_id,
            "working_profile_id": str(selected_profile.get("working_profile_id") or "default"),
            "selection_mode": str(selected_profile.get("selection_mode") or ""),
            "template_path": str(render_result.get("template_path") or ""),
            "template_hash": str(render_result.get("template_hash") or ""),
            "template_version": (
                str(render_result.get("template_version"))
                if render_result.get("template_version") is not None
                else None
            ),
            "template_name": (
                str(render_result.get("template_name"))
                if render_result.get("template_name") is not None
                else None
            ),
            "is_custom_template": bool(render_result.get("is_custom_template")),
        }
        if job_id and run_id:
            complete_activity_job_run(
                settings.processed_log_file,
                job_id,
                run_id,
                owner=lock_owner,
                outcome="succeeded",
                result=result,
            )
        record_activity_output(
            settings.processed_log_file,
            selected_activity_id,
            state="succeeded",
            result_status=result["status"],
            profile_id=profile_id,
            title=str(update_payload.get("name") or "").strip() or None,
            description=description,
            job_id=job_id,
            run_id=run_id,
            error=None,
            template_hash=str(render_result.get("template_hash") or "").strip() or None,
            template_path=str(render_result.get("template_path") or "").strip() or None,
            template_version=(
                str(render_result.get("template_version"))
                if render_result.get("template_version") is not None
                else None
            ),
            template_name=(
                str(render_result.get("template_name"))
                if render_result.get("template_name") is not None
                else None
            ),
            working_profile_id=str(selected_profile.get("working_profile_id") or "default"),
            selection_mode=str(selected_profile.get("selection_mode") or ""),
            is_custom_template=bool(render_result.get("is_custom_template")),
        )
        _record_cycle_status(
            settings,
            status=result["status"],
            activity_id=selected_activity_id,
        )
        return result
    except Exception as exc:
        if selected_activity_id is not None:
            outcome = "retry_wait" if _is_retryable_run_error(exc) else "failed_permanent"
            if job_id and run_id:
                complete_activity_job_run(
                    settings.processed_log_file,
                    job_id,
                    run_id,
                    owner=lock_owner,
                    outcome=outcome,
                    error=str(exc),
                    result={"status": "error", "error": str(exc)},
                    retry_delay_seconds=settings.job_retry_delay_seconds,
                )
            record_activity_output(
                settings.processed_log_file,
                selected_activity_id,
                state=outcome,
                result_status="error",
                job_id=job_id,
                run_id=run_id,
                error=str(exc),
            )
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
