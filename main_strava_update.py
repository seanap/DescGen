from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config import Settings
from stat_modules import beers_earned, week_stats
from stat_modules.crono_api import format_crono_line, get_crono_summary_for_activity
from stat_modules.intervals_data import get_intervals_activity_data
from stat_modules.misery_index import (
    get_misery_index_details_for_activity,
    get_misery_index_for_activity,
)
from stat_modules.smashrun import (
    aggregate_elevation_totals,
    get_activity_elevation_feet,
    get_activities as get_smashrun_activities,
    get_longest_streak,
    get_notables,
)
from stat_modules.vo2max import fetch_training_status_and_scores
from storage import is_activity_processed, mark_activity_processed, write_json
from strava_utils import StravaClient, get_gap_speed_mps, mps_to_pace


logger = logging.getLogger(__name__)


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


def _default_garmin_metrics() -> dict[str, Any]:
    return {
        "vo2max": "N/A",
        "training_status_key": "N/A",
        "training_status_emoji": "⚪",
        "acute_load": "N/A",
        "chronic_load": "N/A",
        "acwr_status": "N/A",
        "acwr_status_emoji": "⚪",
        "training_readiness_score": "N/A",
        "training_readiness_emoji": "⚪",
        "endurance_overall_score": "N/A",
        "hill_overall_score": "N/A",
        "average_hr": "N/A",
        "running_cadence": "N/A",
        "aerobic_training_effect": "N/A",
        "anaerobic_training_effect": "N/A",
        "training_effect_label": "N/A",
        "resting_hr": "N/A",
        "sleep_score": "N/A",
        "fitness_age": "N/A",
        "avg_grade_adjusted_speed": "N/A",
    }


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


def _is_treadmill(activity: dict[str, Any]) -> bool:
    return bool(activity.get("trainer")) and not activity.get("start_latlng")


def _build_treadmill_payload(activity: dict[str, Any]) -> dict[str, Any]:
    speed_mps = float(activity.get("average_speed", 0) or 0)
    speed_mph = speed_mps * 2.23694
    distance_meters = float(activity.get("distance", 0) or 0)
    distance_miles = distance_meters / 1609.34
    vertical_gain_ft = round(distance_miles * 5280 * 0.15)
    beers_treadmill = round(float(activity.get("calories", 0) or 0) / 150.0, 1)

    description = (
        "∠ Incline: 15%\n"
        f"⏲ Avg Speed: {speed_mph:.1f}mph\n"
        f"🗻 {vertical_gain_ft}' Treadmill Elevation\n"
        f"🍺 {beers_treadmill}"
    )
    is_walk = speed_mph < 4.0
    return {
        "type": "Walk" if is_walk else "Run",
        "name": "Max Incline Treadmill Walk" if is_walk else "Max Incline Treadmill Run",
        "description": description,
    }


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
        return _default_garmin_metrics()
    try:
        return fetch_training_status_and_scores(client)
    except Exception as exc:
        logger.error("Garmin data fetch failed: %s", exc)
        return _default_garmin_metrics()


def _merge_hr_cadence_from_strava(training: dict[str, Any], detailed_activity: dict[str, Any]) -> tuple[Any, Any]:
    average_hr = training.get("average_hr", "N/A")
    running_cadence = training.get("running_cadence", "N/A")

    strava_hr = detailed_activity.get("average_heartrate")
    if average_hr == "N/A" and isinstance(strava_hr, (int, float)):
        average_hr = int(round(strava_hr))

    strava_cadence = detailed_activity.get("average_cadence")
    if running_cadence == "N/A" and isinstance(strava_cadence, (int, float)):
        running_cadence = int(round(strava_cadence * 2 if strava_cadence < 130 else strava_cadence))

    return average_hr, running_cadence


def _build_description(
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
) -> str:
    achievements = intervals_payload.get("achievements", []) if intervals_payload else []
    norm_power = intervals_payload.get("norm_power", "N/A") if intervals_payload else "N/A"
    work = intervals_payload.get("work", "N/A") if intervals_payload else "N/A"
    efficiency = intervals_payload.get("efficiency", "N/A") if intervals_payload else "N/A"
    icu_summary = intervals_payload.get("icu_summary", "N/A") if intervals_payload else "N/A"

    distance_miles = round(float(detailed_activity.get("distance", 0) or 0) / 1609.34, 2)
    elapsed_seconds = int(
        detailed_activity.get("moving_time")
        or detailed_activity.get("elapsed_time")
        or 0
    )
    activity_time = _format_activity_time(elapsed_seconds)
    beers = beers_earned.calculate_beers(detailed_activity)

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

    average_hr, running_cadence = _merge_hr_cadence_from_strava(training, detailed_activity)

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

    vo2_value = training.get("vo2max")
    vo2_display = _display_number(vo2_value, decimals=1) if isinstance(vo2_value, (int, float)) else str(vo2_value)

    description = ""
    description += f"🏆 {longest_streak if longest_streak is not None else 'N/A'} days in a row\n"

    if notables:
        description += "\n".join([f"🏅 {notable}" for notable in notables]) + "\n"

    if achievements:
        description += "\n".join([f"🏅 {achievement}" for achievement in achievements]) + "\n"

    description += f"🌤️🌡️ Misery Index: {misery_display} {misery_desc_display} | 🏭 AQI: {aqi_display}{aqi_desc_display}\n"
    if crono_line:
        description += f"{crono_line}\n"
    description += (
        f"🌤️🚦 Training Readiness: {training.get('training_readiness_score', 'N/A')} "
        f"{training.get('training_readiness_emoji', '⚪')} | "
        f"💗 {training.get('resting_hr', 'N/A')} | 💤 {training.get('sleep_score', 'N/A')}\n"
    )

    description += (
        f"👟🏃 {gap_pace} | 🗺️ {distance_miles} | "
        f"🏔️ {int(round(elevation_feet)) if elevation_feet is not None else 'N/A'}' | "
        f"🕓 {activity_time} | 🍺 {beers:.1f}\n"
    )

    description += (
        f"👟👣 {running_cadence if running_cadence != 'N/A' else 'N/A'}spm | "
        f"💼 {work} | ⚡ {norm_power} | "
        f"💓 {average_hr if average_hr != 'N/A' else 'N/A'} | ⚙️{efficiency}\n"
    )

    description += (
        f"🚄 {training.get('training_status_emoji', '⚪')} {training.get('training_status_key', 'N/A')} | "
        f"{training.get('aerobic_training_effect', 'N/A')} : {training.get('anaerobic_training_effect', 'N/A')} - "
        f"{training.get('training_effect_label', 'N/A')}\n"
    )

    description += f"🚄 {icu_summary}\n"
    description += (
        f"🚄 🏋️ {training.get('chronic_load', 'N/A')} | 💦 {training.get('acute_load', 'N/A')} | "
        f"🗿 {load_ratio} - {training.get('acwr_status', 'N/A')} {training.get('acwr_status_emoji', '⚪')}\n"
    )

    description += (
        f"❤️‍🔥 {vo2_display} | ♾ Endur: {training.get('endurance_overall_score', 'N/A')} | "
        f"🗻 Hill: {training.get('hill_overall_score', 'N/A')}\n\n"
    )

    description += "7️⃣ Past 7 days:\n"
    description += (
        f"🏃 {week['gap']} | 🗺️ {week['distance']:.1f} | "
        f"🏔️ {int(round(week['elevation']))}' | 🕓 {week['duration']} | "
        f"🍺 {week['beers_earned']:.0f}\n"
    )

    description += "📅 Past 30 days:\n"
    description += (
        f"🏃 {month['gap']} | 🗺️ {month['distance']:.0f} | "
        f"🏔️ {int(round(month['elevation']))}' | 🕓 {month['duration']} | "
        f"🍺 {month['beers_earned']:.0f}\n"
    )

    description += "🌍 This Year:\n"
    description += (
        f"🏃 {year['gap']} | 🗺️ {year['distance']:.0f} | "
        f"🏔️ {int(round(year['elevation']))}' | 🕓 {year['duration']} | "
        f"🍺 {year['beers_earned']:.0f}\n"
    )

    return description


def run_once(force_update: bool = False, activity_id: int | None = None) -> dict[str, Any]:
    settings = Settings.from_env()
    settings.validate()
    settings.ensure_state_paths()

    _configure_logging(settings.log_level)
    logger.info("Starting update cycle.")

    strava_client = StravaClient(settings)

    activities = strava_client.get_recent_activities(per_page=5)
    if not activities:
        logger.info("No Strava activities found.")
        return {"status": "no_activities"}

    latest = activities[0]
    selected = latest
    target_activity_id = activity_id

    if target_activity_id is not None:
        target_activity_id = int(target_activity_id)
        selected = next(
            (activity for activity in activities if int(activity["id"]) == target_activity_id),
            {"id": target_activity_id},
        )
    elif not force_update:
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
            logger.info("No unprocessed activities in latest %s items.", len(activities))
            return {"status": "already_processed", "activity_id": int(latest["id"])}

    selected_activity_id = int(selected["id"])
    detailed_activity = strava_client.get_activity_details(selected_activity_id)
    selected.setdefault("start_date", detailed_activity.get("start_date"))

    if selected_activity_id != int(latest["id"]):
        logger.info(
            "Selected activity %s (latest is %s).",
            selected_activity_id,
            int(latest["id"]),
        )

    if _is_treadmill(detailed_activity):
        treadmill_payload = _build_treadmill_payload(detailed_activity)
        strava_client.update_activity(selected_activity_id, treadmill_payload)

        now = datetime.now(timezone.utc)
        payload = {
            "updated_at_utc": now.isoformat(),
            "activity_id": selected_activity_id,
            "activity_start_date": selected.get("start_date"),
            "description": treadmill_payload["description"],
            "source": "treadmill",
        }
        mark_activity_processed(settings.processed_log_file, selected_activity_id)
        write_json(settings.latest_json_file, payload)
        logger.info("Treadmill activity %s updated.", selected_activity_id)
        return {"status": "updated_treadmill", "activity_id": selected_activity_id}

    try:
        local_tz = ZoneInfo(settings.timezone)
    except ZoneInfoNotFoundError:
        logger.warning("Unknown timezone '%s'. Falling back to UTC.", settings.timezone)
        local_tz = timezone.utc

    now_local = datetime.now(local_tz)
    now_utc = now_local.astimezone(timezone.utc)
    year_start = datetime(now_local.year, 1, 1, tzinfo=local_tz).astimezone(timezone.utc)

    strava_activities = strava_client.get_activities_after(year_start)

    longest_streak = None
    notables: list[str] = []
    latest_elevation_feet = None
    smashrun_elevation_totals = {"week": 0.0, "month": 0.0, "year": 0.0}

    if settings.enable_smashrun and settings.smashrun_access_token:
        smashrun_activities = get_smashrun_activities(settings.smashrun_access_token)
        latest_elevation_feet = get_activity_elevation_feet(smashrun_activities, detailed_activity)
        smashrun_elevation_totals = aggregate_elevation_totals(
            smashrun_activities,
            now_utc,
            timezone_name=settings.timezone,
        )
        longest_streak = get_longest_streak(settings.smashrun_access_token)
        if selected_activity_id == int(latest["id"]):
            latest_smashrun_activity_id = (
                smashrun_activities[0].get("activityId") if smashrun_activities else None
            )
            notables = get_notables(
                settings.smashrun_access_token,
                latest_activity_id=latest_smashrun_activity_id,
            )
        else:
            logger.info("Skipping Smashrun notables because selected activity is not latest.")

    garmin_client = _get_garmin_client(settings)
    training = _get_garmin_metrics(garmin_client)
    garmin_period_fallback = week_stats.get_garmin_period_fallback(
        garmin_client,
        now_utc=now_utc,
        timezone_name=settings.timezone,
    )

    period_stats = week_stats.get_period_stats(
        strava_activities,
        smashrun_elevation_totals,
        now_utc,
        timezone_name=settings.timezone,
        garmin_period_fallback=garmin_period_fallback,
    )

    intervals_payload = None
    if settings.enable_intervals:
        intervals_payload = get_intervals_activity_data(
            settings.intervals_user_id,
            settings.intervals_api_key,
        )

    misery_index = misery_desc = aqi = aqi_desc = None
    weather_details = None
    if settings.enable_weather:
        weather_details = get_misery_index_details_for_activity(
            detailed_activity,
            settings.weather_api_key,
        )
        if weather_details:
            misery_index = weather_details.get("misery_index")
            misery_desc = weather_details.get("misery_description")
            aqi = weather_details.get("aqi")
            aqi_desc = weather_details.get("aqi_description")
        else:
            misery_index, misery_desc, aqi, aqi_desc = get_misery_index_for_activity(
                detailed_activity,
                settings.weather_api_key,
            )

    crono_line = None
    if settings.enable_crono_api:
        crono_summary = get_crono_summary_for_activity(
            activity=detailed_activity,
            timezone_name=settings.timezone,
            base_url=settings.crono_api_base_url,
            api_key=settings.crono_api_key,
            days=7,
        )
        crono_line = format_crono_line(crono_summary)

    description = _build_description(
        detailed_activity=detailed_activity,
        training=training,
        intervals_payload=intervals_payload,
        week=period_stats["week"],
        month=period_stats["month"],
        year=period_stats["year"],
        longest_streak=longest_streak,
        notables=notables,
        latest_elevation_feet=latest_elevation_feet,
        misery_index=misery_index,
        misery_index_description=misery_desc,
        air_quality_index=aqi,
        aqi_description=aqi_desc,
        crono_line=crono_line,
    )

    strava_client.update_activity(selected_activity_id, {"description": description})

    payload = {
        "updated_at_utc": now_utc.isoformat(),
        "activity_id": selected_activity_id,
        "activity_start_date": selected.get("start_date"),
        "description": description,
        "source": "standard",
        "period_stats": period_stats,
        "weather": weather_details,
    }
    mark_activity_processed(settings.processed_log_file, selected_activity_id)
    write_json(settings.latest_json_file, payload)

    logger.info("Activity %s updated successfully.", selected_activity_id)
    return {"status": "updated", "activity_id": selected_activity_id}


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
