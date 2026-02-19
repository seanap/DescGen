from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests
from flask import Flask, render_template, request

from activity_pipeline import run_once
from config import Settings
from dashboard_data import get_dashboard_payload
from setup_config import (
    PROVIDER_FIELDS,
    PROVIDER_LINKS,
    SETUP_ALLOWED_KEYS,
    SETUP_SECRET_KEYS,
    mask_setup_values,
    merge_setup_overrides,
    render_env_snippet,
    setup_env_file_path,
    update_setup_env_file,
)
from storage import (
    delete_runtime_value,
    get_runtime_value,
    get_worker_heartbeat,
    is_worker_healthy,
    read_json,
    set_runtime_value,
    write_json,
)
from template_profiles import (
    get_template_profile,
    get_working_template_profile,
    list_template_profiles,
    set_working_template_profile,
    update_template_profile,
)
from template_repository import (
    create_template_repository_template,
    duplicate_template_repository_template,
    export_template_repository_bundle,
    get_active_template,
    get_default_template,
    get_editor_snippets,
    get_sample_template_context,
    get_starter_templates,
    get_template_repository_template,
    get_template_version,
    import_template_repository_bundle,
    list_sample_template_fixtures,
    list_template_repository_templates,
    list_template_versions,
    rollback_template_version,
    save_active_template,
    update_template_repository_template,
)
from template_rendering import normalize_template_context, render_template_text, validate_template_text
from template_schema import build_context_schema


app = Flask(__name__)
settings = Settings.from_env()
settings.ensure_state_paths()

STRAVA_OAUTH_SCOPE = "read,activity:read_all,activity:write"
STRAVA_OAUTH_RUNTIME_KEY = "setup.strava.oauth"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"


def _effective_settings() -> Settings:
    current = Settings.from_env()
    current.ensure_state_paths()
    return current


def _setup_effective_values() -> dict[str, object]:
    current = _effective_settings()
    values: dict[str, object] = {
        "STRAVA_CLIENT_ID": current.strava_client_id,
        "STRAVA_CLIENT_SECRET": current.strava_client_secret,
        "STRAVA_REFRESH_TOKEN": current.strava_refresh_token,
        "STRAVA_ACCESS_TOKEN": current.strava_access_token or "",
        "ENABLE_GARMIN": current.enable_garmin,
        "GARMIN_EMAIL": current.garmin_email or "",
        "GARMIN_PASSWORD": current.garmin_password or "",
        "ENABLE_INTERVALS": current.enable_intervals,
        "INTERVALS_API_KEY": current.intervals_api_key or "",
        "INTERVALS_USER_ID": current.intervals_user_id or "",
        "ENABLE_WEATHER": current.enable_weather,
        "WEATHER_API_KEY": current.weather_api_key or "",
        "ENABLE_SMASHRUN": current.enable_smashrun,
        "SMASHRUN_ACCESS_TOKEN": current.smashrun_access_token or "",
        "ENABLE_CRONO_API": current.enable_crono_api,
        "CRONO_API_BASE_URL": current.crono_api_base_url or "",
        "CRONO_API_KEY": current.crono_api_key or "",
        "TIMEZONE": current.timezone,
    }

    cached_tokens = read_json(current.strava_token_file) or {}
    cached_refresh = cached_tokens.get("refresh_token")
    if (
        isinstance(cached_refresh, str)
        and cached_refresh.strip()
        and not str(values.get("STRAVA_REFRESH_TOKEN") or "").strip()
    ):
        values["STRAVA_REFRESH_TOKEN"] = cached_refresh.strip()
    cached_access = cached_tokens.get("access_token")
    if (
        isinstance(cached_access, str)
        and cached_access.strip()
        and not str(values.get("STRAVA_ACCESS_TOKEN") or "").strip()
    ):
        values["STRAVA_ACCESS_TOKEN"] = cached_access.strip()

    return values


def _setup_strava_status(values: dict[str, object]) -> dict[str, object]:
    client_id = str(values.get("STRAVA_CLIENT_ID") or "").strip()
    client_secret = str(values.get("STRAVA_CLIENT_SECRET") or "").strip()
    refresh_token = str(values.get("STRAVA_REFRESH_TOKEN") or "").strip()
    access_token = str(values.get("STRAVA_ACCESS_TOKEN") or "").strip()
    return {
        "client_configured": bool(client_id and client_secret),
        "connected": bool(refresh_token),
        "has_refresh_token": bool(refresh_token),
        "has_access_token": bool(access_token),
    }


def _public_setup_values(values: dict[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key in SETUP_ALLOWED_KEYS:
        value = values.get(key)
        if key in SETUP_SECRET_KEYS:
            result[key] = ""
            continue
        if value is None:
            result[key] = ""
            continue
        result[key] = value
    return result


def _setup_payload() -> dict[str, object]:
    values = _setup_effective_values()
    masked_values = mask_setup_values(values)
    secret_presence = {
        key: bool(str(values.get(key) or "").strip())
        for key in sorted(SETUP_SECRET_KEYS)
    }
    provider_fields = {
        provider: fields
        for provider, fields in PROVIDER_FIELDS.items()
    }
    env_path = setup_env_file_path()
    env_writable = os.access(env_path, os.W_OK) if env_path.exists() else os.access(env_path.parent, os.W_OK)
    return {
        "status": "ok",
        "values": _public_setup_values(values),
        "masked_values": masked_values,
        "secret_presence": secret_presence,
        "provider_links": PROVIDER_LINKS,
        "provider_fields": provider_fields,
        "allowed_keys": sorted(SETUP_ALLOWED_KEYS),
        "secret_keys": sorted(SETUP_SECRET_KEYS),
        "strava": _setup_strava_status(values),
        "env_file": {
            "path": str(env_path),
            "exists": env_path.exists(),
            "writable": bool(env_writable),
        },
    }


def _default_setup_callback_url() -> str:
    return request.url_root.rstrip("/") + "/setup/strava/callback"


def _redirect_setup_with_status(status: str, reason: str = ""):
    params = {"strava_oauth": status}
    if reason:
        params["reason"] = reason
    return app.redirect_class(f"/setup?{urlencode(params)}", 302)


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

    ready_ok = (
        checks["state_path_writable"]
        and checks["template_accessible"]
        and checks["worker_heartbeat_healthy"]
    )
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


@app.get("/setup")
def setup_page() -> str:
    return render_template("setup.html")


@app.get("/dashboard")
def dashboard_page() -> str:
    return render_template("dashboard.html")


@app.get("/dashboard/data.json")
def dashboard_data_get() -> tuple[dict, int]:
    force_refresh = str(request.args.get("force") or "").strip().lower() in {"1", "true", "yes", "on"}
    current = _effective_settings()
    try:
        payload = get_dashboard_payload(current, force_refresh=force_refresh)
    except Exception as exc:
        return {"status": "error", "error": f"Failed to build dashboard payload: {exc}"}, 500
    return payload, 200


@app.get("/setup/api/config")
def setup_config_get() -> tuple[dict, int]:
    return _setup_payload(), 200


@app.put("/setup/api/config")
def setup_config_put() -> tuple[dict, int]:
    body = request.get_json(silent=True) or {}
    values = body.get("values", body)
    if not isinstance(values, dict):
        return {"status": "error", "error": "values must be a JSON object."}, 400

    updates: dict[str, object] = {}
    for key, value in values.items():
        if key not in SETUP_ALLOWED_KEYS:
            continue
        if key in SETUP_SECRET_KEYS and isinstance(value, str) and not value.strip():
            # Empty secret input means "keep existing secret".
            continue
        updates[key] = value

    try:
        env_path = update_setup_env_file(updates)
    except OSError as exc:
        return {
            "status": "error",
            "error": f"Failed to write env file at {setup_env_file_path()}: {exc}",
        }, 500

    merge_setup_overrides(settings.state_dir, updates)
    payload = _setup_payload()
    payload["env_write_path"] = str(env_path)
    return payload, 200


@app.get("/setup/api/env")
def setup_env_get() -> tuple[dict, int]:
    values = _setup_effective_values()
    filtered: dict[str, object] = {}
    for key in sorted(SETUP_ALLOWED_KEYS):
        value = values.get(key)
        if isinstance(value, bool):
            filtered[key] = value
        elif isinstance(value, str):
            text = value.strip()
            if text:
                filtered[key] = text
    return {
        "status": "ok",
        "env": render_env_snippet(filtered),
    }, 200


@app.get("/setup/api/strava/status")
def setup_strava_status_get() -> tuple[dict, int]:
    values = _setup_effective_values()
    return {
        "status": "ok",
        "strava": _setup_strava_status(values),
    }, 200


@app.post("/setup/api/strava/oauth/start")
def setup_strava_oauth_start_post() -> tuple[dict, int]:
    values = _setup_effective_values()
    client_id = str(values.get("STRAVA_CLIENT_ID") or "").strip()
    client_secret = str(values.get("STRAVA_CLIENT_SECRET") or "").strip()
    if not client_id or not client_secret:
        return {
            "status": "error",
            "error": "Set STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET before starting OAuth.",
        }, 400

    body = request.get_json(silent=True) or {}
    redirect_uri = body.get("redirect_uri")
    if not isinstance(redirect_uri, str) or not redirect_uri.strip():
        redirect_uri = _default_setup_callback_url()
    redirect_uri = redirect_uri.strip()

    state_token = secrets.token_urlsafe(24)
    set_runtime_value(
        settings.processed_log_file,
        STRAVA_OAUTH_RUNTIME_KEY,
        {
            "state": state_token,
            "redirect_uri": redirect_uri,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    )

    authorize_url = (
        f"{STRAVA_AUTHORIZE_URL}?"
        f"{urlencode({'client_id': client_id, 'response_type': 'code', 'redirect_uri': redirect_uri, 'approval_prompt': 'force', 'scope': STRAVA_OAUTH_SCOPE, 'state': state_token})}"
    )
    return {
        "status": "ok",
        "authorize_url": authorize_url,
        "state": state_token,
        "redirect_uri": redirect_uri,
    }, 200


@app.get("/setup/strava/callback")
def setup_strava_oauth_callback_get():
    error = str(request.args.get("error") or "").strip()
    if error:
        return _redirect_setup_with_status("error", error)

    code = str(request.args.get("code") or "").strip()
    state_token = str(request.args.get("state") or "").strip()
    runtime_state = get_runtime_value(settings.processed_log_file, STRAVA_OAUTH_RUNTIME_KEY, {})
    saved_state = str(runtime_state.get("state") or "").strip() if isinstance(runtime_state, dict) else ""
    redirect_uri = (
        str(runtime_state.get("redirect_uri") or "").strip()
        if isinstance(runtime_state, dict)
        else ""
    )
    if not redirect_uri:
        redirect_uri = _default_setup_callback_url()

    if not code:
        return _redirect_setup_with_status("error", "missing_code")
    if not state_token or state_token != saved_state:
        return _redirect_setup_with_status("error", "state_mismatch")

    values = _setup_effective_values()
    client_id = str(values.get("STRAVA_CLIENT_ID") or "").strip()
    client_secret = str(values.get("STRAVA_CLIENT_SECRET") or "").strip()
    if not client_id or not client_secret:
        return _redirect_setup_with_status("error", "missing_client_credentials")

    try:
        response = requests.post(
            STRAVA_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException:
        return _redirect_setup_with_status("error", "token_exchange_failed")

    refresh_token = payload.get("refresh_token")
    access_token = payload.get("access_token")
    if not isinstance(refresh_token, str) or not refresh_token.strip():
        return _redirect_setup_with_status("error", "missing_refresh_token")
    if not isinstance(access_token, str) or not access_token.strip():
        return _redirect_setup_with_status("error", "missing_access_token")

    try:
        update_setup_env_file(
            {
                "STRAVA_REFRESH_TOKEN": refresh_token.strip(),
                "STRAVA_ACCESS_TOKEN": access_token.strip(),
            }
        )
    except OSError:
        return _redirect_setup_with_status("error", "env_write_failed")

    merge_setup_overrides(
        settings.state_dir,
        {
            "STRAVA_REFRESH_TOKEN": refresh_token.strip(),
            "STRAVA_ACCESS_TOKEN": access_token.strip(),
        },
    )

    current = _effective_settings()
    write_json(
        current.strava_token_file,
        {
            "access_token": access_token.strip(),
            "refresh_token": refresh_token.strip(),
        },
    )
    delete_runtime_value(settings.processed_log_file, STRAVA_OAUTH_RUNTIME_KEY)
    return _redirect_setup_with_status("connected")


@app.post("/setup/api/strava/disconnect")
def setup_strava_disconnect_post() -> tuple[dict, int]:
    try:
        update_setup_env_file(
            {
                "STRAVA_REFRESH_TOKEN": None,
                "STRAVA_ACCESS_TOKEN": None,
            }
        )
    except OSError as exc:
        return {
            "status": "error",
            "error": f"Failed to update env file at {setup_env_file_path()}: {exc}",
        }, 500

    merge_setup_overrides(
        settings.state_dir,
        {
            "STRAVA_REFRESH_TOKEN": None,
            "STRAVA_ACCESS_TOKEN": None,
        },
    )
    current = _effective_settings()
    current.strava_token_file.unlink(missing_ok=True)

    return {
        "status": "ok",
        "strava": _setup_strava_status(_setup_effective_values()),
        "env_write_path": str(setup_env_file_path()),
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


def _run_rerun(force_update: bool, activity_id: int | None = None) -> tuple[dict, int]:
    try:
        if activity_id is None:
            result = run_once(force_update=force_update)
        else:
            result = run_once(force_update=force_update, activity_id=activity_id)

        response: dict[str, object] = {"status": "ok", "result": result}
        if isinstance(result, dict) and str(result.get("status") or "").strip().lower() == "updated":
            try:
                get_dashboard_payload(_effective_settings(), force_refresh=True)
                response["dashboard_refresh"] = "updated"
            except Exception as exc:
                response["dashboard_refresh"] = f"error: {exc}"
        return response, 200
    except Exception as exc:
        return {"status": "error", "error": str(exc)}, 500


@app.post("/rerun/latest")
def rerun_latest() -> tuple[dict, int]:
    return _run_rerun(force_update=True)


@app.post("/rerun/activity/<int:activity_id>")
def rerun_activity(activity_id: int) -> tuple[dict, int]:
    return _run_rerun(force_update=True, activity_id=activity_id)


@app.post("/rerun")
def rerun() -> tuple[dict, int]:
    body = request.get_json(silent=True) or {}
    activity_id = body.get("activity_id")
    if activity_id is None:
        return _run_rerun(force_update=True)

    try:
        activity_id_int = int(activity_id)
    except (TypeError, ValueError):
        return {"status": "error", "error": "activity_id must be an integer."}, 400

    return _run_rerun(force_update=True, activity_id=activity_id_int)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.api_port)
