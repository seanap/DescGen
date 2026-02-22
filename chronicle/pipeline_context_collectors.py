from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable

from .config import Settings
from .stat_modules.crono_api import format_crono_line, get_crono_summary_for_activity
from .stat_modules.misery_index import (
    get_misery_index_details_for_activity,
    get_misery_index_for_activity,
)
from .stat_modules.smashrun import (
    aggregate_elevation_totals,
    get_activity_elevation_feet,
    get_activity_record,
    get_activities as get_smashrun_activities,
    get_badges as get_smashrun_badges,
    get_notables,
    get_stats as get_smashrun_stats,
)


RunServiceCall = Callable[..., Any]
AsFloat = Callable[[Any], float | None]


def collect_smashrun_context(
    settings: Settings,
    detailed_activity: dict[str, Any],
    *,
    selected_activity_id: int,
    latest_activity_id: int,
    now_utc: datetime,
    service_state: dict[str, Any] | None,
    run_service_call: RunServiceCall,
    as_float: AsFloat,
    logger: logging.Logger | None = None,
) -> dict[str, Any]:
    local_logger = logger or logging.getLogger(__name__)
    context: dict[str, Any] = {
        "longest_streak": None,
        "notables": [],
        "latest_elevation_feet": None,
        "smashrun_elevation_totals": {"week": 0.0, "month": 0.0, "year": 0.0},
        "smashrun_activity_record": None,
        "smashrun_stats": None,
        "smashrun_badges": [],
    }

    if not (settings.enable_smashrun and settings.smashrun_access_token):
        return context

    smashrun_activities = run_service_call(
        settings,
        "smashrun.activities",
        get_smashrun_activities,
        settings.smashrun_access_token,
        service_state=service_state,
        cache_key="smashrun.activities:default",
        cache_ttl_seconds=settings.service_cache_ttl_seconds,
    )

    if smashrun_activities:
        context["smashrun_activity_record"] = get_activity_record(smashrun_activities, detailed_activity)
        context["latest_elevation_feet"] = get_activity_elevation_feet(smashrun_activities, detailed_activity)
        context["smashrun_elevation_totals"] = aggregate_elevation_totals(
            smashrun_activities,
            now_utc,
            timezone_name=settings.timezone,
        )
        if selected_activity_id == latest_activity_id:
            latest_smashrun_activity_id = smashrun_activities[0].get("activityId") if smashrun_activities else None
            notables_payload = run_service_call(
                settings,
                "smashrun.notables",
                get_notables,
                settings.smashrun_access_token,
                latest_activity_id=latest_smashrun_activity_id,
                service_state=service_state,
                cache_key=f"smashrun.notables:{latest_smashrun_activity_id or 'latest'}",
                cache_ttl_seconds=settings.service_cache_ttl_seconds,
            )
            if isinstance(notables_payload, list):
                context["notables"] = [str(item) for item in notables_payload if str(item).strip()]
        else:
            local_logger.info("Skipping Smashrun notables because selected activity is not latest.")

    smashrun_stats_payload = run_service_call(
        settings,
        "smashrun.stats",
        get_smashrun_stats,
        settings.smashrun_access_token,
        service_state=service_state,
        cache_key="smashrun.stats:default",
        cache_ttl_seconds=settings.service_cache_ttl_seconds,
    )
    if isinstance(smashrun_stats_payload, dict):
        context["smashrun_stats"] = smashrun_stats_payload
        streak_numeric = as_float(smashrun_stats_payload.get("longestStreak"))
        if streak_numeric is not None:
            context["longest_streak"] = int(round(streak_numeric))

    smashrun_badges_payload = run_service_call(
        settings,
        "smashrun.badges",
        get_smashrun_badges,
        settings.smashrun_access_token,
        service_state=service_state,
        cache_key="smashrun.badges:default",
        cache_ttl_seconds=settings.service_cache_ttl_seconds,
    )
    if isinstance(smashrun_badges_payload, list):
        context["smashrun_badges"] = [item for item in smashrun_badges_payload if isinstance(item, dict)]

    return context


def collect_weather_context(
    settings: Settings,
    detailed_activity: dict[str, Any],
    *,
    selected_activity_id: int,
    service_state: dict[str, Any] | None,
    run_service_call: RunServiceCall,
) -> dict[str, Any]:
    context = {
        "weather_details": None,
        "misery_index": None,
        "misery_desc": None,
        "aqi": None,
        "aqi_desc": None,
    }
    if not settings.enable_weather:
        return context

    weather_details = run_service_call(
        settings,
        "weather.details",
        get_misery_index_details_for_activity,
        detailed_activity,
        settings.weather_api_key,
        service_state=service_state,
        cache_key=f"weather.details:{selected_activity_id}",
        cache_ttl_seconds=settings.service_cache_ttl_seconds,
    )
    context["weather_details"] = weather_details
    if weather_details:
        context["misery_index"] = weather_details.get("misery_index")
        context["misery_desc"] = weather_details.get("misery_description")
        context["aqi"] = weather_details.get("aqi")
        context["aqi_desc"] = weather_details.get("aqi_description")
        return context

    fallback_weather = run_service_call(
        settings,
        "weather.fallback",
        get_misery_index_for_activity,
        detailed_activity,
        settings.weather_api_key,
        service_state=service_state,
        cache_key=f"weather.fallback:{selected_activity_id}",
        cache_ttl_seconds=settings.service_cache_ttl_seconds,
    )
    if isinstance(fallback_weather, tuple) and len(fallback_weather) == 4:
        context["misery_index"], context["misery_desc"], context["aqi"], context["aqi_desc"] = fallback_weather
    return context


def collect_crono_context(
    settings: Settings,
    detailed_activity: dict[str, Any],
    *,
    selected_activity_id: int,
    service_state: dict[str, Any] | None,
    run_service_call: RunServiceCall,
) -> tuple[dict[str, Any] | None, str | None]:
    if not settings.enable_crono_api:
        return None, None
    crono_summary = run_service_call(
        settings,
        "crono.summary",
        get_crono_summary_for_activity,
        service_state=service_state,
        cache_key=f"crono.summary:{selected_activity_id}:{settings.timezone}:7",
        cache_ttl_seconds=settings.service_cache_ttl_seconds,
        activity=detailed_activity,
        timezone_name=settings.timezone,
        base_url=settings.crono_api_base_url,
        api_key=settings.crono_api_key,
        days=7,
    )
    return crono_summary, format_crono_line(crono_summary)
