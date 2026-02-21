from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from ..numeric_utils import (
    as_float as _shared_as_float,
    as_int as _shared_as_int,
    meters_to_feet_int as _shared_meters_to_feet_int,
    meters_to_miles as _shared_meters_to_miles,
    mps_to_mph as _shared_mps_to_mph,
    mps_to_pace as _shared_mps_to_pace,
    seconds_to_hms as _shared_seconds_to_hms,
)


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


def default_metrics() -> dict[str, Any]:
    return _default_metrics()


def _as_float(value: Any) -> float | None:
    return _shared_as_float(value)


def _as_int(value: Any) -> int | None:
    return _shared_as_int(value)


def _seconds_to_hms(value: Any) -> str:
    return _shared_seconds_to_hms(value)


def _meters_to_miles(value: Any) -> str:
    return _shared_meters_to_miles(value, include_unit=True)


def _meters_to_feet(value: Any) -> int | str:
    return _shared_meters_to_feet_int(value)


def _mps_to_mph(value: Any) -> str:
    return _shared_mps_to_mph(value, include_unit=True)


def _mps_to_pace(value: Any) -> str:
    return _shared_mps_to_pace(value, include_unit=True)


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


def _normalize_strength_summary_sets(payload: Any) -> list[dict[str, Any]]:
    def _clean_label(value: Any) -> str | None:
        text = str(value or "").strip()
        if not text:
            return None
        if text.lower() in {"n/a", "na", "none", "null", "unknown"}:
            return None
        return text

    if not isinstance(payload, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        sets = _as_int(item.get("sets"))
        reps = _as_int(item.get("reps"))
        max_weight = _as_float(item.get("maxWeight"))
        duration_ms = _as_float(item.get("duration"))
        category = _clean_label(item.get("category"))
        sub_category = _clean_label(item.get("subCategory"))
        if sub_category is None and category is not None:
            sub_category = category
        if category is None and sub_category is not None:
            category = sub_category
        rows.append(
            {
                "category": category or "N/A",
                "sub_category": sub_category or "N/A",
                "sets": sets if sets is not None else "N/A",
                "reps": reps if reps is not None else "N/A",
                "max_weight": round(max_weight, 2) if max_weight is not None else "N/A",
                "duration_seconds": int(round(duration_ms / 1000.0))
                if duration_ms is not None and duration_ms >= 0
                else "N/A",
            }
        )
    return rows


def _normalize_exercise_sets(payload: Any) -> list[dict[str, Any]]:
    def _clean_label(value: Any) -> str | None:
        text = str(value or "").strip()
        if not text:
            return None
        if text.lower() in {"n/a", "na", "none", "null", "unknown"}:
            return None
        return text

    def _weight_display(weight_value: float | None, set_type: str) -> str:
        if weight_value is None:
            return "N/A"
        if set_type == "ACTIVE" and abs(weight_value) < 1e-9:
            return "Bodyweight"
        if float(weight_value).is_integer():
            return str(int(round(weight_value)))
        return f"{weight_value:.2f}".rstrip("0").rstrip(".")

    if not isinstance(payload, dict):
        return []
    rows = payload.get("exerciseSets")
    if not isinstance(rows, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        set_type = str(item.get("setType") or "UNKNOWN").strip().upper()
        repetition_count = _as_int(item.get("repetitionCount"))
        raw_weight = _as_float(item.get("weight"))
        weight: float | None
        if raw_weight is None or raw_weight < 0:
            weight = None
        else:
            weight = round(raw_weight, 2)
        duration_seconds = _as_float(item.get("duration"))
        exercise_names: list[str] = []
        exercises = item.get("exercises")
        if isinstance(exercises, list):
            for exercise in exercises:
                if not isinstance(exercise, dict):
                    continue
                name = _clean_label(exercise.get("name")) or _clean_label(exercise.get("category"))
                if not name or name in exercise_names:
                    continue
                exercise_names.append(name)

        normalized.append(
            {
                "set_type": set_type,
                "reps": repetition_count if repetition_count is not None else "N/A",
                "weight": _weight_display(weight, set_type)
                if (weight is None or (set_type == "ACTIVE" and abs(weight) < 1e-9))
                else weight,
                "weight_value": weight if weight is not None else "N/A",
                "weight_display": _weight_display(weight, set_type),
                "duration_seconds": int(round(duration_seconds))
                if duration_seconds is not None and duration_seconds >= 0
                else "N/A",
                "exercise_names": exercise_names,
            }
        )

    return normalized


def _parse_garmin_start_utc(activity: dict[str, Any]) -> datetime | None:
    raw_gmt = activity.get("startTimeGMT")
    if isinstance(raw_gmt, str) and raw_gmt.strip():
        try:
            return datetime.strptime(raw_gmt.strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    raw_local = activity.get("startTimeLocal")
    if isinstance(raw_local, str) and raw_local.strip():
        candidate = raw_local.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _parse_strava_start_utc(activity: dict[str, Any]) -> datetime | None:
    for key in ("start_date", "start_date_local"):
        raw_value = activity.get(key)
        if not isinstance(raw_value, str) or not raw_value.strip():
            continue
        candidate = raw_value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _fetch_activity_exercise_sets(client: Any | None, activity_id: int | None) -> Any | None:
    if client is None or activity_id is None:
        return None
    get_exercise_sets = getattr(client, "get_activity_exercise_sets", None)
    if not callable(get_exercise_sets):
        return None
    try:
        return get_exercise_sets(activity_id)
    except Exception as exc:
        logger.debug("Garmin activity exercise sets unavailable for %s: %s", activity_id, exc)
        return None


def build_garmin_activity_context(client: Any | None, activity_payload: dict[str, Any]) -> dict[str, Any]:
    activity_id = _as_int(activity_payload.get("activityId"))
    exercise_sets_payload = _fetch_activity_exercise_sets(client, activity_id)
    return _build_garmin_last_activity_context(
        activity_payload,
        exercise_sets_payload=exercise_sets_payload,
    )


def get_activity_context_for_strava_activity(
    client: Any | None,
    strava_activity: dict[str, Any],
    *,
    max_start_diff_seconds: int = 6 * 60 * 60,
) -> dict[str, Any] | None:
    if client is None or not isinstance(strava_activity, dict):
        return None

    strava_start_utc = _parse_strava_start_utc(strava_activity)
    if strava_start_utc is None:
        return None

    get_activities_by_date = getattr(client, "get_activities_by_date", None)
    if not callable(get_activities_by_date):
        return None

    window_start = (strava_start_utc - timedelta(days=1)).date().isoformat()
    window_end = (strava_start_utc + timedelta(days=1)).date().isoformat()
    try:
        garmin_activities = get_activities_by_date(window_start, window_end)
    except Exception as exc:
        logger.debug("Garmin activity matching lookup failed: %s", exc)
        return None
    if not isinstance(garmin_activities, list):
        return None

    strava_distance = _as_float(strava_activity.get("distance"))
    strava_duration = _as_float(strava_activity.get("moving_time")) or _as_float(strava_activity.get("elapsed_time"))
    ranked: list[tuple[float, dict[str, Any]]] = []

    for candidate in garmin_activities:
        if not isinstance(candidate, dict):
            continue
        candidate_start = _parse_garmin_start_utc(candidate)
        if candidate_start is None:
            continue
        start_diff = abs((candidate_start - strava_start_utc).total_seconds())
        if start_diff > float(max_start_diff_seconds):
            continue

        score = float(start_diff)
        candidate_distance = _as_float(candidate.get("distance"))
        if (
            candidate_distance is not None
            and strava_distance is not None
            and candidate_distance > 0
            and strava_distance > 0
        ):
            distance_ratio = abs(candidate_distance - strava_distance) / max(candidate_distance, strava_distance)
            score += distance_ratio * 1800.0

        candidate_duration = _as_float(candidate.get("movingDuration")) or _as_float(candidate.get("duration"))
        if (
            candidate_duration is not None
            and strava_duration is not None
            and candidate_duration > 0
            and strava_duration > 0
        ):
            duration_ratio = abs(candidate_duration - strava_duration) / max(candidate_duration, strava_duration)
            score += duration_ratio * 1200.0

        ranked.append((score, candidate))

    if not ranked:
        return None

    ranked.sort(key=lambda item: item[0])
    best_candidate = dict(ranked[0][1])
    activity_id = _as_int(best_candidate.get("activityId"))

    get_activity_details = getattr(client, "get_activity_details", None)
    if activity_id is not None and callable(get_activity_details):
        try:
            details = get_activity_details(activity_id)
            if isinstance(details, dict):
                best_candidate.update(details)
        except Exception as exc:
            logger.debug("Garmin activity detail lookup unavailable for %s: %s", activity_id, exc)

    return build_garmin_activity_context(client, best_candidate)


def _build_garmin_last_activity_context(
    last_activity: dict[str, Any],
    *,
    exercise_sets_payload: Any | None = None,
) -> dict[str, Any]:
    avg_power = _as_float(last_activity.get("avgPower"))
    norm_power = _as_float(last_activity.get("normPower"))
    max_power = _as_float(last_activity.get("maxPower"))
    strength_summary_sets = _normalize_strength_summary_sets(last_activity.get("summarizedExerciseSets"))
    exercise_sets = _normalize_exercise_sets(exercise_sets_payload)

    active_sets_from_payload = [row for row in exercise_sets if str(row.get("set_type")) == "ACTIVE"]
    total_sets = _as_int(last_activity.get("totalSets"))
    active_sets = _as_int(last_activity.get("activeSets"))
    total_reps = _as_int(last_activity.get("totalReps"))
    max_weight = None

    if total_sets is None:
        if active_sets_from_payload:
            total_sets = len(active_sets_from_payload)
        else:
            total_sets = 0
            for row in strength_summary_sets:
                row_sets = _as_int(row.get("sets"))
                if row_sets is not None and row_sets > 0:
                    total_sets += row_sets
            if total_sets <= 0:
                total_sets = None

    if active_sets is None:
        active_sets = len(active_sets_from_payload) if active_sets_from_payload else total_sets

    if total_reps is None:
        total_reps = 0
        for row in active_sets_from_payload:
            reps = _as_int(row.get("reps"))
            if reps is not None and reps > 0:
                total_reps += reps
        if total_reps <= 0:
            total_reps = 0
            for row in strength_summary_sets:
                reps = _as_int(row.get("reps"))
                if reps is not None and reps > 0:
                    total_reps += reps
            if total_reps <= 0:
                total_reps = None

    for row in active_sets_from_payload:
        weight = _as_float(row.get("weight"))
        if weight is None:
            continue
        if max_weight is None or weight > max_weight:
            max_weight = weight
    if max_weight is None:
        for row in strength_summary_sets:
            weight = _as_float(row.get("max_weight"))
            if weight is None:
                continue
            if max_weight is None or weight > max_weight:
                max_weight = weight

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
        "total_sets": total_sets if total_sets is not None else "N/A",
        "active_sets": active_sets if active_sets is not None else "N/A",
        "total_reps": total_reps if total_reps is not None else "N/A",
        "max_weight": round(max_weight, 2) if max_weight is not None else "N/A",
        "strength_summary_sets": strength_summary_sets,
        "exercise_sets": exercise_sets,
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
    metrics["garmin_last_activity"] = build_garmin_activity_context(client, last_activity)
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
