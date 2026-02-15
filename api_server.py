from __future__ import annotations

from datetime import datetime, timezone

from flask import Flask, render_template, request

from description_template import (
    build_context_schema,
    get_editor_snippets,
    get_default_template,
    get_active_template,
    get_sample_template_context,
    render_template_text,
    save_active_template,
    validate_template_text,
)
from main_strava_update import run_once

from config import Settings
from storage import read_json


app = Flask(__name__)
settings = Settings.from_env()
settings.ensure_state_paths()


def _latest_payload() -> dict | None:
    return read_json(settings.latest_json_file)


def _latest_template_context() -> dict | None:
    payload = _latest_payload()
    if not payload:
        return None
    context = payload.get("template_context")
    if isinstance(context, dict):
        return context
    return None


def _resolve_context_mode(raw_mode: str | None) -> str:
    mode = (raw_mode or "latest").strip().lower()
    if mode not in {"latest", "sample", "latest_or_sample"}:
        raise ValueError("context_mode must be one of: latest, sample, latest_or_sample.")
    return mode


def _context_for_mode(mode: str) -> tuple[dict | None, str]:
    if mode == "latest":
        return _latest_template_context(), "latest"
    if mode == "sample":
        return get_sample_template_context(), "sample"

    latest = _latest_template_context()
    if latest is not None:
        return latest, "latest"
    return get_sample_template_context(), "sample"


@app.get("/health")
def health() -> tuple[dict, int]:
    payload = _latest_payload()
    return (
        {
            "status": "ok",
            "time_utc": datetime.now(timezone.utc).isoformat(),
            "latest_payload_exists": payload is not None,
        },
        200,
    )


@app.get("/latest")
def latest() -> tuple[dict, int]:
    payload = _latest_payload()
    if payload is None:
        return {"error": "No activity payload has been written yet."}, 404
    return payload, 200


@app.get("/editor")
def editor_page() -> str:
    return render_template("editor.html")


@app.get("/editor/template")
def editor_template_get() -> tuple[dict, int]:
    active = get_active_template(settings)
    return {
        "status": "ok",
        "template": active["template"],
        "is_custom": active["is_custom"],
        "template_path": active["path"],
    }, 200


@app.get("/editor/template/default")
def editor_template_default_get() -> tuple[dict, int]:
    return {
        "status": "ok",
        "template": get_default_template(),
    }, 200


@app.get("/editor/snippets")
def editor_snippets_get() -> tuple[dict, int]:
    return {
        "status": "ok",
        "snippets": get_editor_snippets(),
        "context_modes": ["latest", "sample", "latest_or_sample"],
    }, 200


@app.get("/editor/context/sample")
def editor_sample_context_get() -> tuple[dict, int]:
    context = get_sample_template_context()
    return {
        "status": "ok",
        "context": context,
        "schema": build_context_schema(context),
    }, 200


@app.put("/editor/template")
def editor_template_put() -> tuple[dict, int]:
    body = request.get_json(silent=True) or {}
    template_text = body.get("template")
    if not isinstance(template_text, str) or not template_text.strip():
        return {"status": "error", "error": "template must be a non-empty string."}, 400

    context = _latest_template_context()
    validation = validate_template_text(template_text, context)
    if not validation["valid"]:
        return {"status": "error", "validation": validation}, 400

    path = save_active_template(settings, template_text)
    return {
        "status": "ok",
        "template_path": str(path),
        "validation": validation,
    }, 200


@app.post("/editor/validate")
def editor_validate() -> tuple[dict, int]:
    body = request.get_json(silent=True) or {}
    template_text = body.get("template")
    if template_text is None:
        template_text = get_active_template(settings)["template"]
    if not isinstance(template_text, str):
        return {"status": "error", "error": "template must be a string."}, 400

    try:
        context_mode = _resolve_context_mode(body.get("context_mode"))
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 400

    context, context_source = _context_for_mode(context_mode)
    validation = validate_template_text(template_text, context)
    return {
        "status": "ok" if validation["valid"] else "error",
        "has_context": context is not None,
        "context_source": context_source if context is not None else None,
        "validation": validation,
    }, 200 if validation["valid"] else 400


@app.post("/editor/preview")
def editor_preview() -> tuple[dict, int]:
    body = request.get_json(silent=True) or {}
    template_text = body.get("template")
    if template_text is None:
        template_text = get_active_template(settings)["template"]
    if not isinstance(template_text, str):
        return {"status": "error", "error": "template must be a string."}, 400

    try:
        context_mode = _resolve_context_mode(body.get("context_mode"))
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 400

    context, context_source = _context_for_mode(context_mode)
    if context is None:
        return {
            "status": "error",
            "error": "No template context is available yet. Run one update cycle first.",
        }, 404

    result = render_template_text(template_text, context)
    if not result["ok"]:
        return {"status": "error", "error": result["error"]}, 400
    return {
        "status": "ok",
        "context_source": context_source,
        "preview": result["description"],
        "length": len(result["description"]),
    }, 200


@app.get("/editor/schema")
def editor_schema() -> tuple[dict, int]:
    raw_mode = request.args.get("context_mode")
    try:
        context_mode = _resolve_context_mode(raw_mode)
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 400

    context, context_source = _context_for_mode(context_mode)
    if context is None:
        return {
            "status": "ok",
            "has_context": False,
            "context_source": None,
            "schema": build_context_schema({}),
        }, 200
    return {
        "status": "ok",
        "has_context": True,
        "context_source": context_source,
        "schema": build_context_schema(context),
    }, 200


@app.post("/rerun/latest")
def rerun_latest() -> tuple[dict, int]:
    try:
        result = run_once(force_update=True)
        return {"status": "ok", "result": result}, 200
    except Exception as exc:
        return {"status": "error", "error": str(exc)}, 500


@app.post("/rerun/activity/<int:activity_id>")
def rerun_activity(activity_id: int) -> tuple[dict, int]:
    try:
        result = run_once(force_update=True, activity_id=activity_id)
        return {"status": "ok", "result": result}, 200
    except Exception as exc:
        return {"status": "error", "error": str(exc)}, 500


@app.post("/rerun")
def rerun() -> tuple[dict, int]:
    body = request.get_json(silent=True) or {}
    activity_id = body.get("activity_id")
    if activity_id is None:
        try:
            result = run_once(force_update=True)
            return {"status": "ok", "result": result}, 200
        except Exception as exc:
            return {"status": "error", "error": str(exc)}, 500

    try:
        activity_id_int = int(activity_id)
    except (TypeError, ValueError):
        return {"status": "error", "error": "activity_id must be an integer."}, 400

    try:
        result = run_once(force_update=True, activity_id=activity_id_int)
        return {"status": "ok", "result": result}, 200
    except Exception as exc:
        return {"status": "error", "error": str(exc)}, 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.api_port)
