from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import Settings
from .dashboard_data import get_dashboard_payload
from .storage import list_plan_days, list_plan_sessions


METERS_PER_MILE = 1609.34
DEFAULT_WINDOW_DAYS = 14
MIN_WINDOW_DAYS = 7
MAX_WINDOW_DAYS = 56

RUN_LIKE_TYPES = {"run", "trailrun", "virtualrun", "walk"}
LONG_RUN_TYPES = {"longroad", "longmoderate", "longtrail", "race"}
RUN_TYPE_OPTIONS = [
    "",
    "Easy",
    "Recovery",
    "SOS",
    "Long Road",
    "Long Moderate",
    "Long Trail",
    "Race",
    "LT1",
    "LT2",
    "HIIT",
]


def _normalize_key(value: Any) -> str:
    return "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum())


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _coerce_window_days(value: Any) -> int:
    parsed = DEFAULT_WINDOW_DAYS
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = int(value.strip())
        except ValueError:
            parsed = DEFAULT_WINDOW_DAYS
    return max(MIN_WINDOW_DAYS, min(parsed, MAX_WINDOW_DAYS))


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _resolve_center_date(center_date: Any, *, default_date: date) -> date:
    if center_date is None or (isinstance(center_date, str) and not center_date.strip()):
        return default_date
    parsed = _parse_date(center_date)
    if parsed is None:
        raise ValueError("center_date must be YYYY-MM-DD.")
    return parsed


def _date_range(start_date: date, end_date: date) -> list[date]:
    if end_date < start_date:
        return []
    total_days = (end_date - start_date).days
    return [start_date + timedelta(days=offset) for offset in range(total_days + 1)]


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _month_end(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1) - timedelta(days=1)
    return date(value.year, value.month + 1, 1) - timedelta(days=1)


def _prev_month_key(value: date) -> str:
    prev_month_end = _month_start(value) - timedelta(days=1)
    return f"{prev_month_end.year:04d}-{prev_month_end.month:02d}"


def _week_start(value: date) -> date:
    return value - timedelta(days=value.weekday())


def _sum_days(day_values: dict[str, float], ending_date: date, days: int) -> float:
    total = 0.0
    for offset in range(days):
        day_key = (ending_date - timedelta(days=offset)).isoformat()
        total += float(day_values.get(day_key, 0.0))
    return total


def _ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def _max_days(day_values: dict[str, float], ending_date: date, days: int) -> float:
    values: list[float] = []
    for offset in range(days):
        day_key = (ending_date - timedelta(days=offset)).isoformat()
        values.append(float(day_values.get(day_key, 0.0)))
    return max(values) if values else 0.0


def _band_wow(change: float | None) -> str:
    if change is None:
        return "neutral"
    if change < 0.0:
        return "easy"
    if change <= 0.08:
        return "good"
    if change <= 0.12:
        return "caution"
    return "hard"


def _band_long_pct(value: float | None) -> str:
    if value is None:
        return "neutral"
    if value < 0.20:
        return "easy"
    if value <= 0.30:
        return "good"
    if value <= 0.35:
        return "caution"
    return "hard"


def _band_mi_t30_ratio(value: float | None) -> str:
    if value is None:
        return "neutral"
    if value < 0.75:
        return "easy"
    if value <= 1.40:
        return "good"
    if value <= 1.80:
        return "caution"
    return "hard"


def _band_t7_ratio(value: float | None) -> str:
    if value is None:
        return "neutral"
    if value < 0.90:
        return "easy"
    if value <= 1.20:
        return "good"
    if value <= 1.35:
        return "caution"
    return "hard"


def _band_session_spike(value: float | None) -> str:
    if value is None:
        return "neutral"
    if value <= 1.10:
        return "good"
    if value <= 1.30:
        return "caution"
    return "hard"


def _activity_date_key(activity: dict[str, Any]) -> str:
    date_value = _parse_date(activity.get("date"))
    if date_value is not None:
        return date_value.isoformat()
    parsed_start = _parse_date(activity.get("start_date_local"))
    if parsed_start is not None:
        return parsed_start.isoformat()
    return ""


def _actual_miles_by_date(activities: list[dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for activity in activities:
        if not isinstance(activity, dict):
            continue
        activity_type = _normalize_key(activity.get("type") or activity.get("raw_type"))
        if activity_type not in RUN_LIKE_TYPES:
            continue
        date_key = _activity_date_key(activity)
        if not date_key:
            continue
        distance_m = _as_float(activity.get("distance"))
        if distance_m is None or distance_m <= 0:
            continue
        totals[date_key] = float(totals.get(date_key, 0.0)) + (distance_m / METERS_PER_MILE)
    return totals


def _plan_day_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        day = _parse_date(row.get("date_local"))
        if day is None:
            continue
        mapped[day.isoformat()] = row
    return mapped


def _format_session_piece(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text


def _planned_input_for_day(*, planned_total: float, sessions: list[dict[str, Any]]) -> str:
    pieces: list[str] = []
    for session in sessions:
        if not isinstance(session, dict):
            continue
        planned = _as_float(session.get("planned_miles"))
        if planned is None or planned <= 0:
            continue
        pieces.append(_format_session_piece(planned))
    if pieces:
        return "+".join(pieces)
    if planned_total <= 0:
        return ""
    return _format_session_piece(planned_total)


def get_plan_payload(
    settings: Settings,
    *,
    center_date: str | None = None,
    window_days: int | str = DEFAULT_WINDOW_DAYS,
    today_local: date | None = None,
    dashboard_payload: dict[str, Any] | None = None,
    plan_day_rows: list[dict[str, Any]] | None = None,
    plan_sessions_by_day: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    try:
        local_tz = ZoneInfo(settings.timezone)
    except ZoneInfoNotFoundError:
        local_tz = timezone.utc

    today = today_local or datetime.now(local_tz).date()
    window = _coerce_window_days(window_days)
    center = _resolve_center_date(center_date, default_date=today)
    display_start = center - timedelta(days=window)
    display_end = center + timedelta(days=window)

    first_month_start = _month_start(display_start)
    calc_start = min(display_start - timedelta(days=90), first_month_start - timedelta(days=35))
    calc_end = max(display_end, _month_end(display_end))

    if dashboard_payload is None:
        try:
            dashboard_payload = get_dashboard_payload(
                settings,
                force_refresh=False,
                response_mode="full",
            )
        except Exception:
            dashboard_payload = {}

    activities_raw = dashboard_payload.get("activities") if isinstance(dashboard_payload, dict) else []
    activities = activities_raw if isinstance(activities_raw, list) else []
    actual_miles = _actual_miles_by_date(activities)

    if plan_day_rows is None:
        plan_day_rows = list_plan_days(
            settings.processed_log_file,
            start_date=calc_start.isoformat(),
            end_date=calc_end.isoformat(),
        )
    plan_days = _plan_day_map(plan_day_rows if isinstance(plan_day_rows, list) else [])
    if plan_sessions_by_day is None:
        plan_sessions_by_day = list_plan_sessions(
            settings.processed_log_file,
            start_date=calc_start.isoformat(),
            end_date=calc_end.isoformat(),
        )

    dates_full = _date_range(calc_start, calc_end)
    planned_miles: dict[str, float] = {}
    planned_sessions_clean: dict[str, list[float]] = {}
    actual_miles_by_day: dict[str, float] = {}
    effective_miles: dict[str, float] = {}
    run_type_by_date: dict[str, str] = {}
    complete_by_date: dict[str, bool] = {}
    completion_source_by_date: dict[str, str] = {}
    notes_by_date: dict[str, str] = {}

    for day in dates_full:
        day_key = day.isoformat()
        plan_row = plan_days.get(day_key) or {}
        sessions_for_day = (
            plan_sessions_by_day.get(day_key)
            if isinstance(plan_sessions_by_day, dict)
            else []
        )
        planned_from_day = _as_float(plan_row.get("planned_total_miles")) or 0.0
        session_total = 0.0
        session_values: list[float] = []
        if isinstance(sessions_for_day, list):
            for session in sessions_for_day:
                if not isinstance(session, dict):
                    continue
                planned_piece = _as_float(session.get("planned_miles"))
                if planned_piece is None or planned_piece <= 0:
                    continue
                session_total += planned_piece
                session_values.append(planned_piece)
        planned = session_total if session_total > 0 else planned_from_day
        actual = _as_float(actual_miles.get(day_key)) or 0.0
        run_type = str(plan_row.get("run_type") or "").strip()
        notes = str(plan_row.get("notes") or "").strip()

        if day <= today:
            effective = actual if actual > 0 else planned
        else:
            effective = planned

        explicit_complete = plan_row.get("is_complete")
        if isinstance(explicit_complete, bool):
            complete = explicit_complete
            completion_source = "manual"
        else:
            complete = day <= today and actual > 0
            completion_source = "auto"

        planned_miles[day_key] = planned
        planned_sessions_clean[day_key] = session_values
        actual_miles_by_day[day_key] = actual
        effective_miles[day_key] = effective
        run_type_by_date[day_key] = run_type
        complete_by_date[day_key] = complete
        completion_source_by_date[day_key] = completion_source
        notes_by_date[day_key] = notes

    week_totals: dict[str, float] = {}
    week_planned_totals: dict[str, float] = {}
    week_actual_totals: dict[str, float] = {}
    week_long_miles: dict[str, float] = {}
    for day in dates_full:
        week_key = _week_start(day).isoformat()
        if week_key in week_totals:
            continue
        week_start = _week_start(day)
        week_days = [week_start + timedelta(days=idx) for idx in range(7)]
        miles_values = [float(effective_miles.get(item.isoformat(), 0.0)) for item in week_days]
        planned_values = [float(planned_miles.get(item.isoformat(), 0.0)) for item in week_days]
        actual_values = [float(actual_miles_by_day.get(item.isoformat(), 0.0)) for item in week_days]
        week_totals[week_key] = sum(miles_values)
        week_planned_totals[week_key] = sum(planned_values)
        week_actual_totals[week_key] = sum(actual_values)
        long_values = [
            miles_values[idx]
            for idx, week_day in enumerate(week_days)
            if _normalize_key(run_type_by_date.get(week_day.isoformat())) in LONG_RUN_TYPES
        ]
        week_long_miles[week_key] = max(long_values) if long_values else (max(miles_values) if miles_values else 0.0)

    month_totals: dict[str, float] = {}
    month_planned_totals: dict[str, float] = {}
    month_actual_totals: dict[str, float] = {}
    month_cursor = _month_start(calc_start)
    month_limit = _month_end(calc_end)
    while month_cursor <= month_limit:
        month_key = f"{month_cursor.year:04d}-{month_cursor.month:02d}"
        month_last_day = _month_end(month_cursor)
        month_days = _date_range(month_cursor, month_last_day)
        month_totals[month_key] = sum(float(effective_miles.get(item.isoformat(), 0.0)) for item in month_days)
        month_planned_totals[month_key] = sum(float(planned_miles.get(item.isoformat(), 0.0)) for item in month_days)
        month_actual_totals[month_key] = sum(float(actual_miles_by_day.get(item.isoformat(), 0.0)) for item in month_days)
        month_cursor = month_last_day + timedelta(days=1)

    rows: list[dict[str, Any]] = []
    for day in _date_range(display_start, display_end):
        day_key = day.isoformat()
        week_start = _week_start(day)
        week_key = week_start.isoformat()
        prev_week_key = (week_start - timedelta(days=7)).isoformat()
        week_total = float(week_totals.get(week_key, 0.0))
        week_planned_total = float(week_planned_totals.get(week_key, 0.0))
        week_actual_total = float(week_actual_totals.get(week_key, 0.0))
        prev_week_total = float(week_totals.get(prev_week_key, 0.0))
        wow_change = ((week_total - prev_week_total) / prev_week_total) if prev_week_total > 0 else None
        long_pct = (float(week_long_miles.get(week_key, 0.0)) / week_total) if week_total > 0 else None

        month_key = f"{day.year:04d}-{day.month:02d}"
        prev_month_key = _prev_month_key(day)
        month_total = float(month_totals.get(month_key, 0.0))
        month_planned_total = float(month_planned_totals.get(month_key, 0.0))
        month_actual_total = float(month_actual_totals.get(month_key, 0.0))
        prev_month_total = float(month_totals.get(prev_month_key, 0.0))
        mom_change = ((month_total - prev_month_total) / prev_month_total) if prev_month_total > 0 else None

        planned_value = float(planned_miles.get(day_key, 0.0))
        actual_value = float(actual_miles_by_day.get(day_key, 0.0))
        effective = float(effective_miles.get(day_key, 0.0))
        day_delta = actual_value - planned_value
        t7 = _sum_days(effective_miles, day, 7)
        t7_planned = _sum_days(planned_miles, day, 7)
        t7_actual = _sum_days(actual_miles_by_day, day, 7)
        t30 = _sum_days(effective_miles, day, 30)
        t30_planned = _sum_days(planned_miles, day, 30)
        t30_actual = _sum_days(actual_miles_by_day, day, 30)
        avg30 = t30 / 30.0
        mi_t30_ratio = (effective / avg30) if avg30 > 0 else None
        prev_t7 = _sum_days(effective_miles, day - timedelta(days=7), 7)
        prev_t30 = _sum_days(effective_miles, day - timedelta(days=30), 30)
        t7_p7_ratio = (t7 / prev_t7) if prev_t7 > 0 else None
        t30_p30_ratio = (t30 / prev_t30) if prev_t30 > 0 else None

        longest_30d_before = _max_days(effective_miles, day - timedelta(days=1), 30)
        session_spike_ratio = (effective / longest_30d_before) if longest_30d_before > 0 else None

        prev_display_day = day - timedelta(days=1)
        show_week_metrics = prev_display_day < display_start or _week_start(prev_display_day) != week_start
        show_month_metrics = prev_display_day < display_start or prev_display_day.month != day.month or prev_display_day.year != day.year
        week_row_span = 0
        month_row_span = 0
        if show_week_metrics:
            week_row_span = int((min(display_end, week_start + timedelta(days=6)) - day).days + 1)
        if show_month_metrics:
            month_row_span = int((min(display_end, _month_end(day)) - day).days + 1)

        rows.append(
            {
                "date": day_key,
                "is_today": day == today,
                "is_past_or_today": day <= today,
                "is_complete": bool(complete_by_date.get(day_key, False)),
                "completion_source": completion_source_by_date.get(day_key, "auto"),
                "run_type": run_type_by_date.get(day_key, ""),
                "notes": notes_by_date.get(day_key, ""),
                "planned_miles": planned_value,
                "planned_sessions": list(planned_sessions_clean.get(day_key, [])),
                "planned_input": _planned_input_for_day(
                    planned_total=float(planned_miles.get(day_key, 0.0)),
                    sessions=(
                        plan_sessions_by_day.get(day_key)
                        if isinstance(plan_sessions_by_day, dict)
                        and isinstance(plan_sessions_by_day.get(day_key), list)
                        else []
                    ),
                ),
                "actual_miles": actual_value,
                "day_delta": day_delta,
                "effective_miles": effective,
                "weekly_total": week_total,
                "weekly_planned_total": week_planned_total,
                "weekly_actual_total": week_actual_total,
                "weekly_adherence_ratio": _ratio(week_actual_total, week_planned_total),
                "wow_change": wow_change,
                "long_pct": long_pct,
                "monthly_total": month_total,
                "monthly_planned_total": month_planned_total,
                "monthly_actual_total": month_actual_total,
                "monthly_adherence_ratio": _ratio(month_actual_total, month_planned_total),
                "mom_change": mom_change,
                "mi_t30_ratio": mi_t30_ratio,
                "t7_miles": t7,
                "t7_planned_miles": t7_planned,
                "t7_actual_miles": t7_actual,
                "t7_adherence_ratio": _ratio(t7_actual, t7_planned),
                "t7_p7_ratio": t7_p7_ratio,
                "t30_miles": t30,
                "t30_planned_miles": t30_planned,
                "t30_actual_miles": t30_actual,
                "t30_adherence_ratio": _ratio(t30_actual, t30_planned),
                "t30_p30_ratio": t30_p30_ratio,
                "avg30_miles_per_day": avg30,
                "session_spike_ratio": session_spike_ratio,
                "show_week_metrics": show_week_metrics,
                "week_row_span": week_row_span,
                "show_month_metrics": show_month_metrics,
                "month_row_span": month_row_span,
                "bands": {
                    "wow_change": _band_wow(wow_change),
                    "long_pct": _band_long_pct(long_pct),
                    "mi_t30_ratio": _band_mi_t30_ratio(mi_t30_ratio),
                    "t7_p7_ratio": _band_t7_ratio(t7_p7_ratio),
                    "t30_p30_ratio": _band_t7_ratio(t30_p30_ratio),
                    "session_spike_ratio": _band_session_spike(session_spike_ratio),
                },
            }
        )

    summary_anchor = center.isoformat()
    anchor_row = next((row for row in rows if str(row.get("date")) == summary_anchor), None)
    if anchor_row is None:
        anchor_row = rows[0] if rows else {}

    summary = {
        "anchor_date": summary_anchor,
        "day_planned": float(anchor_row.get("planned_miles") or 0.0),
        "day_actual": float(anchor_row.get("actual_miles") or 0.0),
        "day_delta": float(anchor_row.get("day_delta") or 0.0),
        "t7_planned": float(anchor_row.get("t7_planned_miles") or 0.0),
        "t7_actual": float(anchor_row.get("t7_actual_miles") or 0.0),
        "t7_delta": float(anchor_row.get("t7_actual_miles") or 0.0) - float(anchor_row.get("t7_planned_miles") or 0.0),
        "t7_adherence_ratio": anchor_row.get("t7_adherence_ratio"),
        "t30_planned": float(anchor_row.get("t30_planned_miles") or 0.0),
        "t30_actual": float(anchor_row.get("t30_actual_miles") or 0.0),
        "t30_delta": float(anchor_row.get("t30_actual_miles") or 0.0) - float(anchor_row.get("t30_planned_miles") or 0.0),
        "t30_adherence_ratio": anchor_row.get("t30_adherence_ratio"),
        "week_planned": float(anchor_row.get("weekly_planned_total") or 0.0),
        "week_actual": float(anchor_row.get("weekly_actual_total") or 0.0),
        "week_delta": float(anchor_row.get("weekly_actual_total") or 0.0) - float(anchor_row.get("weekly_planned_total") or 0.0),
        "week_adherence_ratio": anchor_row.get("weekly_adherence_ratio"),
        "month_planned": float(anchor_row.get("monthly_planned_total") or 0.0),
        "month_actual": float(anchor_row.get("monthly_actual_total") or 0.0),
        "month_delta": float(anchor_row.get("monthly_actual_total") or 0.0) - float(anchor_row.get("monthly_planned_total") or 0.0),
        "month_adherence_ratio": anchor_row.get("monthly_adherence_ratio"),
    }

    return {
        "status": "ok",
        "timezone": settings.timezone,
        "today": today.isoformat(),
        "center_date": center.isoformat(),
        "window_days": window,
        "start_date": display_start.isoformat(),
        "end_date": display_end.isoformat(),
        "run_type_options": list(RUN_TYPE_OPTIONS),
        "summary": summary,
        "rows": rows,
    }
