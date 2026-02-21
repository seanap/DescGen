from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from ..numeric_utils import (
    as_float as _shared_as_float,
    meters_to_feet_int as _shared_meters_to_feet_int,
    meters_to_miles as _shared_meters_to_miles,
    mps_to_mph as _shared_mps_to_mph,
    mps_to_pace as _shared_mps_to_pace,
    seconds_to_hms as _shared_seconds_to_hms,
)


logger = logging.getLogger(__name__)
TIMEOUT_SECONDS = 30


def _normalize_activities_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        activities = payload.get("activities")
        if isinstance(activities, list):
            return [item for item in activities if isinstance(item, dict)]
    return []


def _normalize_achievements_payload(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def format_time(seconds: float | int | None) -> str:
    if seconds is None:
        return "N/A"
    seconds_int = int(float(seconds))
    hours = int(seconds_int // 3600)
    minutes = int((seconds_int % 3600) // 60)
    remaining = int(seconds_int % 60)
    if hours > 0:
        return f"{hours}h {minutes}m {remaining}s"
    if minutes > 0:
        return f"{minutes}m {remaining}s"
    return f"{remaining}s"


def format_distance(distance_meters: float | int | None) -> str:
    if distance_meters is None:
        return "N/A"
    return f"{float(distance_meters) / 1000:.0f}k"


def _as_float(value: Any) -> float | None:
    return _shared_as_float(value)


def _seconds_to_hms(value: Any) -> str:
    return _shared_seconds_to_hms(value)


def _mps_to_pace(value: Any) -> str:
    return _shared_mps_to_pace(value, include_unit=True)


def _mps_to_mph(value: Any) -> str:
    return _shared_mps_to_mph(value, include_unit=True)


def _meters_to_miles(value: Any) -> str:
    return _shared_meters_to_miles(value, include_unit=True)


def _meters_to_feet_int(value: Any) -> int | str:
    return _shared_meters_to_feet_int(value)


def _temperature_f(value: Any) -> str:
    temp = _as_float(value)
    if temp is None:
        return "N/A"
    return f"{temp:.1f}F"


def _format_zone_summary(value: Any) -> str:
    entries: list[tuple[int, int]] = []
    if isinstance(value, list):
        for idx, item in enumerate(value, start=1):
            zone_id = idx
            secs_value = None
            if isinstance(item, dict):
                zid = item.get("id")
                if isinstance(zid, int) and zid > 0:
                    zone_id = zid
                secs_value = _as_float(item.get("secs"))
            else:
                secs_value = _as_float(item)
            if secs_value is None or secs_value <= 0:
                continue
            entries.append((zone_id, int(round(secs_value))))
    if not entries:
        return "N/A"
    parts = [f"Z{zone} {format_time(secs)}" for zone, secs in entries]
    return " | ".join(parts)


def _calc_form_percent(ctl: Any, atl: Any) -> float | None:
    ctl_value = _as_float(ctl)
    atl_value = _as_float(atl)
    if ctl_value is None or atl_value is None or ctl_value == 0:
        return None
    return ((ctl_value - atl_value) / ctl_value) * 100.0


def _classify_form(form_percent: Any) -> tuple[str, str]:
    form_value = _as_float(form_percent)
    if form_value is None:
        return "N/A", "⚪"

    if form_value < -30:
        return "High Risk", "⚠️"
    if form_value <= -10:
        return "Optimal", "🦾"
    if form_value <= 5:
        return "Grey Zone", "⛔"
    if form_value <= 20:
        return "Fresh", "🏁"
    return "Transition", "❄️"


def _format_icu_summary(ctl: float | None, atl: float | None) -> str:
    form_raw = _calc_form_percent(ctl, atl)
    if form_raw is None:
        return "N/A"

    fitness = int(round(ctl))
    fatigue = int(round(atl))
    form = int(round(form_raw))
    form_class, form_emoji = _classify_form(form)
    return f"🏋️ {fitness} | 💦 {fatigue} | 🗿 {form}% - {form_class} {form_emoji}"


def _first_numeric(*values: Any) -> float | None:
    for value in values:
        parsed = _as_float(value)
        if parsed is not None:
            return parsed
    return None


def _iso_window_value(value: datetime | str | None, *, fallback: datetime) -> str:
    if isinstance(value, datetime):
        parsed = value.astimezone(timezone.utc)
        return parsed.strftime("%Y-%m-%dT%H:%M:%S")
    text = str(value or "").strip()
    if not text:
        return fallback.strftime("%Y-%m-%dT%H:%M:%S")
    parsed = None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
    if parsed is None:
        return fallback.strftime("%Y-%m-%dT%H:%M:%S")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return parsed.strftime("%Y-%m-%dT%H:%M:%S")


def _extract_strava_activity_id(activity: dict[str, Any]) -> str | None:
    direct_candidates = (
        activity.get("strava_activity_id"),
        activity.get("stravaActivityId"),
        activity.get("strava_id"),
        activity.get("stravaId"),
        activity.get("source_id"),
        activity.get("sourceId"),
        activity.get("external_id"),
        activity.get("externalId"),
    )
    for candidate in direct_candidates:
        text = str(candidate or "").strip()
        if text and text.isdigit():
            return text

    nested = activity.get("source")
    if isinstance(nested, dict):
        source_candidates = (
            nested.get("activity_id"),
            nested.get("activityId"),
            nested.get("strava_activity_id"),
            nested.get("stravaActivityId"),
            nested.get("id"),
        )
        for candidate in source_candidates:
            text = str(candidate or "").strip()
            if text and text.isdigit():
                return text

    for key in ("source_id", "sourceId", "external_id", "externalId", "id"):
        text = str(activity.get(key) or "").strip()
        if not text:
            continue
        if key != "id" and text.isdigit():
            return text
        match = re.search(r"(?:strava[^0-9]*)([0-9]{5,})", text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
        if key != "id":
            digit_match = re.search(r"\b([0-9]{5,})\b", text)
            if digit_match:
                return digit_match.group(1)
    return None


def _extract_start_date(activity: dict[str, Any]) -> str | None:
    for key in (
        "start_date",
        "startDate",
        "start_date_local",
        "startDateLocal",
        "start_time",
        "startTime",
        "start_time_local",
        "startTimeLocal",
        "start_datetime",
        "startDateTime",
    ):
        raw = activity.get(key)
        text = str(raw or "").strip()
        if text:
            return text
    return None


def get_intervals_dashboard_metrics(
    user_id: str | None,
    api_key: str | None,
    *,
    oldest: datetime | str | None,
    newest: datetime | str | None,
) -> list[dict[str, Any]]:
    if not user_id or not api_key:
        return []

    now = datetime.now(timezone.utc)
    oldest_text = _iso_window_value(oldest, fallback=now - timedelta(days=365))
    newest_text = _iso_window_value(newest, fallback=now)
    auth = ("API_KEY", api_key)
    list_url = (
        f"https://intervals.icu/api/v1/athlete/{user_id}/activities"
        f"?oldest={oldest_text}&newest={newest_text}"
    )

    try:
        response = requests.get(list_url, auth=auth, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        activities = _normalize_activities_payload(response.json())
    except requests.RequestException as exc:
        logger.warning("Intervals.icu dashboard request failed: %s", exc)
        return []

    records: list[dict[str, Any]] = []
    for activity in activities:
        if not isinstance(activity, dict):
            continue

        moving_time = _first_numeric(
            activity.get("moving_time"),
            activity.get("movingTime"),
            activity.get("elapsed_time"),
            activity.get("elapsedTime"),
        )
        distance = _first_numeric(
            activity.get("distance"),
            activity.get("distance_m"),
            activity.get("distanceM"),
            activity.get("distanceMeters"),
        )
        avg_speed = _first_numeric(
            activity.get("average_speed"),
            activity.get("averageSpeed"),
            activity.get("avg_speed"),
            activity.get("avgSpeed"),
            activity.get("speed"),
        )
        pace_mps = avg_speed
        if (pace_mps is None or pace_mps <= 0) and distance and moving_time and moving_time > 0:
            pace_mps = distance / moving_time
        if pace_mps is not None and pace_mps <= 0:
            pace_mps = None

        efficiency = _first_numeric(
            activity.get("icu_efficiency_factor"),
            activity.get("icuEfficiencyFactor"),
            activity.get("efficiency_factor"),
            activity.get("efficiencyFactor"),
            activity.get("efficiency"),
        )
        fitness = _first_numeric(
            activity.get("icu_ctl"),
            activity.get("icuCtl"),
            activity.get("ctl"),
            activity.get("fitness_score"),
            activity.get("fitnessScore"),
            activity.get("fitness"),
        )
        fatigue = _first_numeric(
            activity.get("icu_atl"),
            activity.get("icuAtl"),
            activity.get("atl"),
            activity.get("fatigue_score"),
            activity.get("fatigueScore"),
            activity.get("fatigue"),
        )

        if (
            pace_mps is None
            and efficiency is None
            and fitness is None
            and fatigue is None
        ):
            continue

        record: dict[str, Any] = {
            "strava_activity_id": _extract_strava_activity_id(activity),
            "start_date": _extract_start_date(activity),
            "avg_pace_mps": pace_mps,
            "avg_efficiency_factor": efficiency,
            "avg_fitness": fitness,
            "avg_fatigue": fatigue,
            "moving_time_seconds": moving_time if moving_time and moving_time > 0 else None,
        }
        records.append(record)

    return records


def get_intervals_activity_data(
    user_id: str | None, api_key: str | None, lookback_days: int = 2
) -> dict[str, Any] | None:
    if not user_id or not api_key:
        return None

    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=lookback_days)
    start_date_str = start_date.strftime("%Y-%m-%dT%H:%M:%S")
    end_date_str = end_date.strftime("%Y-%m-%dT%H:%M:%S")
    auth = ("API_KEY", api_key)

    list_url = (
        f"https://intervals.icu/api/v1/athlete/{user_id}/activities"
        f"?oldest={start_date_str}&newest={end_date_str}"
    )
    try:
        list_response = requests.get(list_url, auth=auth, timeout=TIMEOUT_SECONDS)
        list_response.raise_for_status()
        activities = _normalize_activities_payload(list_response.json())
        if not activities:
            return None

        activity_id = activities[0].get("id") or activities[0].get("activity_id")
        if activity_id is None:
            return None

        detail_response = requests.get(
            f"https://intervals.icu/api/v1/activity/{activity_id}",
            auth=auth,
            params={"intervals": "false"},
            timeout=TIMEOUT_SECONDS,
        )
        detail_response.raise_for_status()
        detail_payload = detail_response.json()
        data = detail_payload if isinstance(detail_payload, dict) else {}
    except requests.RequestException as exc:
        logger.error("Intervals.icu request failed: %s", exc)
        return None

    achievements_raw = _normalize_achievements_payload(data.get("icu_achievements"))
    achievements: list[str] = []
    for achievement in achievements_raw:
        achievement_type = achievement.get("type")
        if achievement_type == "BEST_POWER":
            achievements.append(
                f"New best power: {achievement.get('watts', 'N/A')}W for {format_time(achievement.get('secs'))}"
            )
        elif achievement_type == "BEST_PACE":
            achievements.append(
                f"New best pace: {format_time(achievement.get('secs'))} for {format_distance(achievement.get('distance'))}"
            )
        else:
            message = achievement.get("message")
            if message:
                achievements.append(message)

    norm_power = data.get("icu_weighted_avg_watts")
    work = data.get("icu_joules")
    efficiency = data.get("icu_efficiency_factor")
    ctl = data.get("icu_ctl")
    atl = data.get("icu_atl")
    training_load = data.get("icu_training_load")
    ramp_rate = _first_numeric(
        data.get("ramp_rate"),
        data.get("icu_ramp_rate"),
        data.get("rampRate"),
        data.get("ctl_ramp_rate"),
        data.get("ctlRampRate"),
        data.get("ramp"),
    )
    strain_score = data.get("strain_score")
    pace_load = data.get("pace_load")
    hr_load = data.get("hr_load")
    power_load = data.get("power_load")

    average_speed = data.get("average_speed")
    max_speed = data.get("max_speed")
    distance = data.get("distance")
    moving_time = data.get("moving_time")
    elapsed_time = data.get("elapsed_time")
    average_hr = data.get("average_heartrate")
    max_hr = data.get("max_heartrate")
    total_elevation_gain = data.get("total_elevation_gain")
    total_elevation_loss = data.get("total_elevation_loss")
    average_temp = data.get("average_temp")
    max_temp = data.get("max_temp")
    min_temp = data.get("min_temp")

    zone_summary = _format_zone_summary(data.get("icu_zone_times"))
    hr_zone_summary = _format_zone_summary(data.get("icu_hr_zone_times"))
    pace_zone_summary = _format_zone_summary(data.get("pace_zone_times"))
    gap_zone_summary = _format_zone_summary(data.get("gap_zone_times"))

    fitness = int(round(float(ctl))) if isinstance(ctl, (int, float)) else "N/A"
    fatigue = int(round(float(atl))) if isinstance(atl, (int, float)) else "N/A"
    load = (
        int(round(float(training_load)))
        if isinstance(training_load, (int, float))
        else "N/A"
    )
    ramp = round(ramp_rate, 1) if ramp_rate is not None else "N/A"

    form_percent_raw = _calc_form_percent(ctl, atl)
    form_percent = int(round(form_percent_raw)) if form_percent_raw is not None else "N/A"
    form_class, form_class_emoji = _classify_form(form_percent_raw)
    form_percent_display = (
        f"{form_percent}%"
        if isinstance(form_percent, int)
        else "N/A"
    )

    return {
        "norm_power": f"{int(round(float(norm_power)))}W" if isinstance(norm_power, (int, float)) else "N/A",
        "work": f"{round(float(work) / 1000)} kJ" if isinstance(work, (int, float)) else "N/A",
        "efficiency": f"{round(float(efficiency), 2)}" if isinstance(efficiency, (int, float)) else "N/A",
        "achievements": achievements,
        "icu_ctl": ctl,
        "icu_atl": atl,
        "icu_summary": _format_icu_summary(ctl, atl),
        "ctl": fitness,
        "atl": fatigue,
        "fitness": fitness,
        "fatigue": fatigue,
        "training_load": load,
        "load": load,
        "ramp": ramp,
        "ramp_display": f"{ramp:+.1f}" if isinstance(ramp, (int, float)) else "N/A",
        "form_percent": form_percent,
        "form_percent_display": form_percent_display,
        "form_class": form_class,
        "form_class_emoji": form_class_emoji,
        "strain_score": int(round(float(strain_score))) if isinstance(strain_score, (int, float)) else "N/A",
        "pace_load": int(round(float(pace_load))) if isinstance(pace_load, (int, float)) else "N/A",
        "hr_load": int(round(float(hr_load))) if isinstance(hr_load, (int, float)) else "N/A",
        "power_load": int(round(float(power_load))) if isinstance(power_load, (int, float)) else "N/A",
        "avg_pace": _mps_to_pace(average_speed),
        "avg_speed_mph": _mps_to_mph(average_speed),
        "max_speed_mph": _mps_to_mph(max_speed),
        "distance_miles": _meters_to_miles(distance),
        "moving_time": _seconds_to_hms(moving_time),
        "elapsed_time": _seconds_to_hms(elapsed_time),
        "average_hr": int(round(float(average_hr))) if isinstance(average_hr, (int, float)) else "N/A",
        "max_hr": int(round(float(max_hr))) if isinstance(max_hr, (int, float)) else "N/A",
        "elevation_gain_feet": _meters_to_feet_int(total_elevation_gain),
        "elevation_loss_feet": _meters_to_feet_int(total_elevation_loss),
        "average_temp_f": _temperature_f(average_temp),
        "max_temp_f": _temperature_f(max_temp),
        "min_temp_f": _temperature_f(min_temp),
        "zone_summary": zone_summary,
        "hr_zone_summary": hr_zone_summary,
        "pace_zone_summary": pace_zone_summary,
        "gap_zone_summary": gap_zone_summary,
    }
