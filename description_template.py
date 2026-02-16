from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from jinja2 import StrictUndefined, TemplateError, meta
from jinja2.sandbox import SandboxedEnvironment

from config import Settings


DEFAULT_DESCRIPTION_TEMPLATE = """🏆 {{ streak_days }} days in a row
{% for notable in notables %}🏅 {{ notable }}
{% endfor %}{% for achievement in achievements %}🏅 {{ achievement }}
{% endfor %}🌤️🌡️ Misery Index: {{ weather.misery_index }} {{ weather.misery_description }} | 🏭 AQI: {{ weather.aqi }}{{ weather.aqi_description }}
{% if crono.average_net_kcal_per_day is defined and crono.average_net_kcal_per_day is not none %}🔥 7d avg daily Energy Balance:{{ "%+.0f"|format(crono.average_net_kcal_per_day) }} kcal{% if crono.average_status %} ({{ crono.average_status }}){% endif %}{% if crono.protein_g and crono.protein_g > 0 %} | 🥩:{{ crono.protein_g|round|int }}g{% endif %}{% if crono.carbs_g and crono.carbs_g > 0 %} | 🍞:{{ crono.carbs_g|round|int }}g{% endif %}
{% elif crono.line %}{{ crono.line }}
{% endif %}🌤️🚦 Training Readiness: {{ training.readiness_score }} {{ training.readiness_emoji }} | 💗 {{ training.resting_hr }} | 💤 {{ training.sleep_score }}
👟🏃 {{ activity.gap_pace }} | 🗺️ {{ activity.distance_miles }} | 🏔️ {{ activity.elevation_feet }}' | 🕓 {{ activity.time }} | 🍺 {{ activity.beers }}
👟👣 {{ activity.cadence_spm }}spm | 💼 {{ activity.work }} | ⚡ {{ activity.norm_power }} | 💓 {{ activity.average_hr }} | ⚙️{{ activity.efficiency }}
🚄 {{ training.status_emoji }} {{ training.status_key }} | {{ training.aerobic_te }} : {{ training.anaerobic_te }} - {{ training.te_label }}
🚄 {{ intervals.summary }}
🚄 🏋️ {{ training.chronic_load }} | 💦 {{ training.acute_load }} | 🗿 {{ training.load_ratio }} - {{ training.acwr_status }} {{ training.acwr_status_emoji }}
❤️‍🔥 {{ training.vo2 }} | ♾ Endur: {{ training.endurance_score }} | 🗻 Hill: {{ training.hill_score }}

7️⃣ Past 7 days:
🏃 {{ periods.week.gap }} | 🗺️ {{ periods.week.distance_miles }} | 🏔️ {{ periods.week.elevation_feet }}' | 🕓 {{ periods.week.duration }} | 🍺 {{ periods.week.beers }}
📅 Past 30 days:
🏃 {{ periods.month.gap }} | 🗺️ {{ periods.month.distance_miles }} | 🏔️ {{ periods.month.elevation_feet }}' | 🕓 {{ periods.month.duration }} | 🍺 {{ periods.month.beers }}
🌍 This Year:
🏃 {{ periods.year.gap }} | 🗺️ {{ periods.year.distance_miles }} | 🏔️ {{ periods.year.elevation_feet }}' | 🕓 {{ periods.year.duration }} | 🍺 {{ periods.year.beers }}"""

MAX_TEMPLATE_CHARS = 16000
FORBIDDEN_TEMPLATE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"{%\s*(import|from|include|extends|macro|call)\b", re.IGNORECASE), "Template uses unsupported Jinja control tag."),
    (re.compile(r"\b__\w+\b"), "Template references dunder-style attributes, which are not allowed."),
]


EDITOR_SNIPPETS: list[dict[str, str]] = [
    {
        "id": "if-block",
        "category": "logic",
        "label": "If Present Block",
        "template": "{% if value %}\n{{ value }}\n{% endif %}",
        "description": "Render a line only when a value exists.",
    },
    {
        "id": "for-loop",
        "category": "logic",
        "label": "Simple For Loop",
        "template": "{% for item in items %}\n- {{ item }}\n{% endfor %}",
        "description": "Loop over a list.",
    },
    {
        "id": "default-filter",
        "category": "filters",
        "label": "Default Fallback",
        "template": "{{ value | default('N/A') }}",
        "description": "Provide a fallback when a value is missing.",
    },
    {
        "id": "round-filter",
        "category": "filters",
        "label": "Round Number",
        "template": "{{ value | round(1) }}",
        "description": "Round to one decimal place.",
    },
    {
        "id": "join-filter",
        "category": "filters",
        "label": "Join List",
        "template": "{{ items | join(', ') }}",
        "description": "Join list items into one line.",
    },
    {
        "id": "line-break",
        "category": "layout",
        "label": "Blank Line",
        "template": "\n",
        "description": "Insert an empty line.",
    },
]


SAMPLE_TEMPLATE_CONTEXT: dict[str, Any] = {
    "streak_days": 412,
    "notables": [
        "Longest run in 90 days",
        "2nd best GAP pace this month",
    ],
    "achievements": [],
    "crono": {
        "line": "🔥 7d avg daily Energy Balance:-1131 kcal (deficit) | 🥩:182g | 🍞:216g",
        "date": "2026-02-15",
        "average_net_kcal_per_day": -1131.0,
        "average_status": "deficit",
        "protein_g": 182.0,
        "carbs_g": 216.0,
    },
    "weather": {
        "misery_index": 104.3,
        "misery_description": "😀 Perfect",
        "aqi": 22,
        "aqi_description": " Good",
        "details": {
            "temperature_f": 63.0,
            "dew_point_f": 49.6,
            "humidity_percent": 61,
            "wind_mph": 11.9,
            "condition_text": "Clear",
        },
    },
    "training": {
        "readiness_score": 83,
        "readiness_emoji": "🟢",
        "resting_hr": 47,
        "sleep_score": 86,
        "status_emoji": "🟢",
        "status_key": "Productive",
        "aerobic_te": 4.1,
        "anaerobic_te": 0.1,
        "te_label": "Tempo",
        "chronic_load": 72,
        "acute_load": 78,
        "load_ratio": 1.1,
        "acwr_status": "Optimal",
        "acwr_status_emoji": "🟢",
        "vo2": 57.2,
        "endurance_score": 7312,
        "hill_score": 102,
    },
    "activity": {
        "gap_pace": "7:18/mi",
        "distance_miles": "8.02",
        "elevation_feet": 612,
        "time": "58:39",
        "beers": "5.1",
        "cadence_spm": 176,
        "work": "914 kJ",
        "norm_power": "271 W",
        "average_hr": 149,
        "efficiency": "1.03",
    },
    "intervals": {
        "summary": "CTL 72 | ATL 78 | Form -6",
    },
    "periods": {
        "week": {
            "gap": "7:44/mi",
            "distance_miles": "41.6",
            "elevation_feet": 3904,
            "duration": "5:21:08",
            "beers": "27",
        },
        "month": {
            "gap": "7:58/mi",
            "distance_miles": "156",
            "elevation_feet": 14902,
            "duration": "20:04:51",
            "beers": "101",
        },
        "year": {
            "gap": "8:05/mi",
            "distance_miles": "284",
            "elevation_feet": 24117,
            "duration": "36:40:27",
            "beers": "184",
        },
    },
    "raw": {
        "activity": {"id": 1234567890},
        "training": {},
        "intervals": {},
        "week": {},
        "month": {},
        "year": {},
        "weather": {},
    },
}


def _build_sample_fixtures() -> dict[str, dict[str, Any]]:
    default_ctx = deepcopy(SAMPLE_TEMPLATE_CONTEXT)

    winter_ctx = deepcopy(default_ctx)
    winter_ctx["weather"]["misery_index"] = 34.7
    winter_ctx["weather"]["misery_description"] = "🥶 Oppressively cold"
    winter_ctx["weather"]["aqi"] = 11
    winter_ctx["weather"]["details"] = {
        "temperature_f": 24.1,
        "dew_point_f": 5.0,
        "humidity_percent": 43,
        "wind_mph": 16.5,
        "condition_text": "Windy",
    }
    winter_ctx["activity"]["gap_pace"] = "8:42/mi"
    winter_ctx["activity"]["distance_miles"] = "6.10"
    winter_ctx["activity"]["elevation_feet"] = 441
    winter_ctx["activity"]["time"] = "53:03"
    winter_ctx["activity"]["beers"] = "3.1"
    winter_ctx["crono"]["average_net_kcal_per_day"] = -842.0
    winter_ctx["crono"]["average_status"] = "deficit"
    winter_ctx["crono"]["protein_g"] = 169.0
    winter_ctx["crono"]["carbs_g"] = 153.0

    humid_ctx = deepcopy(default_ctx)
    humid_ctx["weather"]["misery_index"] = 172.2
    humid_ctx["weather"]["misery_description"] = "😡 Miserable"
    humid_ctx["weather"]["aqi"] = 67
    humid_ctx["weather"]["details"] = {
        "temperature_f": 89.8,
        "dew_point_f": 80.2,
        "humidity_percent": 78,
        "wind_mph": 2.7,
        "condition_text": "Humid",
    }
    humid_ctx["activity"]["gap_pace"] = "8:31/mi"
    humid_ctx["activity"]["distance_miles"] = "9.28"
    humid_ctx["activity"]["elevation_feet"] = 518
    humid_ctx["activity"]["time"] = "1:19:16"
    humid_ctx["activity"]["beers"] = "6.7"
    humid_ctx["crono"]["average_net_kcal_per_day"] = 204.0
    humid_ctx["crono"]["average_status"] = "surplus"
    humid_ctx["crono"]["protein_g"] = 132.0
    humid_ctx["crono"]["carbs_g"] = 301.0

    return {
        "default": {
            "name": "default",
            "label": "Default",
            "description": "Balanced weather and training context.",
            "context": default_ctx,
        },
        "winter_grind": {
            "name": "winter_grind",
            "label": "Winter Grind",
            "description": "Cold and windy run profile for edge-case formatting.",
            "context": winter_ctx,
        },
        "humid_hammer": {
            "name": "humid_hammer",
            "label": "Humid Hammer",
            "description": "Hot + humid profile for heat-stress rendering checks.",
            "context": humid_ctx,
        },
    }


SAMPLE_TEMPLATE_FIXTURES = _build_sample_fixtures()


def _template_environment() -> SandboxedEnvironment:
    return SandboxedEnvironment(
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=False,
        undefined=StrictUndefined,
    )


def _normalize_template_text(template_text: str) -> str:
    return template_text.replace("\r\n", "\n").strip("\n")


def _normalize_rendered_text(rendered: str) -> str:
    lines = [line.rstrip() for line in rendered.replace("\r\n", "\n").split("\n")]
    return "\n".join(lines).strip()


def get_default_template() -> str:
    return DEFAULT_DESCRIPTION_TEMPLATE


def get_editor_snippets() -> list[dict[str, str]]:
    return deepcopy(EDITOR_SNIPPETS)


def list_sample_template_fixtures() -> list[dict[str, str]]:
    fixtures: list[dict[str, str]] = []
    for fixture in SAMPLE_TEMPLATE_FIXTURES.values():
        fixtures.append(
            {
                "name": str(fixture["name"]),
                "label": str(fixture["label"]),
                "description": str(fixture["description"]),
            }
        )
    fixtures.sort(key=lambda item: item["name"])
    return fixtures


def get_sample_template_context(fixture_name: str | None = None) -> dict[str, Any]:
    key = (fixture_name or "default").strip().lower()
    fixture = SAMPLE_TEMPLATE_FIXTURES.get(key) or SAMPLE_TEMPLATE_FIXTURES["default"]
    return deepcopy(fixture["context"])


def _template_path(settings: Settings) -> Path:
    return settings.description_template_file


def _template_meta_path(settings: Settings) -> Path:
    return _template_path(settings).with_suffix(".meta.json")


def _template_versions_dir(settings: Settings) -> Path:
    return _template_path(settings).parent / "template_versions"


def _read_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if isinstance(data, dict):
        return data
    return None


def _write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)


def _new_version_id(template_text: str) -> str:
    now = datetime.now(timezone.utc)
    digest = hashlib.sha256(template_text.encode("utf-8")).hexdigest()[:10]
    return f"v{now.strftime('%Y%m%dT%H%M%S%fZ')}-{digest}"


def _template_metadata_defaults() -> dict[str, Any]:
    return {
        "name": "Auto Stat Template",
        "current_version": None,
        "updated_at_utc": None,
        "updated_by": "system",
        "source": "default",
    }


def _load_template_metadata(settings: Settings) -> dict[str, Any]:
    data = _read_json_file(_template_meta_path(settings))
    if data is None:
        return _template_metadata_defaults()
    defaults = _template_metadata_defaults()
    defaults.update({k: v for k, v in data.items() if k in defaults})
    return defaults


def _save_template_metadata(settings: Settings, metadata: dict[str, Any]) -> None:
    merged = _template_metadata_defaults()
    merged.update({k: v for k, v in metadata.items() if k in merged})
    _write_json_file(_template_meta_path(settings), merged)


def _build_template_version_record(
    *,
    template_text: str,
    name: str,
    author: str,
    source: str,
    notes: str | None,
    operation: str,
    rolled_back_from: str | None = None,
) -> dict[str, Any]:
    normalized = _normalize_template_text(template_text)
    now_iso = datetime.now(timezone.utc).isoformat()
    version_id = _new_version_id(normalized)
    return {
        "version_id": version_id,
        "name": name.strip() or "Auto Stat Template",
        "author": author.strip() or "unknown",
        "source": source.strip() or "editor",
        "operation": operation,
        "notes": (notes or "").strip() or None,
        "rolled_back_from": rolled_back_from,
        "created_at_utc": now_iso,
        "template_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        "template": normalized,
    }


def _store_template_version(settings: Settings, record: dict[str, Any]) -> None:
    versions_dir = _template_versions_dir(settings)
    version_id = str(record.get("version_id") or "").strip()
    if not version_id:
        raise ValueError("Template version record missing version_id.")
    version_path = versions_dir / f"{version_id}.json"
    _write_json_file(version_path, record)


def get_template_version(settings: Settings, version_id: str) -> dict[str, Any] | None:
    version_key = version_id.strip()
    if not version_key:
        return None
    version_path = _template_versions_dir(settings) / f"{version_key}.json"
    return _read_json_file(version_path)


def list_template_versions(settings: Settings, limit: int = 50) -> list[dict[str, Any]]:
    versions_dir = _template_versions_dir(settings)
    if not versions_dir.exists():
        return []

    records: list[dict[str, Any]] = []
    for path in sorted(versions_dir.glob("*.json"), reverse=True):
        record = _read_json_file(path)
        if not record:
            continue
        records.append(
            {
                "version_id": record.get("version_id"),
                "name": record.get("name"),
                "author": record.get("author"),
                "source": record.get("source"),
                "operation": record.get("operation"),
                "notes": record.get("notes"),
                "rolled_back_from": record.get("rolled_back_from"),
                "created_at_utc": record.get("created_at_utc"),
                "template_sha256": record.get("template_sha256"),
            }
        )
        if len(records) >= max(1, int(limit)):
            break
    return records


def rollback_template_version(
    settings: Settings,
    *,
    version_id: str,
    author: str = "unknown",
    source: str = "rollback",
    notes: str | None = None,
) -> dict[str, Any]:
    record = get_template_version(settings, version_id)
    if not record:
        raise ValueError(f"Unknown template version: {version_id}")

    template_text = record.get("template")
    if not isinstance(template_text, str) or not template_text.strip():
        raise ValueError("Selected template version has no template body.")

    current = get_active_template(settings)
    rollback_name = str(record.get("name") or current.get("name") or "Auto Stat Template")
    saved = save_active_template(
        settings,
        template_text,
        name=rollback_name,
        author=author,
        source=source,
        notes=notes or f"Rollback to {version_id}",
        operation="rollback",
        rolled_back_from=version_id,
    )
    return saved


def get_active_template(settings: Settings) -> dict[str, Any]:
    path = _template_path(settings)
    metadata = _load_template_metadata(settings)
    if path.exists():
        text = path.read_text(encoding="utf-8").strip()
        if text:
            return {
                "template": _normalize_template_text(text),
                "is_custom": True,
                "path": str(path),
                "name": metadata.get("name"),
                "current_version": metadata.get("current_version"),
                "updated_at_utc": metadata.get("updated_at_utc"),
                "updated_by": metadata.get("updated_by"),
                "source": metadata.get("source"),
                "metadata": metadata,
            }
    default_meta = _template_metadata_defaults()
    return {
        "template": get_default_template(),
        "is_custom": False,
        "path": str(path),
        "name": default_meta["name"],
        "current_version": None,
        "updated_at_utc": None,
        "updated_by": default_meta["updated_by"],
        "source": default_meta["source"],
        "metadata": default_meta,
    }


def save_active_template(
    settings: Settings,
    template_text: str,
    *,
    name: str | None = None,
    author: str = "unknown",
    source: str = "editor",
    notes: str | None = None,
    operation: str = "save",
    rolled_back_from: str | None = None,
) -> dict[str, Any]:
    path = _template_path(settings)
    normalized = _normalize_template_text(template_text)
    if not normalized:
        raise ValueError("template_text must not be empty.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(normalized + "\n", encoding="utf-8")

    current = get_active_template(settings)
    record = _build_template_version_record(
        template_text=normalized,
        name=name or str(current.get("name") or "Auto Stat Template"),
        author=author,
        source=source,
        notes=notes,
        operation=operation,
        rolled_back_from=rolled_back_from,
    )
    _store_template_version(settings, record)

    metadata = _template_metadata_defaults()
    metadata.update(
        {
            "name": record["name"],
            "current_version": record["version_id"],
            "updated_at_utc": record["created_at_utc"],
            "updated_by": record["author"],
            "source": record["source"],
        }
    )
    _save_template_metadata(settings, metadata)

    active = get_active_template(settings)
    active["saved_version"] = record["version_id"]
    return active


def _lint_template_text(template_text: str) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []

    if len(template_text) > MAX_TEMPLATE_CHARS:
        errors.append(
            f"Template is too large ({len(template_text)} chars). Max allowed: {MAX_TEMPLATE_CHARS}."
        )

    for pattern, message in FORBIDDEN_TEMPLATE_PATTERNS:
        if pattern.search(template_text):
            errors.append(message)

    if "raw." in template_text:
        warnings.append("Template uses raw payload fields; prefer curated fields for stability.")

    long_line_count = 0
    for line in template_text.splitlines():
        if len(line) > 240:
            long_line_count += 1
    if long_line_count:
        warnings.append(f"Template has {long_line_count} long line(s) over 240 chars.")

    return warnings, errors


def validate_template_text(template_text: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    env = _template_environment()
    template_text = _normalize_template_text(template_text)

    errors: list[str] = []
    warnings: list[str] = []
    undeclared: list[str] = []
    lint_warnings, lint_errors = _lint_template_text(template_text)
    warnings.extend(lint_warnings)
    errors.extend(lint_errors)

    if errors:
        return {
            "valid": False,
            "errors": errors,
            "warnings": warnings,
            "undeclared_variables": undeclared,
        }

    try:
        ast = env.parse(template_text)
        undeclared = sorted(meta.find_undeclared_variables(ast))
    except TemplateError as exc:
        return {
            "valid": False,
            "errors": [str(exc)],
            "warnings": warnings,
            "undeclared_variables": undeclared,
        }

    if context is not None:
        unknown_top_level = sorted(
            var for var in undeclared if var not in set(context.keys())
        )
        if unknown_top_level:
            warnings.append(
                "Template references top-level variables not present in context: "
                + ", ".join(unknown_top_level)
            )

        try:
            rendered = env.from_string(template_text).render(context)
            _normalize_rendered_text(rendered)
        except TemplateError as exc:
            errors.append(str(exc))
    else:
        warnings.append("No render context was provided for runtime validation.")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "undeclared_variables": undeclared,
    }


def render_template_text(template_text: str, context: dict[str, Any]) -> dict[str, Any]:
    env = _template_environment()
    template_text = _normalize_template_text(template_text)
    try:
        template = env.from_string(template_text)
        rendered = template.render(context)
    except TemplateError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "description": None,
        }

    return {
        "ok": True,
        "error": None,
        "description": _normalize_rendered_text(rendered),
    }


def render_with_active_template(settings: Settings, context: dict[str, Any]) -> dict[str, Any]:
    active = get_active_template(settings)
    render_result = render_template_text(active["template"], context)
    render_result["is_custom_template"] = active["is_custom"]
    render_result["template_path"] = active["path"]

    if render_result["ok"]:
        render_result["fallback_used"] = False
        return render_result

    if active["is_custom"]:
        fallback_result = render_template_text(get_default_template(), context)
        fallback_result["is_custom_template"] = active["is_custom"]
        fallback_result["template_path"] = active["path"]
        fallback_result["fallback_used"] = fallback_result["ok"]
        fallback_result["fallback_reason"] = render_result["error"]
        return fallback_result

    render_result["fallback_used"] = False
    return render_result


def _sample_value(value: Any) -> Any:
    if isinstance(value, dict):
        return "{...}"
    if isinstance(value, list):
        if not value:
            return []
        return value[:3]
    return value


def _type_name(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    if value is None:
        return "null"
    return type(value).__name__


_GROUP_SOURCE_MAP: dict[str, tuple[str, str]] = {
    "achievements": ("Intervals.icu", "Achievement badges from Intervals activity payload."),
    "activity": ("Strava", "Latest activity metrics. Elevation can be overridden by Smashrun."),
    "crono": ("crono-api", "Local nutrition/energy balance API values."),
    "intervals": ("Intervals.icu", "Intervals.icu rollup metrics."),
    "notables": ("Smashrun", "Smashrun notable badges for latest run."),
    "periods": ("Strava+Smashrun+Garmin", "Aggregated rolling summaries by period."),
    "raw": ("Mixed", "Raw and derived payloads from all enabled services."),
    "streak_days": ("Smashrun", "Current run streak length from Smashrun."),
    "training": ("Garmin+Strava", "Garmin metrics with Strava fallback for missing HR/cadence."),
    "weather": ("Weather.com", "Weather + AQI conditions for activity time."),
}


_FIELD_SOURCE_EXACT_MAP: dict[str, tuple[str, str]] = {
    "activity.elevation_feet": ("Smashrun", "Per-activity elevation from Smashrun; Strava fallback."),
    "activity.gap_pace": ("Strava+Garmin", "Strava GAP pace when available; Garmin/average-speed fallback."),
    "activity.beers": ("Strava", "Calories from Strava converted to beers."),
    "crono.line": ("crono-api", "Legacy preformatted line for backward compatibility."),
    "crono.average_net_kcal_per_day": ("crono-api", "Trailing completed-day average net calories."),
    "crono.average_status": ("crono-api", "Energy trend label (deficit/surplus)."),
    "crono.protein_g": ("crono-api", "Protein grams for activity day."),
    "crono.carbs_g": ("crono-api", "Carb grams for activity day."),
    "crono.date": ("crono-api", "Resolved local date used for Crono lookup."),
    "periods.week.elevation_feet": ("Smashrun", "7-day elevation total from Smashrun."),
    "periods.month.elevation_feet": ("Smashrun", "30-day elevation total from Smashrun."),
    "periods.year.elevation_feet": ("Smashrun", "YTD elevation total from Smashrun."),
    "periods.week.gap": ("Strava+Garmin", "Average GAP from Strava runs; Garmin fallback."),
    "periods.month.gap": ("Strava+Garmin", "Average GAP from Strava runs; Garmin fallback."),
    "periods.year.gap": ("Strava+Garmin", "Average GAP from Strava runs; Garmin fallback."),
    "periods.week.beers": ("Strava+Garmin", "Calories-derived beers from Strava; Garmin fallback."),
    "periods.month.beers": ("Strava+Garmin", "Calories-derived beers from Strava; Garmin fallback."),
    "periods.year.beers": ("Strava+Garmin", "Calories-derived beers from Strava; Garmin fallback."),
    "raw.activity": ("Strava", "Raw activity detail payload."),
    "raw.training": ("Garmin", "Raw Garmin-derived training payload."),
    "raw.intervals": ("Intervals.icu", "Raw Intervals payload."),
    "raw.weather": ("Weather.com", "Raw weather payload."),
    "raw.week": ("Derived", "Computed 7-day aggregate from source activities."),
    "raw.month": ("Derived", "Computed 30-day aggregate from source activities."),
    "raw.year": ("Derived", "Computed YTD aggregate from source activities."),
}


def _source_for_path(path: str) -> tuple[str, str]:
    exact = _FIELD_SOURCE_EXACT_MAP.get(path)
    if exact:
        return exact

    for prefix, details in (
        ("raw.activity.", ("Strava", "Raw activity detail payload.")),
        ("raw.training.", ("Garmin", "Raw Garmin-derived training payload.")),
        ("raw.intervals.", ("Intervals.icu", "Raw Intervals payload.")),
        ("raw.weather.", ("Weather.com", "Raw weather payload.")),
        ("raw.week.", ("Derived", "Computed 7-day aggregate from source activities.")),
        ("raw.month.", ("Derived", "Computed 30-day aggregate from source activities.")),
        ("raw.year.", ("Derived", "Computed YTD aggregate from source activities.")),
        ("weather.details.", ("Weather.com", "Detailed weather conditions for activity time.")),
    ):
        if path.startswith(prefix):
            return details

    top_key = path.split(".", 1)[0].split("[", 1)[0]
    return _GROUP_SOURCE_MAP.get(top_key, ("Unknown", "No source mapping available."))


def _collect_schema_fields(path_prefix: str, value: Any, fields: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        for key, nested in sorted(value.items()):
            next_path = f"{path_prefix}.{key}" if path_prefix else key
            _collect_schema_fields(next_path, nested, fields)
        return

    if isinstance(value, list):
        source, source_note = _source_for_path(path_prefix)
        fields.append(
            {
                "path": path_prefix,
                "type": _type_name(value),
                "sample": _sample_value(value),
                "source": source,
                "source_note": source_note,
            }
        )
        if value and isinstance(value[0], dict):
            for key, nested in sorted(value[0].items()):
                _collect_schema_fields(f"{path_prefix}[0].{key}", nested, fields)
        return

    source, source_note = _source_for_path(path_prefix)
    fields.append(
        {
            "path": path_prefix,
            "type": _type_name(value),
            "sample": _sample_value(value),
            "source": source,
            "source_note": source_note,
        }
    )


def build_context_schema(context: dict[str, Any]) -> dict[str, Any]:
    groups: list[dict[str, Any]] = []
    total_fields = 0

    for top_key in sorted(context.keys()):
        value = context[top_key]
        fields: list[dict[str, Any]] = []
        if isinstance(value, dict):
            for key, nested in sorted(value.items()):
                _collect_schema_fields(f"{top_key}.{key}", nested, fields)
        else:
            _collect_schema_fields(top_key, value, fields)

        total_fields += len(fields)
        group_source, group_source_note = _GROUP_SOURCE_MAP.get(
            top_key, ("Unknown", "No source mapping available.")
        )
        groups.append(
            {
                "group": top_key,
                "field_count": len(fields),
                "source": group_source,
                "source_note": group_source_note,
                "fields": fields,
            }
        )

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "group_count": len(groups),
        "field_count": total_fields,
        "groups": groups,
    }
