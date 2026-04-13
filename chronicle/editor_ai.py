from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .agent_runner import TemplateCustomizeRequest, agent_provider_status, generate_template_customization


@dataclass(frozen=True)
class EditorAssistantRequest:
    request_text: str
    template_text: str
    profile_id: str
    context_mode: str
    fixture_name: str | None = None
    preview_text: str | None = None
    selected_text: str | None = None
    available_context_keys: tuple[str, ...] = ()


def editor_assistant_status(settings: Any) -> dict[str, Any]:
    status = agent_provider_status(settings)
    return {
        "enabled": bool(getattr(settings, "enable_editor_ai", False)),
        "available": bool(getattr(settings, "enable_editor_ai", False)) and bool(status.get("available")),
        "reason": status.get("reason"),
        "provider": status.get("provider"),
        "protocol_version": status.get("protocol_version"),
        **({"remote_url": status.get("remote_url")} if status.get("remote_url") else {}),
        **({"cli_path": status.get("cli_path")} if status.get("cli_path") else {}),
    }


def generate_editor_customization(settings: Any, request: EditorAssistantRequest) -> dict[str, Any]:
    if not bool(getattr(settings, "enable_editor_ai", False)):
        raise RuntimeError("Editor AI is disabled by configuration.")
    return generate_template_customization(
        settings,
        TemplateCustomizeRequest(
            request_text=request.request_text,
            template_text=request.template_text,
            profile_id=request.profile_id,
            context_mode=request.context_mode,
            fixture_name=request.fixture_name,
            preview_text=request.preview_text,
            selected_text=request.selected_text,
            available_context_keys=request.available_context_keys,
        ),
    )
