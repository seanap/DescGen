from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any

import requests
from flask import Flask, jsonify, request

from chronicle.agent_runner import (
    COMPANION_PROTOCOL_VERSION,
    TemplateCustomizeRequest,
    generate_bundle_create,
    generate_plan_next_week_draft,
    generate_template_customization,
)


app = Flask(__name__)


def _companion_settings() -> SimpleNamespace:
    return SimpleNamespace(
        agent_provider="local_codex_exec",
        editor_ai_codex_cli_path=os.getenv("EDITOR_AI_CODEX_CLI_PATH"),
        editor_ai_workspace_dir=os.getenv("EDITOR_AI_WORKSPACE_DIR") or ".",
        editor_ai_timeout_seconds=int(os.getenv("EDITOR_AI_TIMEOUT_SECONDS", "90")),
        editor_ai_codex_model=os.getenv("EDITOR_AI_CODEX_MODEL"),
    )


def _require_api_key() -> tuple[dict[str, Any], int] | None:
    expected = str(os.getenv("CHRONICLE_COMPANION_API_KEY", "") or "").strip()
    if not expected:
        return None
    presented = str(request.headers.get("X-Chronicle-Agent-Key") or "").strip()
    if presented != expected:
        return {"status": "error", "error": "Unauthorized."}, 401
    return None


def _chronicle_get(base_url: str, api_key: str | None, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
    headers = {}
    if api_key:
        headers["X-Chronicle-Agent-Key"] = api_key
    response = requests.get(
        f"{base_url.rstrip('/')}{path}",
        params=params,
        headers=headers,
        timeout=int(os.getenv("CHRONICLE_COMPANION_HTTP_TIMEOUT_SECONDS", "30")),
    )
    payload = response.json()
    if response.status_code >= 400:
        raise RuntimeError(str(payload.get("error") or f"Chronicle request failed: {response.status_code}"))
    return payload


@app.get("/health")
def health() -> tuple[dict[str, Any], int]:
    return {"status": "ok", "protocol_version": COMPANION_PROTOCOL_VERSION}, 200


@app.get("/v1/handshake")
def handshake() -> tuple[dict[str, Any], int]:
    return {
        "status": "ok",
        "protocol_version": COMPANION_PROTOCOL_VERSION,
        "capabilities": ["template_customize", "plan_next_week_draft", "bundle_create"],
    }, 200


@app.post("/v1/tasks/execute")
def execute_task() -> tuple[dict[str, Any], int]:
    auth_error = _require_api_key()
    if auth_error is not None:
        return auth_error

    body = request.get_json(silent=True) or {}
    protocol_version = str(body.get("protocol_version") or "").strip()
    if protocol_version and protocol_version != COMPANION_PROTOCOL_VERSION:
        return {
            "status": "error",
            "error": f"Unsupported protocol_version '{protocol_version}'.",
        }, 400

    task = str(body.get("task") or "").strip()
    payload = body.get("payload") if isinstance(body.get("payload"), dict) else {}
    settings = _companion_settings()

    try:
        if task == "template_customize":
            result = generate_template_customization(
                settings,
                TemplateCustomizeRequest(
                    request_text=str(payload.get("request_text") or ""),
                    template_text=str(payload.get("template_text") or ""),
                    profile_id=str(payload.get("profile_id") or "default"),
                    context_mode=str(payload.get("context_mode") or "sample"),
                    fixture_name=str(payload.get("fixture_name") or "").strip() or None,
                    preview_text=str(payload.get("preview_text") or "").strip() or None,
                    selected_text=str(payload.get("selected_text") or "").strip() or None,
                    available_context_keys=tuple(
                        str(item).strip()
                        for item in (payload.get("available_context_keys") or [])
                        if str(item).strip()
                    ),
                ),
            )
        elif task == "plan_next_week_draft":
            context_payload = payload.get("context_payload")
            if not isinstance(context_payload, dict):
                context_payload = {}
            chronicle_context = payload.get("chronicle_context")
            if not isinstance(chronicle_context, dict):
                chronicle_context = {}
            if not context_payload and chronicle_context.get("base_url"):
                context_response = _chronicle_get(
                    str(chronicle_context.get("base_url")),
                    str(chronicle_context.get("api_key") or "").strip() or None,
                    "/agent-control/plans/next-week-context",
                    params={"week_start_local": str(payload.get("week_start_local") or "").strip()},
                )
                context_payload = (
                    context_response.get("context")
                    if isinstance(context_response.get("context"), dict)
                    else context_response
                )
            result = generate_plan_next_week_draft(
                settings,
                user_request=str(payload.get("user_request") or ""),
                week_start_local=str(payload.get("week_start_local") or ""),
                context_payload=context_payload,
                chronicle_context=chronicle_context,
            )
        elif task == "bundle_create":
            result = generate_bundle_create(
                settings,
                user_request=str(payload.get("user_request") or ""),
                chronicle_context=payload.get("chronicle_context") if isinstance(payload.get("chronicle_context"), dict) else {},
            )
        else:
            return {"status": "error", "error": "Unknown task."}, 404
    except RuntimeError as exc:
        return {"status": "error", "error": str(exc)}, 503

    return {
        "status": "ok",
        "protocol_version": COMPANION_PROTOCOL_VERSION,
        "result": result,
    }, 200


if __name__ == "__main__":
    host = os.getenv("CHRONICLE_COMPANION_HOST", "0.0.0.0")
    port = int(os.getenv("CHRONICLE_COMPANION_PORT", "8788"))
    app.run(host=host, port=port)
