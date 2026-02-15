from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests


logger = logging.getLogger(__name__)
TIMEOUT_SECONDS = 30


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _to_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace("%", "")
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(int(value))
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "y", "on"}:
            return True
        if text in {"0", "false", "no", "n", "off"}:
            return False
    return None


def _smoothstep(value: float, edge0: float, edge1: float) -> float:
    if edge0 == edge1:
        return 1.0 if value >= edge1 else 0.0
    t = _clamp((value - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _saturating(value: float, scale: float) -> float:
    if value <= 0:
        return 0.0
    return value / (value + max(1e-6, scale))


def _parse_activity_time(activity: dict[str, Any]) -> datetime | None:
    start_date = activity.get("start_date")
    start_date_local = activity.get("start_date_local")
    for value in (start_date, start_date_local):
        if not isinstance(value, str):
            continue
        iso = value.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(iso)
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return None


def _to_utc_datetime(value: Any, fallback_tz: timezone | ZoneInfo) -> datetime | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=fallback_tz)
        return dt.astimezone(timezone.utc)
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

    location = payload.get("location") or {}
    tz_name = location.get("tz_id")
    try:
        local_tz: timezone | ZoneInfo = ZoneInfo(tz_name) if isinstance(tz_name, str) else timezone.utc
    except ZoneInfoNotFoundError:
        local_tz = timezone.utc

    forecast_days = payload.get("forecast", {}).get("forecastday", [])
    if not forecast_days:
        return None

    hourly = forecast_days[0].get("hour", [])
    if not hourly:
        return None

    activity_time_utc = activity_time.astimezone(timezone.utc)

    def _hour_distance(hour: dict[str, Any]) -> float:
        hour_dt = _to_utc_datetime(hour.get("time_epoch"), local_tz)
        if hour_dt is None:
            hour_dt = _to_utc_datetime(hour.get("time"), local_tz)
        if hour_dt is None:
            return float("inf")
        return abs((hour_dt - activity_time_utc).total_seconds())

    closest = min(hourly, key=_hour_distance)
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
        "tz_id": tz_name,
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
    rh = _clamp(humidity, 0.0, 100.0)
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


def calculate_misery_index_components(
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
    will_it_rain: bool | None = None,
    will_it_snow: bool | None = None,
) -> dict[str, float]:
    rh = _clamp(float(humidity), 0.0, 100.0)
    wind = max(0.0, float(wind_speed_mph))
    dew = float(dew_point_f)
    temp = float(temp_f)
    cloud = _clamp(_to_float(cloud_cover_pct) or 0.0, 0.0, 100.0)
    precip = max(0.0, _to_float(precip_in) or 0.0)
    rain_chance = _clamp(_to_float(chance_of_rain) or 0.0, 0.0, 100.0)
    snow_chance = _clamp(_to_float(chance_of_snow) or 0.0, 0.0, 100.0)

    hi = float(heat_index_f) if isinstance(heat_index_f, (int, float)) else _heat_index_f(temp, rh)
    wc = float(wind_chill_f) if isinstance(wind_chill_f, (int, float)) else _wind_chill_f(temp, wind)

    # Smoothly blend apparent temperature sources so we avoid branch cliffs.
    hot_weight = _smoothstep(temp, 75.0, 85.0)
    cold_weight = 1.0 - _smoothstep(temp, 45.0, 55.0)
    neutral_weight = max(0.0, 1.0 - hot_weight - cold_weight)
    apparent = (neutral_weight * temp) + (hot_weight * hi) + (cold_weight * wc)

    thermal_hot = max(0.0, apparent - 70.0)
    thermal_cold = max(0.0, 50.0 - apparent)

    thermal_hot_points = (0.90 * thermal_hot) + (0.018 * thermal_hot * thermal_hot)
    thermal_cold_points = (1.15 * thermal_cold) + (0.022 * thermal_cold * thermal_cold)

    dew_hot = max(0.0, dew - 60.0)
    dew_cold = max(0.0, 25.0 - dew)
    dew_hot_points = (0.38 * dew_hot) + (0.008 * dew_hot * dew_hot)
    dew_cold_points = 0.22 * dew_cold

    humidity_hot_points = max(0.0, rh - 72.0) * _smoothstep(temp, 78.0, 95.0) * 0.08
    dryness_cold_points = max(0.0, 32.0 - rh) * _smoothstep(50.0 - temp, 0.0, 20.0) * 0.10

    stagnant_hot_points = (
        max(0.0, 2.5 - wind)
        * _smoothstep(temp, 80.0, 95.0)
        * _smoothstep(rh, 65.0, 85.0)
        * 2.5
    )
    hot_breeze_relief = (
        max(0.0, min(wind, 16.0) - 2.0)
        * _smoothstep(temp, 82.0, 98.0)
        * _smoothstep(rh, 60.0, 85.0)
        * 0.35
    )

    # Wind chill already handles most thermal wind effects; this captures severe non-thermal exposure.
    gale_cold_points = max(0.0, wind - 22.0) * _smoothstep(45.0 - temp, 0.0, 20.0) * 0.22

    rain_intensity = _saturating(precip, 0.08)
    rain_points = 18.0 * rain_intensity
    rain_hot_points = 0.0
    rain_cold_points = 0.0
    if temp <= 60.0:
        rain_cold_points += rain_points
    elif temp >= 78.0:
        rain_hot_points += rain_points * 0.45
    else:
        rain_cold_points += rain_points * 0.35

    cold_rain_extra = _smoothstep(45.0 - temp, 0.0, 20.0) * 5.0 * rain_intensity

    rain_hint_points = 0.0
    if precip < 0.005 and rain_chance > 0:
        hint_load = (rain_chance / 100.0) ** 1.4
        if temp <= 60.0:
            rain_hint_points += 2.0 * hint_load
        elif temp >= 80.0:
            rain_hint_points += 1.6 * hint_load

    snow_signal = max(snow_chance / 100.0, rain_intensity if _is_snow_condition(condition_text) else 0.0)
    snow_flag = _is_snow_condition(condition_text)
    snow_bool = _to_bool(will_it_snow)
    if snow_bool is True:
        snow_flag = True
    if snow_chance >= 35.0:
        snow_flag = True

    snow_points = 0.0
    if snow_flag:
        snow_points = 8.0 + (10.0 * snow_signal)
        if temp <= 32.0:
            snow_points += 4.0

    sun_hot_points = 0.0
    cloud_hot_relief = 0.0
    cloud_cold_points = 0.0
    day_flag = _to_bool(is_day)
    if day_flag is True:
        cloud_fraction = cloud / 100.0
        sun_fraction = 1.0 - cloud_fraction
        sun_hot_points = sun_fraction * _smoothstep(temp, 78.0, 98.0) * 6.0
        cloud_hot_relief = cloud_fraction * _smoothstep(temp, 84.0, 100.0) * 2.5
        cloud_cold_points = cloud_fraction * _smoothstep(40.0 - temp, 0.0, 20.0) * 2.0

    hot_points = (
        thermal_hot_points
        + dew_hot_points
        + humidity_hot_points
        + stagnant_hot_points
        + rain_hot_points
        + sun_hot_points
    ) - (hot_breeze_relief + cloud_hot_relief)
    hot_points = max(0.0, hot_points)

    cold_points = (
        thermal_cold_points
        + dew_cold_points
        + dryness_cold_points
        + gale_cold_points
        + rain_cold_points
        + cold_rain_extra
        + rain_hint_points
        + snow_points
        + cloud_cold_points
    )

    raw_score = 100.0 + hot_points - cold_points
    bounded_score = _clamp(raw_score, -40.0, 240.0)

    return {
        "score": round(bounded_score, 1),
        "score_raw": round(raw_score, 1),
        "apparent_temp_f": round(apparent, 1),
        "hot_points": round(hot_points, 2),
        "cold_points": round(cold_points, 2),
        "component_thermal_hot": round(thermal_hot_points, 2),
        "component_thermal_cold": round(thermal_cold_points, 2),
        "component_dew_hot": round(dew_hot_points, 2),
        "component_dew_cold": round(dew_cold_points, 2),
        "component_humidity_hot": round(humidity_hot_points, 2),
        "component_dryness_cold": round(dryness_cold_points, 2),
        "component_stagnant_hot": round(stagnant_hot_points, 2),
        "component_hot_breeze_relief": round(hot_breeze_relief, 2),
        "component_gale_cold": round(gale_cold_points, 2),
        "component_rain_hot": round(rain_hot_points, 2),
        "component_rain_cold": round(rain_cold_points, 2),
        "component_cold_rain_extra": round(cold_rain_extra, 2),
        "component_rain_hint": round(rain_hint_points, 2),
        "component_snow": round(snow_points, 2),
        "component_sun_hot": round(sun_hot_points, 2),
        "component_cloud_hot_relief": round(cloud_hot_relief, 2),
        "component_cloud_cold": round(cloud_cold_points, 2),
    }


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
    will_it_rain: bool | None = None,
    will_it_snow: bool | None = None,
) -> float:
    components = calculate_misery_index_components(
        temp_f=temp_f,
        dew_point_f=dew_point_f,
        humidity=humidity,
        wind_speed_mph=wind_speed_mph,
        cloud_cover_pct=cloud_cover_pct,
        precip_in=precip_in,
        is_day=is_day,
        chance_of_rain=chance_of_rain,
        chance_of_snow=chance_of_snow,
        condition_text=condition_text,
        heat_index_f=heat_index_f,
        wind_chill_f=wind_chill_f,
        will_it_rain=will_it_rain,
        will_it_snow=will_it_snow,
    )
    return components["score"]


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


def get_misery_index_details_for_activity(
    activity: dict[str, Any],
    weather_api_key: str | None,
) -> dict[str, Any] | None:
    if not weather_api_key:
        return None

    start_latlng = activity.get("start_latlng")
    if not isinstance(start_latlng, list) or len(start_latlng) != 2:
        return None

    activity_time = _parse_activity_time(activity)
    if activity_time is None:
        return None

    lat, lon = start_latlng
    try:
        weather_data = _get_weather_data(weather_api_key, float(lat), float(lon), activity_time)
        aqi = _get_air_quality_index(weather_api_key, float(lat), float(lon))
    except requests.RequestException as exc:
        logger.error("Weather API request failed: %s", exc)
        return None

    if not weather_data:
        return {
            "misery_index": None,
            "misery_description": None,
            "aqi": aqi,
            "aqi_description": get_aqi_description(aqi),
            "misery_components": None,
            "weather": None,
        }

    temp_f = _to_float(weather_data.get("temp_f"))
    dew_point_f = _to_float(weather_data.get("dewpoint_f"))
    humidity = _to_float(weather_data.get("humidity"))
    wind_speed_mph = _to_float(weather_data.get("wind_mph"))

    if None in {temp_f, dew_point_f, humidity, wind_speed_mph}:
        return {
            "misery_index": None,
            "misery_description": None,
            "aqi": aqi,
            "aqi_description": get_aqi_description(aqi),
            "misery_components": None,
            "weather": {
                "temp_f": temp_f,
                "dewpoint_f": dew_point_f,
                "humidity": humidity,
                "wind_mph": wind_speed_mph,
                "cloud": _to_float(weather_data.get("cloud")),
                "precip_in": _to_float(weather_data.get("precip_in")),
                "condition_text": weather_data.get("condition_text"),
            },
        }

    components = calculate_misery_index_components(
        temp_f=temp_f,
        dew_point_f=dew_point_f,
        humidity=humidity,
        wind_speed_mph=wind_speed_mph,
        cloud_cover_pct=_to_float(weather_data.get("cloud")),
        precip_in=_to_float(weather_data.get("precip_in")),
        is_day=_to_bool(weather_data.get("is_day")),
        chance_of_rain=_to_float(weather_data.get("chance_of_rain")),
        chance_of_snow=_to_float(weather_data.get("chance_of_snow")),
        condition_text=(
            str(weather_data.get("condition_text"))
            if isinstance(weather_data.get("condition_text"), str)
            else None
        ),
        heat_index_f=_to_float(weather_data.get("heatindex_f")),
        wind_chill_f=_to_float(weather_data.get("windchill_f")),
        will_it_rain=_to_bool(weather_data.get("will_it_rain")),
        will_it_snow=_to_bool(weather_data.get("will_it_snow")),
    )

    misery = components["score"]
    return {
        "misery_index": misery,
        "misery_description": get_misery_index_description(misery),
        "aqi": aqi,
        "aqi_description": get_aqi_description(aqi),
        "misery_components": components,
        "weather": {
            "temp_f": temp_f,
            "dewpoint_f": dew_point_f,
            "humidity": humidity,
            "wind_mph": wind_speed_mph,
            "cloud": _to_float(weather_data.get("cloud")),
            "precip_in": _to_float(weather_data.get("precip_in")),
            "chance_of_rain": _to_float(weather_data.get("chance_of_rain")),
            "chance_of_snow": _to_float(weather_data.get("chance_of_snow")),
            "condition_text": weather_data.get("condition_text"),
            "is_day": _to_bool(weather_data.get("is_day")),
            "heatindex_f": _to_float(weather_data.get("heatindex_f")),
            "windchill_f": _to_float(weather_data.get("windchill_f")),
            "tz_id": weather_data.get("tz_id"),
        },
    }


def get_misery_index_for_activity(
    activity: dict[str, Any],
    weather_api_key: str | None,
) -> tuple[float | None, str | None, int | None, str | None]:
    details = get_misery_index_details_for_activity(activity, weather_api_key)
    if details is None:
        return None, None, None, None

    return (
        details.get("misery_index"),
        details.get("misery_description"),
        details.get("aqi"),
        details.get("aqi_description"),
    )
