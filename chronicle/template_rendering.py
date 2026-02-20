from __future__ import annotations

from typing import Any

from .config import Settings
from .description_template import (
    normalize_template_context,
    render_template_text,
    render_with_active_template,
    validate_template_text,
)

__all__ = [
    "normalize_template_context",
    "render_template_text",
    "render_with_active_template",
    "validate_template_text",
]


def validate_and_render(
    settings: Settings,
    template_text: str,
    context: dict[str, Any],
    *,
    profile_id: str | None = None,
) -> dict[str, Any]:
    validation = validate_template_text(template_text, context)
    if not validation.get("valid"):
        return {
            "ok": False,
            "validation": validation,
            "render": None,
        }

    if profile_id:
        render_result = render_with_active_template(settings, context, profile_id=profile_id)
    else:
        render_result = render_template_text(template_text, context)
    return {
        "ok": bool(render_result.get("ok")),
        "validation": validation,
        "render": render_result,
    }
