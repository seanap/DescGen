from __future__ import annotations

import logging
import math
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


def _to_utc_datetime(value: Any) -> datetime | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _get_weather_data(
    api_key: str,
    lat: float,
    lon: float,
    activity_time: datetime,
) -> dict[str, Any] | None:
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
        return None

    hourly = forecast_days[0].get("hour", [])
    if not hourly:
        return None

    closest = min(
        hourly,
        key=lambda hour: abs(
            (
                _to_utc_datetime(hour.get("time_epoch"))
                or _to_utc_datetime(hour.get("time"))
                or activity_time.astimezone(timezone.utc)
            )
            - activity_time.astimezone(timezone.utc)
        ),
    )
    condition = closest.get("condition") or {}
    return {
        "temp_f": closest.get("temp_f"),
        "dewpoint_f": closest.get("dewpoint_f"),
        "humidity": closest.get("humidity"),
        "wind_mph": closest.get("wind_mph"),
        "cloud": closest.get("cloud"),
        "precip_in": closest.get("precip_in"),
        "is_day": closest.get("is_day"),
        "chance_of_rain": closest.get("chance_of_rain"),
        "chance_of_snow": closest.get("chance_of_snow"),
        "will_it_rain": closest.get("will_it_rain"),
        "will_it_snow": closest.get("will_it_snow"),
        "condition_text": condition.get("text"),
        "heatindex_f": closest.get("heatindex_f"),
        "windchill_f": closest.get("windchill_f"),
    }


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


def _heat_index_f(temp_f: float, humidity: float) -> float:
    rh = max(0.0, min(100.0, humidity))
    simple = 0.5 * (temp_f + 61.0 + ((temp_f - 68.0) * 1.2) + (rh * 0.094))
    approx = (simple + temp_f) / 2.0
    if approx < 80:
        return approx

    hi = (
        -42.379
        + 2.04901523 * temp_f
        + 10.14333127 * rh
        - 0.22475541 * temp_f * rh
        - 0.00683783 * temp_f * temp_f
        - 0.05481717 * rh * rh
        + 0.00122874 * temp_f * temp_f * rh
        + 0.00085282 * temp_f * rh * rh
        - 0.00000199 * temp_f * temp_f * rh * rh
    )

    if rh < 13 and 80 <= temp_f <= 112:
        hi -= ((13 - rh) / 4.0) * math.sqrt((17 - abs(temp_f - 95.0)) / 17.0)
    elif rh > 85 and 80 <= temp_f <= 87:
        hi += ((rh - 85) / 10.0) * ((87 - temp_f) / 5.0)
    return hi


def _wind_chill_f(temp_f: float, wind_speed_mph: float) -> float:
    if temp_f > 50 or wind_speed_mph <= 3:
        return temp_f
    return (
        35.74
        + (0.6215 * temp_f)
        - (35.75 * (wind_speed_mph ** 0.16))
        + (0.4275 * temp_f * (wind_speed_mph ** 0.16))
    )


def _is_snow_condition(condition_text: str | None) -> bool:
    if not condition_text:
        return False
    text = condition_text.lower()
    return any(
        token in text
        for token in ("snow", "sleet", "ice pellets", "blizzard", "flurr", "freezing rain")
    )


def _rain_points(precip_in: float | None) -> float:
    if precip_in is None:
        return 0.0
    if precip_in >= 0.30:
        return 18.0
    if precip_in >= 0.10:
        return 10.0
    if precip_in >= 0.03:
        return 6.0
    if precip_in >= 0.01:
        return 2.0
    return 0.0


def calculate_misery_index(
    temp_f: float,
    dew_point_f: float,
    humidity: float,
    wind_speed_mph: float,
    *,
    cloud_cover_pct: float | None = None,
    precip_in: float | None = None,
    is_day: bool | None = None,
    chance_of_rain: float | None = None,
    chance_of_snow: float | None = None,
    condition_text: str | None = None,
    heat_index_f: float | None = None,
    wind_chill_f: float | None = None,
) -> float:
    hi = float(heat_index_f) if isinstance(heat_index_f, (int, float)) else _heat_index_f(temp_f, humidity)
    wc = float(wind_chill_f) if isinstance(wind_chill_f, (int, float)) else _wind_chill_f(temp_f, wind_speed_mph)

    if temp_f >= 80:
        thermal_f = hi
    elif temp_f <= 50:
        thermal_f = wc
    else:
        thermal_f = temp_f

    hot_points = 0.0
    cold_points = 0.0

    # Symmetric center model: 100 is ideal, >100 is heat stress, <100 is cold stress.
    if thermal_f > 70:
        hot_points += (thermal_f - 70.0) * 1.0
    elif thermal_f < 50:
        cold_points += (50.0 - thermal_f) * 1.5

    # Dew point bands from NWS comfort guidance.
    if dew_point_f > 65:
        hot_points += (dew_point_f - 65.0) * 0.8
    elif dew_point_f < 35:
        cold_points += (35.0 - dew_point_f) * 0.4

    # Additional humidity stress at hot and very dry extremes.
    if temp_f >= 75 and humidity >= 85:
        hot_points += (humidity - 85.0) * 0.2
    elif temp_f <= 70 and humidity <= 25:
        cold_points += (25.0 - humidity) * 0.2

    # Breeze matters: stagnant, humid heat feels much worse; strong cold wind hurts.
    if temp_f >= 80 and humidity >= 70 and wind_speed_mph < 3:
        hot_points += 8.0
    elif temp_f >= 85 and wind_speed_mph >= 10:
        hot_points = max(0.0, hot_points - min(6.0, (wind_speed_mph - 9.0) * 0.5))
    if temp_f <= 55 and wind_speed_mph >= 18:
        cold_points += min(8.0, (wind_speed_mph - 17.0) * 0.6)

    rain_points = _rain_points(precip_in)
    if rain_points > 0:
        if temp_f <= 60:
            cold_points += rain_points
        elif temp_f >= 75:
            hot_points += rain_points * 0.5
        else:
            cold_points += rain_points * 0.5
        if temp_f <= 45:
            cold_points += 8.0

    snow_flag = _is_snow_condition(condition_text)
    if isinstance(chance_of_snow, (int, float)) and chance_of_snow >= 40:
        snow_flag = True
    if snow_flag:
        cold_points += 18.0 if (precip_in or 0.0) >= 0.10 else 12.0

    # Sunshine can worsen hot runs; overcast can make cold runs feel gloomier/colder.
    if is_day and isinstance(cloud_cover_pct, (int, float)):
        cloud = float(cloud_cover_pct)
        if temp_f >= 80 and cloud <= 20:
            hot_points += 6.0
        elif temp_f >= 80 and cloud >= 80:
            hot_points = max(0.0, hot_points - 3.0)
        elif temp_f <= 40 and cloud >= 80:
            cold_points += 3.0

    # Forecast-only chance fields can hint discomfort even if observed precip is near zero.
    if isinstance(chance_of_rain, (int, float)) and chance_of_rain >= 70 and rain_points == 0:
        if temp_f <= 60:
            cold_points += 1.0
        elif temp_f >= 75:
            hot_points += 1.0

    score = 100.0 + hot_points - cold_points
    return round(score, 1)


def get_misery_index_description(misery_index: float) -> str:
    if misery_index < 20:
        return "☠️⚠️ High risk (cold)"
    if 20 <= misery_index < 30:
        return "😡 Miserable (cold)"
    if 30 <= misery_index < 40:
        return "🥶 Oppressively cold"
    if 40 <= misery_index < 50:
        return "😰 Very uncomfortable (cold)"
    if 50 <= misery_index < 60:
        return "😓 Moderate uncomfortable (cold)"
    if 60 <= misery_index < 70:
        return "😕 Mild uncomfortable (cold)"
    if 70 <= misery_index < 130:
        return "😀 Perfect"
    if 130 <= misery_index < 140:
        return "😕 Mild uncomfortable"
    if 140 <= misery_index < 150:
        return "😓 Moderate uncomfortable"
    if 150 <= misery_index < 160:
        return "😰 Very uncomfortable"
    if 160 <= misery_index < 170:
        return "🥵 Oppressive"
    if 170 <= misery_index < 180:
        return "😡 Miserable"
    if misery_index >= 180:
        return "☠️⚠️ High risk"
    return "😀 Perfect"


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
        weather_data = _get_weather_data(
            weather_api_key, float(lat), float(lon), activity_time
        )
        aqi = _get_air_quality_index(weather_api_key, float(lat), float(lon))
    except requests.RequestException as exc:
        logger.error("Weather API request failed: %s", exc)
        return None, None, None, None

    if not weather_data:
        return None, None, aqi, get_aqi_description(aqi)

    temp_f = weather_data.get("temp_f")
    dew_point_f = weather_data.get("dewpoint_f")
    humidity = weather_data.get("humidity")
    wind_speed_mph = weather_data.get("wind_mph")
    if None in {temp_f, dew_point_f, humidity, wind_speed_mph}:
        return None, None, aqi, get_aqi_description(aqi)

    misery = calculate_misery_index(
        float(temp_f),
        float(dew_point_f),
        float(humidity),
        float(wind_speed_mph),
        cloud_cover_pct=(
            float(weather_data["cloud"])
            if isinstance(weather_data.get("cloud"), (int, float))
            else None
        ),
        precip_in=(
            float(weather_data["precip_in"])
            if isinstance(weather_data.get("precip_in"), (int, float))
            else None
        ),
        is_day=bool(weather_data.get("is_day")) if weather_data.get("is_day") is not None else None,
        chance_of_rain=(
            float(weather_data["chance_of_rain"])
            if isinstance(weather_data.get("chance_of_rain"), (int, float))
            else None
        ),
        chance_of_snow=(
            float(weather_data["chance_of_snow"])
            if isinstance(weather_data.get("chance_of_snow"), (int, float))
            else None
        ),
        condition_text=(
            str(weather_data["condition_text"])
            if isinstance(weather_data.get("condition_text"), str)
            else None
        ),
        heat_index_f=(
            float(weather_data["heatindex_f"])
            if isinstance(weather_data.get("heatindex_f"), (int, float))
            else None
        ),
        wind_chill_f=(
            float(weather_data["windchill_f"])
            if isinstance(weather_data.get("windchill_f"), (int, float))
            else None
        ),
    )
    return misery, get_misery_index_description(misery), aqi, get_aqi_description(aqi)
