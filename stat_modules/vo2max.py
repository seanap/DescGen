from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any


logger = logging.getLogger(__name__)


def safe_get(value: Any, keys: list[Any], default: Any = "N/A") -> Any:
    cursor = value
    for key in keys:
        if isinstance(cursor, dict):
            cursor = cursor.get(key, default)
        elif isinstance(cursor, list) and isinstance(key, int):
            if 0 <= key < len(cursor):
                cursor = cursor[key]
            else:
                return default
        else:
            return default
    return cursor


def _default_metrics() -> dict[str, Any]:
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
        "readiness_level": "N/A",
        "readiness_feedback": "N/A",
        "recovery_time_hours": "N/A",
        "readiness_factors": {},
        "load_tunnel_min": "N/A",
        "load_tunnel_max": "N/A",
        "weekly_training_load": "N/A",
        "fitness_trend": "N/A",
        "load_level_trend": "N/A",
        "daily_acwr_ratio": "N/A",
        "acwr_percent": "N/A",
        "garmin_last_activity": {},
        "fitness_age_details": {},
        "garmin_badges": [],
        "garmin_segment_notables": [],
    }


def _as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _as_int(value: Any) -> int | None:
    parsed = _as_float(value)
    if parsed is None:
        return None
    return int(round(parsed))


def _seconds_to_hms(value: Any) -> str:
    parsed = _as_float(value)
    if parsed is None or parsed < 0:
        return "N/A"
    total = int(round(parsed))
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _meters_to_miles(value: Any) -> str:
    parsed = _as_float(value)
    if parsed is None or parsed < 0:
        return "N/A"
    return f"{parsed / 1609.34:.2f} mi"


def _meters_to_feet(value: Any) -> int | str:
    parsed = _as_float(value)
    if parsed is None:
        return "N/A"
    return int(round(parsed * 3.28084))


def _mps_to_mph(value: Any) -> str:
    parsed = _as_float(value)
    if parsed is None or parsed <= 0:
        return "N/A"
    return f"{parsed * 2.23694:.1f} mph"


def _mps_to_pace(value: Any) -> str:
    speed_mps = _as_float(value)
    if speed_mps is None or speed_mps <= 0:
        return "N/A"
    pace_min_per_mile = (1609.34 / speed_mps) / 60.0
    minutes = int(pace_min_per_mile)
    seconds = int(round((pace_min_per_mile - minutes) * 60))
    if seconds == 60:
        minutes += 1
        seconds = 0
    return f"{minutes}:{seconds:02d}/mi"


def _zone_summary(activity: dict[str, Any], prefix: str) -> str:
    parts: list[str] = []
    for zone_id in range(1, 6):
        value = activity.get(f"{prefix}{zone_id}")
        seconds = _as_float(value)
        if seconds is None or seconds <= 0:
            continue
        parts.append(f"Z{zone_id} {_seconds_to_hms(seconds)}")
    return " | ".join(parts) if parts else "N/A"


def _segment_rank_label(rank: int) -> str:
    if rank == 1:
        return "PR"
    if rank == 2:
        return "2nd"
    return "3rd"


def _segment_candidates(last_activity: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for key in ("segmentEfforts", "segment_efforts", "segments", "segmentResults", "segment_results"):
        value = last_activity.get(key)
        if isinstance(value, list):
            candidates.extend(item for item in value if isinstance(item, dict))
    return candidates


def _normalize_garmin_segment_notables(last_activity: dict[str, Any]) -> list[str]:
    selected: dict[str, tuple[int, int | None, str]] = {}
    for effort in _segment_candidates(last_activity):
        rank = _as_int(
            effort.get("pr_rank")
            or effort.get("prRank")
            or effort.get("rank")
            or effort.get("segmentRank")
            or effort.get("leaderboardRank")
            or effort.get("place")
        )
        if rank is None or rank not in (1, 2, 3):
            continue

        segment = effort.get("segment")
        segment_name = ""
        segment_id = ""
        if isinstance(segment, dict):
            segment_name = str(segment.get("name") or "").strip()
            segment_id = str(segment.get("id") or "").strip()
        if not segment_name:
            segment_name = str(
                effort.get("segmentName")
                or effort.get("name")
                or effort.get("segment_name")
                or "Unknown Segment"
            ).strip()
        if not segment_id:
            segment_id = segment_name.lower()

        elapsed_seconds = _as_int(
            effort.get("elapsed_time")
            or effort.get("elapsedTime")
            or effort.get("elapsedTimeInSeconds")
            or effort.get("moving_time")
            or effort.get("movingTime")
        )
        time_display = _seconds_to_hms(elapsed_seconds) if elapsed_seconds is not None else "N/A"
        line = f"Garmin {_segment_rank_label(rank)}: {segment_name} ({time_display})"

        existing = selected.get(segment_id)
        if existing is None:
            selected[segment_id] = (rank, elapsed_seconds, line)
            continue
        current_rank, current_seconds, _ = existing
        better_rank = rank < current_rank
        better_time = (
            rank == current_rank
            and elapsed_seconds is not None
            and (current_seconds is None or elapsed_seconds < current_seconds)
        )
        if better_rank or better_time:
            selected[segment_id] = (rank, elapsed_seconds, line)

    ordered = sorted(selected.values(), key=lambda item: (item[0], item[1] if item[1] is not None else 10**9, item[2]))
    return [item[2] for item in ordered]


def _normalize_garmin_badges(payload: Any, max_items: int = 20) -> list[str]:
    if isinstance(payload, dict):
        for key in ("badges", "items", "results"):
            nested = payload.get(key)
            if isinstance(nested, list):
                payload = nested
                break
    if not isinstance(payload, list):
        return []

    badges: list[str] = []
    seen: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        title = str(item.get("badgeName") or item.get("badgeTypeName") or item.get("name") or "").strip()
        if not title:
            continue
        level = _as_int(item.get("badgeLevel") or item.get("level") or item.get("currentLevel"))
        suffix = f" (L{level})" if level is not None and level > 0 else ""
        line = f"Garmin: {title}{suffix}"
        if line in seen:
            continue
        seen.add(line)
        badges.append(line)
        if len(badges) >= max_items:
            break
    return badges


def _build_garmin_last_activity_context(last_activity: dict[str, Any]) -> dict[str, Any]:
    avg_power = _as_float(last_activity.get("avgPower"))
    norm_power = _as_float(last_activity.get("normPower"))
    max_power = _as_float(last_activity.get("maxPower"))
    return {
        "activity_name": str(last_activity.get("activityName") or "N/A"),
        "activity_type": str(safe_get(last_activity, ["activityType", "typeKey"], default="N/A") or "N/A"),
        "start_local": str(last_activity.get("startTimeLocal") or "N/A"),
        "distance_miles": _meters_to_miles(last_activity.get("distance")),
        "duration": _seconds_to_hms(last_activity.get("duration")),
        "moving_time": _seconds_to_hms(last_activity.get("movingDuration")),
        "elapsed_time": _seconds_to_hms(last_activity.get("elapsedDuration")),
        "average_pace": _mps_to_pace(last_activity.get("averageSpeed")),
        "average_speed_mph": _mps_to_mph(last_activity.get("averageSpeed")),
        "max_speed_mph": _mps_to_mph(last_activity.get("maxSpeed")),
        "gap_pace": _mps_to_pace(last_activity.get("avgGradeAdjustedSpeed")),
        "elevation_gain_feet": _meters_to_feet(last_activity.get("elevationGain")),
        "elevation_loss_feet": _meters_to_feet(last_activity.get("elevationLoss")),
        "avg_elevation_feet": _meters_to_feet(last_activity.get("avgElevation")),
        "max_elevation_feet": _meters_to_feet(last_activity.get("maxElevation")),
        "min_elevation_feet": _meters_to_feet(last_activity.get("minElevation")),
        "average_hr": int(round(_as_float(last_activity.get("averageHR")) or 0))
        if isinstance(last_activity.get("averageHR"), (int, float))
        else "N/A",
        "max_hr": int(round(_as_float(last_activity.get("maxHR")) or 0))
        if isinstance(last_activity.get("maxHR"), (int, float))
        else "N/A",
        "avg_power_w": int(round(avg_power)) if avg_power is not None else "N/A",
        "norm_power_w": int(round(norm_power)) if norm_power is not None else "N/A",
        "max_power_w": int(round(max_power)) if max_power is not None else "N/A",
        "avg_ground_contact_time_ms": int(round(_as_float(last_activity.get("avgGroundContactTime")) or 0))
        if isinstance(last_activity.get("avgGroundContactTime"), (int, float))
        else "N/A",
        "avg_vertical_ratio_pct": (
            f"{(_as_float(last_activity.get('avgVerticalRatio')) or 0.0):.1f}%"
            if isinstance(last_activity.get("avgVerticalRatio"), (int, float))
            else "N/A"
        ),
        "avg_vertical_oscillation_mm": int(round(_as_float(last_activity.get("avgVerticalOscillation")) or 0))
        if isinstance(last_activity.get("avgVerticalOscillation"), (int, float))
        else "N/A",
        "avg_stride_length_m": (
            f"{(_as_float(last_activity.get('avgStrideLength')) or 0.0):.2f} m"
            if isinstance(last_activity.get("avgStrideLength"), (int, float))
            else "N/A"
        ),
        "avg_respiration_rate": (
            f"{(_as_float(last_activity.get('avgRespirationRate')) or 0.0):.1f} brpm"
            if isinstance(last_activity.get("avgRespirationRate"), (int, float))
            else "N/A"
        ),
        "max_respiration_rate": (
            f"{(_as_float(last_activity.get('maxRespirationRate')) or 0.0):.1f} brpm"
            if isinstance(last_activity.get("maxRespirationRate"), (int, float))
            else "N/A"
        ),
        "steps": int(round(_as_float(last_activity.get("steps")) or 0))
        if isinstance(last_activity.get("steps"), (int, float))
        else "N/A",
        "lap_count": int(round(_as_float(last_activity.get("lapCount")) or 0))
        if isinstance(last_activity.get("lapCount"), (int, float))
        else "N/A",
        "hr_zone_summary": _zone_summary(last_activity, "hrTimeInZone_"),
        "power_zone_summary": _zone_summary(last_activity, "powerTimeInZone_"),
        "is_pr": bool(last_activity.get("pr")),
    }


def fetch_training_status_and_scores(client: Any) -> dict[str, Any]:
    metrics = _default_metrics()
    try:
        last_activity = client.get_last_activity() or {}
    except Exception as exc:
        logger.error("Failed to fetch Garmin last activity: %s", exc)
        return metrics

    start_time_gmt = last_activity.get("startTimeGMT")
    duration_seconds = int(last_activity.get("duration", 0) or 0)
    if not start_time_gmt:
        return metrics

    try:
        start_time_dt = datetime.strptime(start_time_gmt, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return metrics

    end_time_dt = start_time_dt + timedelta(seconds=duration_seconds)
    start_date = start_time_dt.strftime("%Y-%m-%d")
    end_date = end_time_dt.strftime("%Y-%m-%d")

    try:
        training_status = client.get_training_status(end_date) or {}
    except Exception as exc:
        logger.error("Failed to fetch Garmin training status: %s", exc)
        training_status = {}

    latest_status_data = safe_get(
        training_status,
        ["mostRecentTrainingStatus", "latestTrainingStatusData", "3417115846"],
        default={},
    )
    if not isinstance(latest_status_data, dict):
        latest_status_data = {}
    acute_load_dto = latest_status_data.get("acuteTrainingLoadDTO")
    if not isinstance(acute_load_dto, dict):
        acute_load_dto = {}

    feedback = safe_get(
        training_status,
        ["mostRecentTrainingStatus", "latestTrainingStatusData", "3417115846", "trainingStatusFeedbackPhrase"],
    )
    acwr_status_raw = safe_get(
        training_status,
        ["mostRecentTrainingStatus", "latestTrainingStatusData", "3417115846", "acuteTrainingLoadDTO", "acwrStatus"],
    )

    metrics["vo2max"] = safe_get(training_status, ["mostRecentVO2Max", "generic", "vo2MaxPreciseValue"])
    metrics["chronic_load"] = safe_get(
        training_status,
        ["mostRecentTrainingStatus", "latestTrainingStatusData", "3417115846", "acuteTrainingLoadDTO", "dailyTrainingLoadChronic"],
    )
    metrics["acute_load"] = safe_get(
        training_status,
        ["mostRecentTrainingStatus", "latestTrainingStatusData", "3417115846", "acuteTrainingLoadDTO", "dailyTrainingLoadAcute"],
    )
    metrics["load_tunnel_min"] = latest_status_data.get("loadTunnelMin", "N/A")
    metrics["load_tunnel_max"] = latest_status_data.get("loadTunnelMax", "N/A")
    metrics["weekly_training_load"] = latest_status_data.get("weeklyTrainingLoad", "N/A")
    metrics["fitness_trend"] = latest_status_data.get("fitnessTrend", "N/A")
    metrics["load_level_trend"] = latest_status_data.get("loadLevelTrend", "N/A")
    metrics["daily_acwr_ratio"] = acute_load_dto.get("dailyAcuteChronicWorkloadRatio", "N/A")
    metrics["acwr_percent"] = acute_load_dto.get("acwrPercent", "N/A")

    status_text = feedback.split("_")[0].capitalize() if isinstance(feedback, str) and feedback else "N/A"
    metrics["training_status_key"] = status_text
    metrics["training_status_emoji"] = {
        "Overreaching": "🔴",
        "Peaking": "🟣",
        "Productive": "🟢",
        "Maintaining": "🟡",
        "Recovery": "🔵",
        "Strained": "😣",
        "Unproductive": "🟠",
        "Detraining": "⚫",
        "No Status": "⚪",
        "Paused": "⚫",
    }.get(status_text, "⚪")

    acwr_status = acwr_status_raw if isinstance(acwr_status_raw, str) else "N/A"
    metrics["acwr_status"] = acwr_status.capitalize() if acwr_status != "N/A" else "N/A"
    metrics["acwr_status_emoji"] = {"OPTIMAL": "🟢", "HIGH": "🔴", "LOW": "🔴", "N/A": "⚪"}.get(acwr_status, "⚪")

    average_hr = last_activity.get("averageHR")
    running_cadence = last_activity.get("averageRunningCadenceInStepsPerMinute")
    aerobic_te = last_activity.get("aerobicTrainingEffect")
    anaerobic_te = last_activity.get("anaerobicTrainingEffect")
    effect_label = str(last_activity.get("trainingEffectLabel", "N/A")).replace("_", " ").title()
    if effect_label.lower() == "unknown":
        effect_label = str(last_activity.get("aerobicTrainingEffectMessage", "No Aerobic Benefit")).replace("_", " ").title()

    metrics["average_hr"] = int(average_hr) if isinstance(average_hr, (int, float)) else "N/A"
    metrics["running_cadence"] = int(running_cadence) if isinstance(running_cadence, (int, float)) else "N/A"
    metrics["aerobic_training_effect"] = round(float(aerobic_te), 1) if isinstance(aerobic_te, (int, float)) else "N/A"
    metrics["anaerobic_training_effect"] = round(float(anaerobic_te), 1) if isinstance(anaerobic_te, (int, float)) else "N/A"
    metrics["training_effect_label"] = effect_label
    metrics["avg_grade_adjusted_speed"] = (
        float(last_activity.get("avgGradeAdjustedSpeed"))
        if isinstance(last_activity.get("avgGradeAdjustedSpeed"), (int, float))
        else "N/A"
    )
    metrics["garmin_last_activity"] = _build_garmin_last_activity_context(last_activity)
    metrics["garmin_segment_notables"] = _normalize_garmin_segment_notables(last_activity)

    try:
        resting_hr_data = client.get_rhr_day(start_date)
        metrics["resting_hr"] = safe_get(
            resting_hr_data, ["allMetrics", "metricsMap", "WELLNESS_RESTING_HEART_RATE", 0, "value"]
        )
    except Exception as exc:
        logger.debug("Garmin resting HR unavailable: %s", exc)

    try:
        readiness = client.get_training_readiness(start_date)
        readiness_entry = readiness[0] if isinstance(readiness, list) and readiness else {}
        readiness_level = safe_get(readiness_entry, ["level"], default="N/A")
        metrics["training_readiness_score"] = safe_get(readiness_entry, ["score"], default="N/A")
        metrics["sleep_score"] = safe_get(readiness_entry, ["sleepScore"], default="N/A")
        metrics["readiness_level"] = readiness_level
        readiness_feedback = readiness_entry.get("feedbackShort") or readiness_entry.get("feedbackLong")
        metrics["readiness_feedback"] = (
            str(readiness_feedback)
            if isinstance(readiness_feedback, str) and readiness_feedback.strip()
            else "N/A"
        )
        recovery_seconds = readiness_entry.get("recoveryTime")
        recovery_float = _as_float(recovery_seconds)
        metrics["recovery_time_hours"] = (
            round(recovery_float / 3600.0, 1)
            if recovery_float is not None and recovery_float >= 0
            else "N/A"
        )
        readiness_factors = {
            "sleep_score_factor_pct": readiness_entry.get("sleepScoreFactorPercent", "N/A"),
            "sleep_history_factor_pct": readiness_entry.get("sleepHistoryFactorPercent", "N/A"),
            "hrv_factor_pct": readiness_entry.get("hrvFactorPercent", "N/A"),
            "stress_history_factor_pct": readiness_entry.get("stressHistoryFactorPercent", "N/A"),
            "acwr_factor_pct": readiness_entry.get("acwrFactorPercent", "N/A"),
            "recovery_time_factor_pct": readiness_entry.get("recoveryTimeFactorPercent", "N/A"),
        }
        metrics["readiness_factors"] = readiness_factors
        metrics["training_readiness_emoji"] = {
            "POOR": "💀",
            "LOW": "😵‍💫",
            "MODERATE": "😒",
            "HIGH": "😄",
            "PRIME": "🤩",
        }.get(str(readiness_level).upper(), "⚪")
    except Exception as exc:
        logger.debug("Garmin training readiness unavailable: %s", exc)

    try:
        endurance_score = client.get_endurance_score(end_date)
        metrics["endurance_overall_score"] = (
            endurance_score.get("overallScore", "N/A") if isinstance(endurance_score, dict) else "N/A"
        )
    except Exception as exc:
        logger.debug("Garmin endurance score unavailable: %s", exc)

    try:
        hill_score = client.get_hill_score(end_date)
        metrics["hill_overall_score"] = (
            hill_score.get("overallScore", "N/A") if isinstance(hill_score, dict) else "N/A"
        )
    except Exception as exc:
        logger.debug("Garmin hill score unavailable: %s", exc)

    try:
        fitness_age_data = client.get_fitnessage_data(date.today().isoformat())
        age_value = fitness_age_data.get("fitnessAge") if isinstance(fitness_age_data, dict) else None
        metrics["fitness_age"] = f"{age_value} yr" if age_value is not None else "N/A"
        if isinstance(fitness_age_data, dict):
            components = fitness_age_data.get("components")
            if not isinstance(components, dict):
                components = {}
            metrics["fitness_age_details"] = {
                "fitness_age": age_value if age_value is not None else "N/A",
                "chronological_age": fitness_age_data.get("chronologicalAge", "N/A"),
                "achievable_fitness_age": fitness_age_data.get("achievableFitnessAge", "N/A"),
                "previous_fitness_age": fitness_age_data.get("previousFitnessAge", "N/A"),
                "body_fat_pct": safe_get(components, ["bodyFat", "value"], default="N/A"),
                "rhr": safe_get(components, ["rhr", "value"], default="N/A"),
                "vigorous_days_avg": safe_get(components, ["vigorousDaysAvg", "value"], default="N/A"),
                "vigorous_minutes_avg": safe_get(components, ["vigorousMinutesAvg", "value"], default="N/A"),
            }
    except Exception as exc:
        logger.debug("Garmin fitness age unavailable: %s", exc)

    try:
        get_earned_badges = getattr(client, "get_earned_badges", None)
        if callable(get_earned_badges):
            metrics["garmin_badges"] = _normalize_garmin_badges(get_earned_badges())
    except Exception as exc:
        logger.debug("Garmin badges unavailable: %s", exc)

    return metrics
