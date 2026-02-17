from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, render_template, request

from description_template import (
    build_context_schema,
    create_template_repository_template,
    duplicate_template_repository_template,
    export_template_repository_bundle,
    get_editor_snippets,
    get_template_repository_template,
    get_starter_templates,
    get_default_template,
    get_active_template,
    get_sample_template_context,
    get_template_version,
    import_template_repository_bundle,
    list_sample_template_fixtures,
    list_template_profiles,
    list_template_repository_templates,
    list_template_versions,
    normalize_template_context,
    get_template_profile,
    get_working_template_profile,
    rollback_template_version,
    render_template_text,
    save_active_template,
    set_working_template_profile,
    update_template_repository_template,
    update_template_profile,
    validate_template_text,
)
from activity_pipeline import run_once

from config import Settings
from storage import get_runtime_value, get_worker_heartbeat, is_worker_healthy, read_json


app = Flask(__name__)
settings = Settings.from_env()
settings.ensure_state_paths()


def _latest_payload() -> dict | None:
    return read_json(settings.latest_json_file)


def _state_path_writable(state_dir: Path) -> bool:
    probe = state_dir / ".ready_probe"
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _latest_template_context() -> dict | None:
    payload = _latest_payload()
    if not payload:
        return None
    context = payload.get("template_context")
    if isinstance(context, dict):
        return normalize_template_context(context)
    return None


def _resolve_context_mode(raw_mode: str | None) -> str:
    mode = (raw_mode or "sample").strip().lower()
    if mode not in {"latest", "sample", "latest_or_sample", "fixture"}:
        raise ValueError("context_mode must be one of: latest, sample, latest_or_sample, fixture.")
    return mode


def _resolve_fixture_name(raw_name: str | None) -> str:
    value = (raw_name or "default").strip().lower()
    return value or "default"


def _context_for_mode(mode: str, fixture_name: str | None = None) -> tuple[dict | None, str]:
    fixture = _resolve_fixture_name(fixture_name)
    if mode == "latest":
        return _latest_template_context(), "latest"
    if mode in {"sample", "fixture"}:
        return get_sample_template_context(fixture), f"sample:{fixture}"

    latest = _latest_template_context()
    if latest is not None:
        return latest, "latest"
    return get_sample_template_context(fixture), f"sample:{fixture}"


def _resolve_profile_id(raw_profile_id: str | None) -> str:
    candidate = str(raw_profile_id or "").strip().lower()
    if candidate:
        profile = get_template_profile(settings, candidate)
        if not profile:
            raise ValueError(f"Unknown profile_id: {candidate}")
        return candidate
    return str(get_working_template_profile(settings).get("profile_id") or "default")


@app.get("/health")
def health() -> tuple[dict, int]:
    payload = _latest_payload()
    heartbeat = get_worker_heartbeat(settings.processed_log_file)
    return (
        {
            "status": "ok",
            "time_utc": datetime.now(timezone.utc).isoformat(),
            "latest_payload_exists": payload is not None,
            "worker_last_heartbeat_utc": heartbeat.isoformat() if heartbeat else None,
        },
        200,
    )


@app.get("/ready")
def ready() -> tuple[dict, int]:
    checks = {
        "state_path_writable": _state_path_writable(settings.state_dir),
        "template_accessible": bool(get_active_template(settings).get("template")),
    }
    worker_healthy = is_worker_healthy(
        settings.processed_log_file,
        max_age_seconds=settings.worker_health_max_age_seconds,
    )
    checks["worker_heartbeat_healthy"] = worker_healthy

    ready_ok = checks["state_path_writable"] and checks["template_accessible"]
    status_code = 200 if ready_ok else 503
    return (
        {
            "status": "ready" if ready_ok else "not_ready",
            "time_utc": datetime.now(timezone.utc).isoformat(),
            "checks": checks,
            "cycle_last_status": get_runtime_value(settings.processed_log_file, "cycle.last_status"),
            "cycle_last_error": get_runtime_value(settings.processed_log_file, "cycle.last_error"),
        },
        status_code,
    )


@app.get("/latest")
def latest() -> tuple[dict, int]:
    payload = _latest_payload()
    if payload is None:
        return {"error": "No activity payload has been written yet."}, 404
    return payload, 200


@app.get("/service-metrics")
def service_metrics() -> tuple[dict, int]:
    cycle_metrics = get_runtime_value(settings.processed_log_file, "cycle.service_calls")
    return {
        "status": "ok",
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "cycle_service_calls": cycle_metrics if isinstance(cycle_metrics, dict) else {},
    }, 200


@app.get("/editor")
def editor_page() -> str:
    return render_template("editor.html")


@app.get("/editor/profiles")
def editor_profiles_get() -> tuple[dict, int]:
    working = get_working_template_profile(settings)
    return {
        "status": "ok",
        "working_profile_id": working.get("profile_id"),
        "profiles": list_template_profiles(settings),
    }, 200


@app.put("/editor/profiles/<string:profile_id>")
def editor_profile_put(profile_id: str) -> tuple[dict, int]:
    body = request.get_json(silent=True) or {}
    enabled = body.get("enabled")
    priority = body.get("priority")
    if enabled is None and priority is None:
        return {"status": "error", "error": "Provide enabled and/or priority."}, 400
    try:
        updated = update_template_profile(
            settings,
            profile_id,
            enabled=bool(enabled) if enabled is not None else None,
            priority=int(priority) if priority is not None else None,
        )
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 400
    return {
        "status": "ok",
        "profile": updated,
        "working_profile_id": get_working_template_profile(settings).get("profile_id"),
    }, 200


@app.post("/editor/profiles/working")
def editor_working_profile_post() -> tuple[dict, int]:
    body = request.get_json(silent=True) or {}
    profile_id = body.get("profile_id")
    if not isinstance(profile_id, str) or not profile_id.strip():
        return {"status": "error", "error": "profile_id is required."}, 400
    try:
        profile = set_working_template_profile(settings, profile_id)
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 400
    return {
        "status": "ok",
        "working_profile_id": profile.get("profile_id"),
        "profile": profile,
    }, 200


@app.get("/editor/template")
def editor_template_get() -> tuple[dict, int]:
    try:
        profile_id = _resolve_profile_id(request.args.get("profile_id"))
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 400
    active = get_active_template(settings, profile_id=profile_id)
    return {
        "status": "ok",
        "template": active["template"],
        "is_custom": active["is_custom"],
        "template_path": active["path"],
        "profile_id": active.get("profile_id"),
        "profile_label": active.get("profile_label"),
        "name": active.get("name"),
        "current_version": active.get("current_version"),
        "updated_at_utc": active.get("updated_at_utc"),
        "updated_by": active.get("updated_by"),
        "source": active.get("source"),
        "metadata": active.get("metadata"),
    }, 200


@app.get("/editor/template/default")
def editor_template_default_get() -> tuple[dict, int]:
    return {
        "status": "ok",
        "template": get_default_template(),
    }, 200


@app.get("/editor/fixtures")
def editor_fixtures_get() -> tuple[dict, int]:
    return {
        "status": "ok",
        "fixtures": list_sample_template_fixtures(),
    }, 200


@app.get("/editor/template/versions")
def editor_template_versions_get() -> tuple[dict, int]:
    limit_raw = request.args.get("limit", "30")
    try:
        limit = max(1, min(200, int(limit_raw)))
    except ValueError:
        limit = 30
    try:
        profile_id = _resolve_profile_id(request.args.get("profile_id"))
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 400
    versions = list_template_versions(settings, limit=limit, profile_id=profile_id)
    return {
        "status": "ok",
        "profile_id": profile_id,
        "versions": versions,
    }, 200


@app.get("/editor/template/export")
def editor_template_export_get() -> tuple[dict, int]:
    template_id = str(request.args.get("template_id") or "").strip()
    try:
        profile_id = _resolve_profile_id(request.args.get("profile_id"))
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 400
    include_versions_raw = str(request.args.get("include_versions", "false")).strip().lower()
    include_versions = include_versions_raw in {"1", "true", "yes", "on"}
    limit_raw = request.args.get("limit", "30")
    try:
        limit = max(1, min(200, int(limit_raw)))
    except ValueError:
        limit = 30

    if template_id:
        try:
            payload = export_template_repository_bundle(
                settings,
                template_id=template_id,
                include_versions=include_versions,
                versions_limit=limit,
            )
        except ValueError as exc:
            return {"status": "error", "error": str(exc)}, 404
        payload["status"] = "ok"
        return payload, 200

    active = get_active_template(settings, profile_id=profile_id)
    payload = {
        "status": "ok",
        "bundle_version": 1,
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "profile_id": profile_id,
        "template": active.get("template"),
        "name": active.get("name"),
        "is_custom": bool(active.get("is_custom")),
        "metadata": active.get("metadata"),
        "current_version": active.get("current_version"),
    }
    if include_versions:
        payload["versions"] = list_template_versions(settings, limit=limit, profile_id=profile_id)
    return payload, 200


@app.get("/editor/repository/templates")
def editor_repository_templates_get() -> tuple[dict, int]:
    templates = list_template_repository_templates(settings)
    return {
        "status": "ok",
        "templates": templates,
        "count": len(templates),
    }, 200


@app.get("/editor/repository/template/<string:template_id>")
def editor_repository_template_get(template_id: str) -> tuple[dict, int]:
    template = get_template_repository_template(settings, template_id)
    if not template:
        return {"status": "error", "error": "Unknown template_id."}, 404
    return {
        "status": "ok",
        "template_record": template,
    }, 200


@app.post("/editor/repository/template/<string:template_id>/load")
def editor_repository_template_load_post(template_id: str) -> tuple[dict, int]:
    template = get_template_repository_template(settings, template_id)
    if not template:
        return {"status": "error", "error": "Unknown template_id."}, 404
    return {
        "status": "ok",
        "template_record": template,
    }, 200


@app.post("/editor/repository/save_as")
def editor_repository_save_as_post() -> tuple[dict, int]:
    body = request.get_json(silent=True) or {}
    template_text = body.get("template")
    if not isinstance(template_text, str) or not template_text.strip():
        return {"status": "error", "error": "template must be a non-empty string."}, 400

    context_mode = body.get("context_mode", "sample")
    fixture_name = body.get("fixture_name")
    try:
        mode = _resolve_context_mode(context_mode)
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 400

    context, context_source = _context_for_mode(mode, fixture_name=fixture_name)
    validation = validate_template_text(template_text, context)
    if not validation["valid"]:
        return {
            "status": "error",
            "context_source": context_source if context is not None else None,
            "validation": validation,
        }, 400

    try:
        created = create_template_repository_template(
            settings,
            template_text=template_text,
            name=str(body.get("name") or "Untitled Template"),
            author=str(body.get("author") or "editor-user"),
            description=str(body.get("description") or ""),
            source=str(body.get("source") or "editor-repository-save-as"),
        )
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 400
    return {
        "status": "ok",
        "context_source": context_source if context is not None else None,
        "template_record": created,
        "validation": validation,
    }, 200


@app.put("/editor/repository/template/<string:template_id>")
def editor_repository_template_put(template_id: str) -> tuple[dict, int]:
    body = request.get_json(silent=True) or {}
    template_text = body.get("template")
    if template_text is not None and (not isinstance(template_text, str) or not template_text.strip()):
        return {"status": "error", "error": "template must be a non-empty string when provided."}, 400

    context_mode = body.get("context_mode", "sample")
    fixture_name = body.get("fixture_name")
    try:
        mode = _resolve_context_mode(context_mode)
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 400

    context, context_source = _context_for_mode(mode, fixture_name=fixture_name)
    if isinstance(template_text, str) and template_text.strip():
        validation = validate_template_text(template_text, context)
        if not validation["valid"]:
            return {
                "status": "error",
                "context_source": context_source if context is not None else None,
                "validation": validation,
            }, 400
    else:
        validation = {"valid": True, "warnings": [], "errors": [], "undeclared_variables": []}

    try:
        updated = update_template_repository_template(
            settings,
            template_id=template_id,
            template_text=template_text,
            name=str(body.get("name")) if body.get("name") is not None else None,
            author=str(body.get("author")) if body.get("author") is not None else None,
            description=str(body.get("description")) if body.get("description") is not None else None,
            source=str(body.get("source") or "editor-repository-save"),
        )
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 400
    return {
        "status": "ok",
        "context_source": context_source if context is not None else None,
        "template_record": updated,
        "validation": validation,
    }, 200


@app.post("/editor/repository/template/<string:template_id>/duplicate")
def editor_repository_template_duplicate_post(template_id: str) -> tuple[dict, int]:
    body = request.get_json(silent=True) or {}
    try:
        duplicated = duplicate_template_repository_template(
            settings,
            template_id=template_id,
            name=str(body.get("name")) if body.get("name") is not None else None,
            author=str(body.get("author")) if body.get("author") is not None else None,
            source=str(body.get("source") or "editor-repository-duplicate"),
        )
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 400
    return {"status": "ok", "template_record": duplicated}, 200


@app.get("/editor/repository/template/<string:template_id>/export")
def editor_repository_template_export_get(template_id: str) -> tuple[dict, int]:
    include_versions_raw = str(request.args.get("include_versions", "false")).strip().lower()
    include_versions = include_versions_raw in {"1", "true", "yes", "on"}
    limit_raw = request.args.get("limit", "30")
    try:
        limit = max(1, min(200, int(limit_raw)))
    except ValueError:
        limit = 30

    try:
        payload = export_template_repository_bundle(
            settings,
            template_id=template_id,
            include_versions=include_versions,
            versions_limit=limit,
        )
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 404
    payload["status"] = "ok"
    return payload, 200


@app.post("/editor/repository/import")
def editor_repository_import_post() -> tuple[dict, int]:
    body = request.get_json(silent=True) or {}
    bundle = body.get("bundle")
    if not isinstance(bundle, dict):
        return {"status": "error", "error": "bundle must be a JSON object."}, 400

    template_text = bundle.get("template")
    if not isinstance(template_text, str) or not template_text.strip():
        return {"status": "error", "error": "bundle.template must be a non-empty string."}, 400

    context_mode = body.get("context_mode", "sample")
    fixture_name = body.get("fixture_name")
    try:
        mode = _resolve_context_mode(context_mode)
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 400

    context, context_source = _context_for_mode(mode, fixture_name=fixture_name)
    validation = validate_template_text(template_text, context)
    if not validation["valid"]:
        return {
            "status": "error",
            "context_source": context_source if context is not None else None,
            "validation": validation,
        }, 400

    try:
        imported = import_template_repository_bundle(
            settings,
            bundle=bundle,
            author=str(body.get("author")) if body.get("author") is not None else None,
            source=str(body.get("source") or "editor-repository-import"),
            name=str(body.get("name")) if body.get("name") is not None else None,
        )
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 400
    return {
        "status": "ok",
        "context_source": context_source if context is not None else None,
        "template_record": imported,
        "validation": validation,
    }, 200


@app.get("/editor/template/version/<string:version_id>")
def editor_template_version_get(version_id: str) -> tuple[dict, int]:
    try:
        profile_id = _resolve_profile_id(request.args.get("profile_id"))
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 400
    record = get_template_version(settings, version_id, profile_id=profile_id)
    if not record:
        return {"status": "error", "error": "Unknown template version."}, 404
    return {"status": "ok", "profile_id": profile_id, "version": record}, 200


@app.post("/editor/template/import")
def editor_template_import_post() -> tuple[dict, int]:
    body = request.get_json(silent=True) or {}
    bundle = body.get("bundle")
    source_payload = bundle if isinstance(bundle, dict) else body

    template_text = source_payload.get("template")
    if not isinstance(template_text, str) or not template_text.strip():
        return {"status": "error", "error": "template must be a non-empty string."}, 400

    try:
        context_mode = _resolve_context_mode(body.get("context_mode"))
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 400

    context, context_source = _context_for_mode(
        context_mode,
        fixture_name=body.get("fixture_name"),
    )
    validation = validate_template_text(template_text, context)
    if not validation["valid"]:
        return {
            "status": "error",
            "context_source": context_source if context is not None else None,
            "validation": validation,
        }, 400

    author = str(body.get("author") or "editor-user")
    source = str(body.get("source") or "editor-import")
    try:
        profile_id = _resolve_profile_id(body.get("profile_id"))
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 400
    name = body.get("name")
    if name is None:
        name = source_payload.get("name")
    notes = body.get("notes")
    if notes is None:
        exported_at = source_payload.get("exported_at_utc")
        if isinstance(exported_at, str) and exported_at.strip():
            notes = f"Imported from bundle exported at {exported_at.strip()}"
    saved = save_active_template(
        settings,
        template_text,
        name=str(name) if name is not None else None,
        author=author,
        source=source,
        notes=str(notes) if notes is not None else None,
        profile_id=profile_id,
    )
    return {
        "status": "ok",
        "profile_id": profile_id,
        "context_source": context_source if context is not None else None,
        "template_path": str(saved.get("path")),
        "saved_version": saved.get("saved_version"),
        "active": saved,
        "validation": validation,
    }, 200


@app.post("/editor/template/rollback")
def editor_template_rollback_post() -> tuple[dict, int]:
    body = request.get_json(silent=True) or {}
    version_id = body.get("version_id")
    if not isinstance(version_id, str) or not version_id.strip():
        return {"status": "error", "error": "version_id is required."}, 400
    author = str(body.get("author") or "editor-user")
    source = str(body.get("source") or "editor-rollback")
    notes = body.get("notes")
    try:
        profile_id = _resolve_profile_id(body.get("profile_id"))
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 400
    try:
        saved = rollback_template_version(
            settings,
            version_id=version_id.strip(),
            author=author,
            source=source,
            notes=str(notes) if notes is not None else None,
            profile_id=profile_id,
        )
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 400
    return {
        "status": "ok",
        "profile_id": profile_id,
        "template_path": saved.get("path"),
        "saved_version": saved.get("saved_version"),
        "active": saved,
    }, 200


@app.get("/editor/snippets")
def editor_snippets_get() -> tuple[dict, int]:
    return {
        "status": "ok",
        "snippets": get_editor_snippets(),
        "context_modes": ["latest", "sample", "latest_or_sample", "fixture"],
    }, 200


@app.get("/editor/starter-templates")
def editor_starter_templates_get() -> tuple[dict, int]:
    templates = get_starter_templates()
    return {
        "status": "ok",
        "starter_templates": templates,
        "count": len(templates),
    }, 200


@app.get("/editor/context/sample")
def editor_sample_context_get() -> tuple[dict, int]:
    context = get_sample_template_context(request.args.get("fixture"))
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

    try:
        context_mode = _resolve_context_mode(body.get("context_mode", "latest_or_sample"))
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 400

    context, context_source = _context_for_mode(
        context_mode,
        fixture_name=body.get("fixture_name"),
    )
    validation = validate_template_text(template_text, context)
    if not validation["valid"]:
        return {
            "status": "error",
            "context_source": context_source if context is not None else None,
            "validation": validation,
        }, 400

    author = str(body.get("author") or "editor-user")
    source = str(body.get("source") or "editor-ui")
    try:
        profile_id = _resolve_profile_id(body.get("profile_id"))
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 400
    name = body.get("name")
    notes = body.get("notes")
    saved = save_active_template(
        settings,
        template_text,
        name=str(name) if name is not None else None,
        author=author,
        source=source,
        notes=str(notes) if notes is not None else None,
        profile_id=profile_id,
    )
    return {
        "status": "ok",
        "profile_id": profile_id,
        "context_source": context_source if context is not None else None,
        "template_path": str(saved.get("path")),
        "saved_version": saved.get("saved_version"),
        "active": saved,
        "validation": validation,
    }, 200


@app.post("/editor/validate")
def editor_validate() -> tuple[dict, int]:
    body = request.get_json(silent=True) or {}
    template_text = body.get("template")
    try:
        profile_id = _resolve_profile_id(body.get("profile_id"))
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 400
    if template_text is None:
        template_text = get_active_template(settings, profile_id=profile_id)["template"]
    if not isinstance(template_text, str):
        return {"status": "error", "error": "template must be a string."}, 400

    try:
        context_mode = _resolve_context_mode(body.get("context_mode"))
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 400

    context, context_source = _context_for_mode(
        context_mode,
        fixture_name=body.get("fixture_name"),
    )
    validation = validate_template_text(template_text, context)
    return {
        "status": "ok" if validation["valid"] else "error",
        "profile_id": profile_id,
        "has_context": context is not None,
        "context_source": context_source if context is not None else None,
        "validation": validation,
    }, 200 if validation["valid"] else 400


@app.post("/editor/preview")
def editor_preview() -> tuple[dict, int]:
    body = request.get_json(silent=True) or {}
    template_text = body.get("template")
    try:
        profile_id = _resolve_profile_id(body.get("profile_id"))
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 400
    if template_text is None:
        template_text = get_active_template(settings, profile_id=profile_id)["template"]
    if not isinstance(template_text, str):
        return {"status": "error", "error": "template must be a string."}, 400

    try:
        context_mode = _resolve_context_mode(body.get("context_mode"))
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 400

    context, context_source = _context_for_mode(
        context_mode,
        fixture_name=body.get("fixture_name"),
    )
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
        "profile_id": profile_id,
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

    context, context_source = _context_for_mode(
        context_mode,
        fixture_name=request.args.get("fixture_name"),
    )
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


@app.get("/editor/catalog")
def editor_catalog() -> tuple[dict, int]:
    raw_mode = request.args.get("context_mode")
    try:
        context_mode = _resolve_context_mode(raw_mode)
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}, 400

    fixture_name = request.args.get("fixture_name")
    context, context_source = _context_for_mode(
        context_mode,
        fixture_name=fixture_name,
    )
    if context is None:
        schema = build_context_schema({})
        return {
            "status": "ok",
            "has_context": False,
            "context_source": None,
            "catalog": schema,
            "fixtures": list_sample_template_fixtures(),
            "context_modes": ["latest", "sample", "latest_or_sample", "fixture"],
        }, 200

    schema = build_context_schema(context)
    return {
        "status": "ok",
        "has_context": True,
        "context_source": context_source,
        "catalog": schema,
        "fixtures": list_sample_template_fixtures(),
        "context_modes": ["latest", "sample", "latest_or_sample", "fixture"],
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
