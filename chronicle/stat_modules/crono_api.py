from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

from ..numeric_utils import as_float


logger = logging.getLogger(__name__)
TIMEOUT_SECONDS = 10


def _headers(api_key: str | None) -> dict[str, str]:
    if not api_key:
        return {}
    return {"x-api-key": api_key}


def _activity_local_date(activity: dict[str, Any], timezone_name: str) -> str | None:
    start_date_local = activity.get("start_date_local")
    if isinstance(start_date_local, str) and len(start_date_local) >= 10:
        return start_date_local[:10]

    start_date = activity.get("start_date")
    if not isinstance(start_date, str):
        return None
    try:
        dt_utc = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)

    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        tz = timezone.utc
    return dt_utc.astimezone(tz).date().isoformat()


def get_crono_summary_for_activity(
    *,
    activity: dict[str, Any],
    timezone_name: str,
    base_url: str | None,
    api_key: str | None = None,
    days: int = 7,
) -> dict[str, Any] | None:
    if not base_url:
        return None

    date_str = _activity_local_date(activity, timezone_name)
    if not date_str:
        return None

    base = base_url.rstrip("/")
    headers = _headers(api_key)

    try:
        macros_response = requests.get(
            f"{base}/api/v1/summary/today-macros",
            params={"date": date_str},
            headers=headers,
            timeout=TIMEOUT_SECONDS,
        )
        macros_response.raise_for_status()
        macros_payload = macros_response.json()

        balance_response = requests.get(
            f"{base}/api/v1/summary/weekly-average-deficit",
            params={"days": days},
            headers=headers,
            timeout=TIMEOUT_SECONDS,
        )
        balance_response.raise_for_status()
        balance_payload = balance_response.json()
    except requests.RequestException as exc:
        logger.error("Crono API request failed: %s", exc)
        return None

    return {
        "date": macros_payload.get("date", date_str),
        "protein_g": as_float(macros_payload.get("protein")),
        "carbs_g": as_float(macros_payload.get("carbs")),
        "average_net_kcal_per_day": as_float(balance_payload.get("averageNetCaloriesPerDay")),
        "average_status": balance_payload.get("averageStatus"),
    }


def _format_grams(value: float | None) -> str | None:
    if value is None or value <= 0:
        return None
    rounded = round(value, 1)
    if abs(rounded - round(rounded)) < 0.05:
        return str(int(round(rounded)))
    return f"{rounded:.1f}"


def format_crono_line(summary: dict[str, Any] | None) -> str | None:
    if not summary:
        return None

    average_net = as_float(summary.get("average_net_kcal_per_day"))
    if average_net is None:
        return None

    status = str(summary.get("average_status") or "").strip().lower()
    if status in {"surplus", "deficit"}:
        balance_text = f"{average_net:+.0f} kcal ({status})"
    else:
        balance_text = f"{average_net:+.0f} kcal"

    parts = [f"🔥 7d avg daily Energy Balance:{balance_text}"]

    protein_text = _format_grams(as_float(summary.get("protein_g")))
    carbs_text = _format_grams(as_float(summary.get("carbs_g")))
    if protein_text is not None:
        parts.append(f"🥩:{protein_text}g")
    if carbs_text is not None:
        parts.append(f"🍞:{carbs_text}g")

    return " | ".join(parts)
