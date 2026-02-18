from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from storage import read_json, write_json


SETUP_OVERRIDES_FILE_ENV = "SETUP_OVERRIDES_FILE"
SETUP_OVERRIDES_FILE_DEFAULT = "setup_overrides.json"

SETUP_ALLOWED_KEYS: set[str] = {
    "STRAVA_CLIENT_ID",
    "STRAVA_CLIENT_SECRET",
    "STRAVA_REFRESH_TOKEN",
    "STRAVA_ACCESS_TOKEN",
    "ENABLE_GARMIN",
    "GARMIN_EMAIL",
    "GARMIN_PASSWORD",
    "ENABLE_INTERVALS",
    "INTERVALS_API_KEY",
    "INTERVALS_USER_ID",
    "ENABLE_WEATHER",
    "WEATHER_API_KEY",
    "ENABLE_SMASHRUN",
    "SMASHRUN_ACCESS_TOKEN",
    "ENABLE_CRONO_API",
    "CRONO_API_BASE_URL",
    "CRONO_API_KEY",
    "TIMEZONE",
}

SETUP_BOOL_KEYS: set[str] = {
    "ENABLE_GARMIN",
    "ENABLE_INTERVALS",
    "ENABLE_WEATHER",
    "ENABLE_SMASHRUN",
    "ENABLE_CRONO_API",
}

SETUP_SECRET_KEYS: set[str] = {
    "STRAVA_CLIENT_SECRET",
    "STRAVA_REFRESH_TOKEN",
    "STRAVA_ACCESS_TOKEN",
    "GARMIN_PASSWORD",
    "INTERVALS_API_KEY",
    "WEATHER_API_KEY",
    "SMASHRUN_ACCESS_TOKEN",
    "CRONO_API_KEY",
}

PROVIDER_LINKS: dict[str, str] = {
    "general": "https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
    "strava": "https://www.strava.com/settings/api",
    "intervals": "https://intervals.icu/",
    "weather": "https://www.weatherapi.com/signup.aspx",
    "smashrun": "https://api.smashrun.com/v1/documentation",
    "garmin": "https://connect.garmin.com/",
    "crono": "https://github.com/seanap/crono-api",
}

PROVIDER_FIELDS: dict[str, list[str]] = {
    "general": [
        "TIMEZONE",
    ],
    "strava": [
        "STRAVA_CLIENT_ID",
        "STRAVA_CLIENT_SECRET",
        "STRAVA_REFRESH_TOKEN",
        "STRAVA_ACCESS_TOKEN",
    ],
    "intervals": [
        "ENABLE_INTERVALS",
        "INTERVALS_API_KEY",
        "INTERVALS_USER_ID",
    ],
    "weather": [
        "ENABLE_WEATHER",
        "WEATHER_API_KEY",
    ],
    "smashrun": [
        "ENABLE_SMASHRUN",
        "SMASHRUN_ACCESS_TOKEN",
    ],
    "garmin": [
        "ENABLE_GARMIN",
        "GARMIN_EMAIL",
        "GARMIN_PASSWORD",
    ],
    "crono": [
        "ENABLE_CRONO_API",
        "CRONO_API_BASE_URL",
        "CRONO_API_KEY",
    ],
}


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(int(value))
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
    return None


def setup_overrides_path(state_dir: Path) -> Path:
    configured = Path(
        os.getenv(SETUP_OVERRIDES_FILE_ENV, SETUP_OVERRIDES_FILE_DEFAULT)
    ).name
    return state_dir / configured


def read_setup_overrides(state_dir: Path) -> dict[str, Any]:
    payload = read_json(setup_overrides_path(state_dir))
    if not isinstance(payload, dict):
        return {}
    values = payload.get("values")
    if not isinstance(values, dict):
        return {}
    out: dict[str, Any] = {}
    for key, value in values.items():
        if key not in SETUP_ALLOWED_KEYS:
            continue
        out[key] = value
    return out


def write_setup_overrides(state_dir: Path, values: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in values.items():
        if key not in SETUP_ALLOWED_KEYS:
            continue
        if value is None:
            continue
        if key in SETUP_BOOL_KEYS:
            as_bool = _to_bool(value)
            if as_bool is None:
                continue
            sanitized[key] = as_bool
            continue
        text = str(value).strip()
        if not text:
            continue
        sanitized[key] = text
    payload = {
        "version": 1,
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "values": sanitized,
    }
    write_json(setup_overrides_path(state_dir), payload)
    return sanitized


def merge_setup_overrides(state_dir: Path, updates: dict[str, Any]) -> dict[str, Any]:
    current = read_setup_overrides(state_dir)
    merged = dict(current)
    for key, value in updates.items():
        if key not in SETUP_ALLOWED_KEYS:
            continue
        if value is None:
            merged.pop(key, None)
            continue
        if key in SETUP_BOOL_KEYS:
            as_bool = _to_bool(value)
            if as_bool is None:
                merged.pop(key, None)
                continue
            merged[key] = as_bool
            continue
        text = str(value).strip()
        if not text:
            merged.pop(key, None)
            continue
        merged[key] = text
    return write_setup_overrides(state_dir, merged)


def mask_setup_values(values: dict[str, Any]) -> dict[str, Any]:
    masked: dict[str, Any] = {}
    for key, value in values.items():
        if key in SETUP_SECRET_KEYS and isinstance(value, str):
            if len(value) <= 6:
                masked[key] = "*" * len(value)
            else:
                masked[key] = f"{value[:2]}***{value[-2:]}"
        else:
            masked[key] = value
    return masked


def render_env_snippet(values: dict[str, Any]) -> str:
    lines: list[str] = []
    for key in sorted(values.keys()):
        value = values[key]
        if key in SETUP_BOOL_KEYS and isinstance(value, bool):
            lines.append(f"{key}={'true' if value else 'false'}")
        else:
            lines.append(f"{key}={value}")
    return "\n".join(lines) + ("\n" if lines else "")
