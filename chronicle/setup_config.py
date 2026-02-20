from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .storage import read_json, write_json


SETUP_OVERRIDES_FILE_ENV = "SETUP_OVERRIDES_FILE"
SETUP_OVERRIDES_FILE_DEFAULT = "setup_overrides.json"
SETUP_ENV_FILE_ENV = "SETUP_ENV_FILE"
SETUP_ENV_FILE_DEFAULT = ".env"

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

ENV_LINE_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")


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


def setup_env_file_path() -> Path:
    configured = os.getenv(SETUP_ENV_FILE_ENV, SETUP_ENV_FILE_DEFAULT).strip() or SETUP_ENV_FILE_DEFAULT
    path = Path(configured)
    if path.is_absolute():
        return path
    return (Path.cwd() / path).resolve()


def read_setup_overrides_payload(state_dir: Path) -> dict[str, Any]:
    payload = read_json(setup_overrides_path(state_dir))
    if not isinstance(payload, dict):
        return {"updated_at_utc": None, "values": {}}
    values = payload.get("values")
    if not isinstance(values, dict):
        return {"updated_at_utc": None, "values": {}}
    out: dict[str, Any] = {}
    for key, value in values.items():
        if key not in SETUP_ALLOWED_KEYS:
            continue
        out[key] = value
    updated_at = payload.get("updated_at_utc")
    if not isinstance(updated_at, str):
        updated_at = None
    return {"updated_at_utc": updated_at, "values": out}


def read_setup_overrides(state_dir: Path) -> dict[str, Any]:
    payload = read_setup_overrides_payload(state_dir)
    values = payload.get("values")
    if not isinstance(values, dict):
        return {}
    out: dict[str, Any] = {}
    for key, value in values.items():
        if key in SETUP_ALLOWED_KEYS:
            out[key] = value
    return out


def _normalize_setup_updates(updates: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in updates.items():
        if key not in SETUP_ALLOWED_KEYS:
            continue
        if value is None:
            normalized[key] = None
            continue
        if key in SETUP_BOOL_KEYS:
            as_bool = _to_bool(value)
            normalized[key] = as_bool
            continue
        text = str(value).strip()
        normalized[key] = text if text else None
    return normalized


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
    normalized = _normalize_setup_updates(updates)
    for key, value in normalized.items():
        if value is None:
            merged.pop(key, None)
            continue
        if key in SETUP_BOOL_KEYS:
            if not isinstance(value, bool):
                merged.pop(key, None)
                continue
            merged[key] = value
            continue
        merged[key] = value
    return write_setup_overrides(state_dir, merged)


def _render_env_line(key: str, value: Any) -> str:
    if key in SETUP_BOOL_KEYS and isinstance(value, bool):
        return f"{key}={'true' if value else 'false'}"
    text = str(value).replace("\n", " ").strip()
    return f"{key}={text}"


def update_setup_env_file(updates: dict[str, Any]) -> Path:
    path = setup_env_file_path()
    normalized = _normalize_setup_updates(updates)
    if not normalized:
        return path

    existing_lines: list[str] = []
    if path.exists():
        existing_lines = path.read_text(encoding="utf-8").splitlines()
    else:
        path.parent.mkdir(parents=True, exist_ok=True)

    indexed: dict[str, list[int]] = {}
    for idx, line in enumerate(existing_lines):
        match = ENV_LINE_RE.match(line)
        if not match:
            continue
        key = match.group(1)
        if key not in SETUP_ALLOWED_KEYS:
            continue
        indexed.setdefault(key, []).append(idx)

    delete_indexes: set[int] = set()
    append_lines: list[str] = []
    for key, value in normalized.items():
        replacement = None if value is None else _render_env_line(key, value)
        locations = indexed.get(key, [])

        if locations:
            first_idx = locations[0]
            if replacement is None:
                delete_indexes.update(locations)
            else:
                existing_lines[first_idx] = replacement
                if len(locations) > 1:
                    delete_indexes.update(locations[1:])
            continue

        if replacement is not None:
            append_lines.append(replacement)

    if delete_indexes:
        existing_lines = [line for idx, line in enumerate(existing_lines) if idx not in delete_indexes]

    final_lines = existing_lines[:]
    if append_lines:
        if final_lines and final_lines[-1].strip():
            final_lines.append("")
        final_lines.extend(append_lines)

    text = "\n".join(final_lines)
    if final_lines:
        text += "\n"
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)
    return path


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
