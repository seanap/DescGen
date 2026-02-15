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
    except Exception as exc:
        logger.debug("Garmin fitness age unavailable: %s", exc)

    return metrics
