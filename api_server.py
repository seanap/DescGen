from __future__ import annotations

from datetime import datetime, timezone

from flask import Flask, request

from main_strava_update import run_once

from config import Settings
from storage import read_json


app = Flask(__name__)
settings = Settings.from_env()
settings.ensure_state_paths()


@app.get("/health")
def health() -> tuple[dict, int]:
    payload = read_json(settings.latest_json_file)
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
    payload = read_json(settings.latest_json_file)
    if payload is None:
        return {"error": "No activity payload has been written yet."}, 404
    return payload, 200


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
