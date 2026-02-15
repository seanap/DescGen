from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import StrictUndefined, TemplateError, meta
from jinja2.sandbox import SandboxedEnvironment

from config import Settings


DEFAULT_DESCRIPTION_TEMPLATE = """🏆 {{ streak_days }} days in a row
{% for notable in notables %}🏅 {{ notable }}
{% endfor %}{% for achievement in achievements %}🏅 {{ achievement }}
{% endfor %}🌤️🌡️ Misery Index: {{ weather.misery_index }} {{ weather.misery_description }} | 🏭 AQI: {{ weather.aqi }}{{ weather.aqi_description }}
{% if crono.line %}{{ crono.line }}
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


def _template_path(settings: Settings) -> Path:
    return settings.description_template_file


def get_active_template(settings: Settings) -> dict[str, Any]:
    path = _template_path(settings)
    if path.exists():
        text = path.read_text(encoding="utf-8").strip()
        if text:
            return {
                "template": _normalize_template_text(text),
                "is_custom": True,
                "path": str(path),
            }
    return {
        "template": get_default_template(),
        "is_custom": False,
        "path": str(path),
    }


def save_active_template(settings: Settings, template_text: str) -> Path:
    path = _template_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_normalize_template_text(template_text) + "\n", encoding="utf-8")
    return path


def validate_template_text(template_text: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    env = _template_environment()
    template_text = _normalize_template_text(template_text)

    errors: list[str] = []
    warnings: list[str] = []
    undeclared: list[str] = []

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


def _collect_schema_fields(path_prefix: str, value: Any, fields: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        for key, nested in sorted(value.items()):
            next_path = f"{path_prefix}.{key}" if path_prefix else key
            _collect_schema_fields(next_path, nested, fields)
        return

    if isinstance(value, list):
        fields.append(
            {
                "path": path_prefix,
                "type": _type_name(value),
                "sample": _sample_value(value),
            }
        )
        if value and isinstance(value[0], dict):
            for key, nested in sorted(value[0].items()):
                _collect_schema_fields(f"{path_prefix}[0].{key}", nested, fields)
        return

    fields.append(
        {
            "path": path_prefix,
            "type": _type_name(value),
            "sample": _sample_value(value),
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
        groups.append(
            {
                "group": top_key,
                "field_count": len(fields),
                "fields": fields,
            }
        )

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "group_count": len(groups),
        "field_count": total_fields,
        "groups": groups,
    }
