from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import requests


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


def _format_icu_summary(ctl: float | None, atl: float | None) -> str:
    if ctl is None or atl is None or ctl == 0:
        return "N/A"

    form_raw = ((ctl - atl) / ctl) * 100
    fitness = int(round(ctl))
    fatigue = int(round(atl))
    form = int(round(form_raw))

    if form < -30:
        form_class = "High Risk ⚠️"
    elif -30 <= form <= -10:
        form_class = "Optimal 🟢"
    elif -10 < form <= 5:
        form_class = "Grey Zone ⛔"
    elif 5 < form <= 20:
        form_class = "Fresh 🏁"
    else:
        form_class = "Too Light ❄"
    return f"🏋️  {fitness}  | 💦  {fatigue}  | 🗿 {form}% - {form_class}"


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

    return {
        "norm_power": f"{int(norm_power)}W" if isinstance(norm_power, (int, float)) else "N/A",
        "work": f"{round(float(work) / 1000)} kJ" if isinstance(work, (int, float)) else "N/A",
        "efficiency": f"{round(float(efficiency), 2)}" if isinstance(efficiency, (int, float)) else "N/A",
        "achievements": achievements,
        "icu_ctl": ctl,
        "icu_atl": atl,
        "icu_summary": _format_icu_summary(ctl, atl),
    }
