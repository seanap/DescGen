from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMPANION_ROOT = PROJECT_ROOT / "ai" / "chronicle_companion"
PROMPTS_ROOT = COMPANION_ROOT / "prompts"
COMPANION_PROTOCOL_VERSION = "1"


@dataclass(frozen=True)
class TemplateCustomizeRequest:
    request_text: str
    template_text: str
    profile_id: str
    context_mode: str
    fixture_name: str | None = None
    preview_text: str | None = None
    selected_text: str | None = None
    available_context_keys: tuple[str, ...] = ()


def _resolve_codex_cli_path(settings: Any) -> str | None:
    configured = str(getattr(settings, "editor_ai_codex_cli_path", "") or "").strip()
    if configured:
        expanded = str(Path(configured).expanduser())
        return expanded if shutil.which(expanded) else None
    return shutil.which("codex")


def _trim_block(value: str | None, maximum: int) -> str:
    text = str(value or "").strip()
    if len(text) <= maximum:
        return text
    omitted = len(text) - maximum
    return f"{text[:maximum].rstrip()}\n\n[truncated {omitted} characters]"


def agent_provider_status(settings: Any) -> dict[str, Any]:
    provider = str(getattr(settings, "agent_provider", "local_codex_exec") or "local_codex_exec").strip()
    if provider == "remote_codex_exec":
        remote_url = str(getattr(settings, "agent_remote_url", "") or "").strip()
        if not remote_url:
            return {
                "provider": provider,
                "available": False,
                "reason": "AGENT_REMOTE_URL is not configured.",
                "protocol_version": COMPANION_PROTOCOL_VERSION,
            }
        return {
            "provider": provider,
            "available": True,
            "reason": None,
            "remote_url": remote_url,
            "protocol_version": COMPANION_PROTOCOL_VERSION,
        }

    cli_path = _resolve_codex_cli_path(settings)
    if cli_path is None:
        return {
            "provider": "local_codex_exec",
            "available": False,
            "reason": "Codex CLI was not found on PATH.",
            "protocol_version": COMPANION_PROTOCOL_VERSION,
        }
    return {
        "provider": "local_codex_exec",
        "available": True,
        "reason": None,
        "cli_path": cli_path,
        "workspace_dir": str(getattr(settings, "editor_ai_workspace_dir", COMPANION_ROOT)),
        "protocol_version": COMPANION_PROTOCOL_VERSION,
    }


def _prompt_text(name: str) -> str:
    return (PROMPTS_ROOT / name).read_text(encoding="utf-8").strip()


def _run_codex_structured(settings: Any, *, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
    status = agent_provider_status(settings)
    if not status.get("available"):
        raise RuntimeError(str(status.get("reason") or "Agent provider unavailable."))
    cli_path = str(status.get("cli_path") or "")
    if not cli_path:
        raise RuntimeError("Local Codex CLI path is unavailable.")

    workspace_dir = Path(getattr(settings, "editor_ai_workspace_dir", COMPANION_ROOT))
    workspace_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="chronicle-agent-") as temp_dir:
        temp_root = Path(temp_dir)
        schema_path = temp_root / "output-schema.json"
        output_path = temp_root / "last-message.json"
        schema_path.write_text(json.dumps(schema), encoding="utf-8")

        cmd = [
            cli_path,
            "exec",
            "--color",
            "never",
            "--sandbox",
            "read-only",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            "-C",
            str(workspace_dir),
            "-",
        ]
        model = str(getattr(settings, "editor_ai_codex_model", "") or "").strip()
        if model:
            cmd[2:2] = ["--model", model]

        completed = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            capture_output=True,
            timeout=max(10, int(getattr(settings, "editor_ai_timeout_seconds", 90))),
            cwd=str(workspace_dir),
            check=False,
        )
        if completed.returncode != 0:
            detail = str(completed.stderr or "").strip() or str(completed.stdout or "").strip()
            raise RuntimeError(detail or f"codex exited with status {completed.returncode}")
        if not output_path.is_file():
            raise RuntimeError("Codex completed without writing the final response.")
        try:
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Codex returned invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("Codex returned an invalid response payload.")
        return payload


def _remote_execute(settings: Any, *, task_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    status = agent_provider_status(settings)
    if not status.get("available"):
        raise RuntimeError(str(status.get("reason") or "Agent provider unavailable."))
    remote_url = str(status.get("remote_url") or "").rstrip("/")
    if not remote_url:
        raise RuntimeError("Remote agent URL is unavailable.")
    headers = {"Content-Type": "application/json"}
    api_key = str(getattr(settings, "agent_remote_api_key", "") or "").strip()
    if api_key:
        headers["X-Chronicle-Agent-Key"] = api_key
    response = requests.post(
        f"{remote_url}/v1/tasks/execute",
        json={
            "protocol_version": COMPANION_PROTOCOL_VERSION,
            "task": task_name,
            "payload": payload,
        },
        headers=headers,
        timeout=max(5, int(getattr(settings, "agent_remote_timeout_seconds", 120))),
    )
    parsed = response.json()
    if response.status_code >= 400:
        raise RuntimeError(str(parsed.get("error") or f"remote provider failed with {response.status_code}"))
    result = parsed.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("Remote provider returned an invalid result payload.")
    return result


def generate_template_customization(settings: Any, request: TemplateCustomizeRequest) -> dict[str, Any]:
    status = agent_provider_status(settings)
    if not status.get("available"):
        raise RuntimeError(str(status.get("reason") or "Template customization is unavailable."))
    payload = {
        "request_text": request.request_text,
        "template_text": request.template_text,
        "profile_id": request.profile_id,
        "context_mode": request.context_mode,
        "fixture_name": request.fixture_name,
        "preview_text": request.preview_text,
        "selected_text": request.selected_text,
        "available_context_keys": list(request.available_context_keys),
    }
    if str(status.get("provider") or "") == "remote_codex_exec":
        return _remote_execute(settings, task_name="template_customize", payload=payload)

    prompt = "\n".join(
        [
            _prompt_text("template_customize.md"),
            "",
            f"Profile id: {request.profile_id}",
            f"Context mode: {request.context_mode}",
            f"Fixture: {request.fixture_name or 'none'}",
            f"Available top-level context keys: {', '.join(request.available_context_keys) if request.available_context_keys else 'unknown'}",
            "",
            "User request:",
            _trim_block(request.request_text, 2000),
            "",
            "Current template:",
            _trim_block(request.template_text, 16000),
            "",
            "Selected text:",
            _trim_block(request.selected_text, 4000) or "none",
            "",
            "Current preview:",
            _trim_block(request.preview_text, 4000) or "none",
        ]
    )
    schema = {
        "type": "object",
        "properties": {
            "suggested_text": {"type": "string"},
            "placement_hint": {"type": "string"},
            "notes": {"type": "string"},
        },
        "required": ["suggested_text", "placement_hint", "notes"],
        "additionalProperties": False,
    }
    result = _run_codex_structured(settings, prompt=prompt, schema=schema)
    result["profile_id"] = request.profile_id
    result["context_mode"] = request.context_mode
    result["fixture_name"] = request.fixture_name
    return result


def generate_plan_next_week_draft(
    settings: Any,
    *,
    user_request: str,
    week_start_local: str,
    context_payload: dict[str, Any] | None = None,
    chronicle_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status = agent_provider_status(settings)
    if not status.get("available"):
        raise RuntimeError(str(status.get("reason") or "Plan drafting is unavailable."))
    payload = {
        "user_request": user_request,
        "week_start_local": week_start_local,
        "context_payload": context_payload or {},
        "chronicle_context": chronicle_context or {},
    }
    if str(status.get("provider") or "") == "remote_codex_exec":
        return _remote_execute(settings, task_name="plan_next_week_draft", payload=payload)

    prompt = "\n".join(
        [
            _prompt_text("plan_next_week_draft.md"),
            "",
            f"Week start local: {week_start_local}",
            "",
            "User request:",
            _trim_block(user_request, 2000),
            "",
            "Chronicle plan context:",
            _trim_block(json.dumps(context_payload or {}, indent=2, sort_keys=True), 18000),
        ]
    )
    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "warnings": {"type": "array", "items": {"type": "string"}},
            "days": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "date_local": {"type": "string"},
                        "run_type": {"type": "string"},
                        "planned_total_miles": {"type": ["number", "null"]},
                        "notes": {"type": ["string", "null"]},
                        "sessions": {"type": ["array", "null"]},
                    },
                    "required": ["date_local"],
                    "additionalProperties": True,
                },
            },
        },
        "required": ["title", "summary", "warnings", "days"],
        "additionalProperties": False,
    }
    return _run_codex_structured(settings, prompt=prompt, schema=schema)


def generate_bundle_create(
    settings: Any,
    *,
    user_request: str,
    chronicle_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status = agent_provider_status(settings)
    if not status.get("available"):
        raise RuntimeError(str(status.get("reason") or "Bundle creation is unavailable."))
    payload = {
        "user_request": user_request,
        "chronicle_context": chronicle_context or {},
    }
    if str(status.get("provider") or "") == "remote_codex_exec":
        return _remote_execute(settings, task_name="bundle_create", payload=payload)

    prompt = "\n".join(
        [
            _prompt_text("bundle_create.md"),
            "",
            "User request:",
            _trim_block(user_request, 2000),
            "",
            "Chronicle context:",
            _trim_block(json.dumps(chronicle_context or {}, indent=2, sort_keys=True), 18000),
        ]
    )
    schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "warnings": {"type": "array", "items": {"type": "string"}},
            "profile_yaml": {"type": ["string", "null"]},
            "template_text": {"type": ["string", "null"]},
            "workout_payload": {"type": ["object", "null"]},
        },
        "required": ["summary", "warnings", "profile_yaml", "template_text", "workout_payload"],
        "additionalProperties": False,
    }
    return _run_codex_structured(settings, prompt=prompt, schema=schema)
