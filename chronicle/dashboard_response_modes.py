from __future__ import annotations

from typing import Any


def normalize_dashboard_response_mode(value: object) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized or normalized == "full":
        return "full"
    if normalized in {"summary", "slim"}:
        return "summary"
    if normalized == "year":
        return "year"
    raise ValueError(f"Invalid dashboard mode '{value}'. Expected one of: full, summary, year.")


def parse_dashboard_response_year(value: object) -> int:
    text = str(value or "").strip()
    if not text:
        raise ValueError("Dashboard year mode requires query parameter 'year'.")
    try:
        year = int(text)
    except ValueError as exc:
        raise ValueError("Dashboard year must be a valid integer.") from exc
    if year < 1970 or year > 9999:
        raise ValueError("Dashboard year must be between 1970 and 9999.")
    return year


def project_dashboard_payload_summary(payload: dict[str, Any]) -> dict[str, Any]:
    projected = dict(payload)
    activities_raw = payload.get("activities")
    activity_count = len(activities_raw) if isinstance(activities_raw, list) else 0
    projected["activities"] = []
    projected["activity_count"] = activity_count
    projected["response_mode"] = "summary"
    return projected


def project_dashboard_payload_year(payload: dict[str, Any], *, response_year: int) -> dict[str, Any]:
    year_key = str(response_year)
    projected = dict(payload)

    aggregates_raw = payload.get("aggregates")
    aggregate_year = (
        aggregates_raw.get(year_key)
        if isinstance(aggregates_raw, dict) and isinstance(aggregates_raw.get(year_key), dict)
        else {}
    )
    projected["aggregates"] = {year_key: aggregate_year} if aggregate_year else {}

    intervals_year_type_raw = payload.get("intervals_year_type_metrics")
    intervals_year_type = (
        intervals_year_type_raw.get(year_key)
        if isinstance(intervals_year_type_raw, dict) and isinstance(intervals_year_type_raw.get(year_key), dict)
        else {}
    )
    projected["intervals_year_type_metrics"] = {year_key: intervals_year_type} if intervals_year_type else {}

    activities: list[dict[str, Any]] = []
    activities_raw = payload.get("activities")
    if isinstance(activities_raw, list):
        for item in activities_raw:
            if not isinstance(item, dict):
                continue
            try:
                item_year = int(item.get("year"))
            except (TypeError, ValueError):
                continue
            if item_year == response_year:
                activities.append(dict(item))
    projected["activities"] = activities
    projected["activity_count"] = len(activities)
    projected["years"] = [response_year]

    types_raw = payload.get("types")
    type_order = [item for item in types_raw if isinstance(item, str)] if isinstance(types_raw, list) else []
    scoped_types = list(aggregate_year.keys())
    ordered_types = [item for item in type_order if item in scoped_types]
    for item in scoped_types:
        if item not in ordered_types:
            ordered_types.append(item)
    projected["types"] = ordered_types

    type_meta_raw = payload.get("type_meta")
    type_meta = type_meta_raw if isinstance(type_meta_raw, dict) else {}
    projected["type_meta"] = {item: type_meta[item] for item in ordered_types if item in type_meta}

    projected["response_mode"] = "year"
    projected["response_year"] = response_year
    return projected


def apply_dashboard_response_mode(
    payload: dict[str, Any],
    *,
    response_mode: str,
    response_year: int | str | None,
) -> dict[str, Any]:
    mode = normalize_dashboard_response_mode(response_mode)
    if mode == "full":
        return dict(payload)
    if mode == "summary":
        return project_dashboard_payload_summary(payload)
    year = parse_dashboard_response_year(response_year)
    return project_dashboard_payload_year(payload, response_year=year)
