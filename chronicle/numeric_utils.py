from __future__ import annotations

from typing import Any


def as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def as_int(value: Any) -> int | None:
    parsed = as_float(value)
    if parsed is None:
        return None
    return int(round(parsed))


def seconds_to_hms(value: Any, *, none_value: str = "N/A") -> str:
    parsed = as_float(value)
    if parsed is None or parsed < 0:
        return none_value
    total = int(round(parsed))
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def mps_to_pace(value: Any, *, include_unit: bool = True, none_value: str = "N/A") -> str:
    speed_mps = as_float(value)
    if speed_mps is None or speed_mps <= 0:
        return none_value
    pace_min_per_mile = (1609.34 / speed_mps) / 60.0
    minutes = int(pace_min_per_mile)
    seconds = int(round((pace_min_per_mile - minutes) * 60))
    if seconds == 60:
        minutes += 1
        seconds = 0
    pace = f"{minutes}:{seconds:02d}"
    if include_unit:
        return f"{pace}/mi"
    return pace


def mps_to_mph(value: Any, *, include_unit: bool = True, none_value: str = "N/A") -> str:
    speed_mps = as_float(value)
    if speed_mps is None or speed_mps <= 0:
        return none_value
    mph = f"{speed_mps * 2.23694:.1f}"
    if include_unit:
        return f"{mph} mph"
    return mph


def meters_to_feet_int(value: Any, *, none_value: str = "N/A") -> int | str:
    meters = as_float(value)
    if meters is None:
        return none_value
    return int(round(meters * 3.28084))


def meters_to_miles(value: Any, *, include_unit: bool = True, none_value: str = "N/A") -> str:
    meters = as_float(value)
    if meters is None or meters < 0:
        return none_value
    miles = f"{meters / 1609.34:.2f}"
    if include_unit:
        return f"{miles} mi"
    return miles
