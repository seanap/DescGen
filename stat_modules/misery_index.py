from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import requests


logger = logging.getLogger(__name__)
TIMEOUT_SECONDS = 30


def _parse_activity_time(activity: dict[str, Any]) -> datetime | None:
    start_date = activity.get("start_date")
    start_date_local = activity.get("start_date_local")
    for value in (start_date, start_date_local):
        if not isinstance(value, str):
            continue
        iso = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(iso)
        except ValueError:
            continue
    return None


def _get_weather_data(api_key: str, lat: float, lon: float, activity_time: datetime) -> tuple[float | None, float | None, float | None, float | None]:
    activity_date = activity_time.astimezone(timezone.utc).date()
    today_date = datetime.now(timezone.utc).date()
    endpoint = "history.json" if activity_date < today_date else "forecast.json"
    date_str = activity_date.strftime("%Y-%m-%d")

    response = requests.get(
        f"http://api.weatherapi.com/v1/{endpoint}",
        params={"key": api_key, "q": f"{lat},{lon}", "dt": date_str},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    forecast_days = payload.get("forecast", {}).get("forecastday", [])
    if not forecast_days:
        return None, None, None, None

    hourly = forecast_days[0].get("hour", [])
    if not hourly:
        return None, None, None, None

    closest = min(
        hourly,
        key=lambda hour: abs(
            datetime.strptime(hour["time"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc) - activity_time.astimezone(timezone.utc)
        ),
    )
    return (
        closest.get("temp_f"),
        closest.get("dewpoint_f"),
        closest.get("humidity"),
        closest.get("wind_mph"),
    )


def _get_air_quality_index(api_key: str, lat: float, lon: float) -> int | None:
    response = requests.get(
        "http://api.weatherapi.com/v1/current.json",
        params={"key": api_key, "q": f"{lat},{lon}", "aqi": "yes"},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    index_value = payload.get("current", {}).get("air_quality", {}).get("us-epa-index")
    if index_value is None:
        return None
    try:
        return int(index_value)
    except (TypeError, ValueError):
        return None


def calculate_misery_index(temp_f: float, dew_point_f: float, humidity: float, wind_speed_mph: float) -> float:
    misery = (temp_f + ((dew_point_f * 2) + humidity) / 3) - (wind_speed_mph * (1 - (humidity / 100)))
    return round(misery, 1)


def get_misery_index_description(misery_index: float) -> str:
    if 130 <= misery_index < 140:
        return "😅 Mild"
    if 140 <= misery_index < 145:
        return "😓 Moderate"
    if 145 <= misery_index < 150:
        return "😰 Very"
    if 150 <= misery_index < 155:
        return "🥵 Oppressive"
    if 155 <= misery_index < 160:
        return "😡 Miserable"
    if misery_index >= 160:
        return "☠️⚠️ High risk"
    return "😀 Pleasant"


def get_aqi_description(us_epa_index: int | None) -> str:
    aqi_descriptions = {1: "😃", 2: "🙂", 3: "😐", 4: "😷", 5: "🤢", 6: "☠️"}
    return aqi_descriptions.get(us_epa_index, "Unknown")


def get_misery_index_for_activity(
    activity: dict[str, Any], weather_api_key: str | None
) -> tuple[float | None, str | None, int | None, str | None]:
    if not weather_api_key:
        return None, None, None, None

    start_latlng = activity.get("start_latlng")
    if not isinstance(start_latlng, list) or len(start_latlng) != 2:
        return None, None, None, None

    activity_time = _parse_activity_time(activity)
    if activity_time is None:
        return None, None, None, None

    lat, lon = start_latlng
    try:
        temp_f, dew_point_f, humidity, wind_speed_mph = _get_weather_data(
            weather_api_key, float(lat), float(lon), activity_time
        )
        aqi = _get_air_quality_index(weather_api_key, float(lat), float(lon))
    except requests.RequestException as exc:
        logger.error("Weather API request failed: %s", exc)
        return None, None, None, None

    if None in {temp_f, dew_point_f, humidity, wind_speed_mph}:
        return None, None, aqi, get_aqi_description(aqi)

    misery = calculate_misery_index(
        float(temp_f), float(dew_point_f), float(humidity), float(wind_speed_mph)
    )
    return misery, get_misery_index_description(misery), aqi, get_aqi_description(aqi)
