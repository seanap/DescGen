from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from datetime import datetime, timezone

from .setup_config import read_setup_overrides_payload

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - fallback for minimal environments
    def load_dotenv() -> None:
        return None


load_dotenv()

PROCESS_STARTED_UTC = datetime.now(timezone.utc)


EnvGetter = Callable[[str], str | None]


def _bool_env(name: str, default: bool, *, getenv: EnvGetter = os.getenv) -> bool:
    value = getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _str_env(*names: str, default: str = "", getenv: EnvGetter = os.getenv) -> str:
    for name in names:
        value = getenv(name)
        if value is not None:
            return value.strip()
    return default


def _optional_str_env(*names: str, getenv: EnvGetter = os.getenv) -> str | None:
    value = _str_env(*names, default="", getenv=getenv)
    return value or None


def _hour_env(name: str, default: int, *, getenv: EnvGetter = os.getenv) -> int:
    value = getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value.strip())
    except ValueError:
        return default
    if 0 <= parsed <= 23:
        return parsed
    return default


def _int_env(
    name: str,
    default: int,
    minimum: int | None = None,
    maximum: int | None = None,
    *,
    getenv: EnvGetter = os.getenv,
) -> int:
    value = getenv(name)
    if value is None:
        parsed = default
    else:
        try:
            parsed = int(value.strip())
        except ValueError:
            parsed = default

    if minimum is not None and parsed < minimum:
        parsed = minimum
    if maximum is not None and parsed > maximum:
        parsed = maximum
    return parsed


def _float_env(
    name: str,
    default: float,
    minimum: float | None = None,
    maximum: float | None = None,
    *,
    getenv: EnvGetter = os.getenv,
) -> float:
    value = getenv(name)
    if value is None:
        parsed = default
    else:
        try:
            parsed = float(value.strip())
        except ValueError:
            parsed = default

    if minimum is not None and parsed < minimum:
        parsed = minimum
    if maximum is not None and parsed > maximum:
        parsed = maximum
    return parsed


def _optional_float_env(name: str, *, getenv: EnvGetter = os.getenv) -> float | None:
    value = getenv(name)
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_utc(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class Settings:
    strava_client_id: str
    strava_client_secret: str
    strava_refresh_token: str
    strava_access_token: str | None

    garmin_email: str | None
    garmin_password: str | None

    intervals_api_key: str | None
    intervals_user_id: str | None
    weather_api_key: str | None
    smashrun_access_token: str | None
    crono_api_base_url: str | None
    crono_api_key: str | None

    poll_interval_seconds: int
    log_level: str
    timezone: str
    api_port: int
    api_workers: int
    api_threads: int
    api_timeout_seconds: int
    worker_health_max_age_seconds: int
    run_lock_ttl_seconds: int
    service_retry_count: int
    service_retry_backoff_seconds: int
    service_cooldown_base_seconds: int
    service_cooldown_max_seconds: int
    enable_service_call_budget: bool
    max_optional_service_calls_per_cycle: int
    enable_service_result_cache: bool
    service_cache_ttl_seconds: int

    state_dir: Path
    processed_log_file: Path
    latest_json_file: Path
    strava_token_file: Path
    description_template_file: Path
    runtime_db_file: Path

    enable_garmin: bool
    enable_intervals: bool
    enable_weather: bool
    enable_smashrun: bool
    enable_crono_api: bool
    enable_quiet_hours: bool
    quiet_hours_start_hour: int
    quiet_hours_end_hour: int
    profile_long_run_miles: float
    profile_trail_gain_per_mile_ft: float
    home_latitude: float | None
    home_longitude: float | None
    home_radius_miles: float

    @classmethod
    def from_env(cls) -> "Settings":
        state_dir = Path(os.getenv("STATE_DIR", "state")).resolve()
        setup_overrides_payload = read_setup_overrides_payload(state_dir)
        setup_overrides_raw = setup_overrides_payload.get("values")
        setup_overrides = setup_overrides_raw if isinstance(setup_overrides_raw, dict) else {}
        overrides_updated_at = _parse_utc(setup_overrides_payload.get("updated_at_utc"))
        overrides_live = bool(overrides_updated_at and overrides_updated_at > PROCESS_STARTED_UTC)

        def env_with_setup_overrides(name: str) -> str | None:
            if overrides_live and name in setup_overrides:
                overridden = setup_overrides[name]
                if isinstance(overridden, bool):
                    return "true" if overridden else "false"
                return str(overridden)
            return os.getenv(name)

        processed_log_file = state_dir / os.getenv(
            "PROCESSED_LOG_FILE", "processed_activities.log"
        )
        latest_json_file = state_dir / os.getenv(
            "LATEST_JSON_FILE", "latest_activity.json"
        )
        strava_token_file = state_dir / os.getenv("STRAVA_TOKEN_FILE", "strava_tokens.json")
        description_template_file = state_dir / os.getenv(
            "DESCRIPTION_TEMPLATE_FILE",
            "description_template.j2",
        )
        runtime_db_file = state_dir / os.getenv("RUNTIME_DB_FILE", "runtime_state.db")

        poll_interval_raw = os.getenv("POLL_INTERVAL_SECONDS", "300")
        try:
            poll_interval_seconds = max(60, int(poll_interval_raw))
        except ValueError:
            poll_interval_seconds = 300

        api_port = _int_env("API_PORT", 1609, minimum=1, maximum=65535)

        return cls(
            strava_client_id=_str_env(
                "STRAVA_CLIENT_ID", "CLIENT_ID", getenv=env_with_setup_overrides
            ),
            strava_client_secret=_str_env(
                "STRAVA_CLIENT_SECRET", "CLIENT_SECRET", getenv=env_with_setup_overrides
            ),
            strava_refresh_token=_str_env(
                "STRAVA_REFRESH_TOKEN", "REFRESH_TOKEN", getenv=env_with_setup_overrides
            ),
            strava_access_token=_optional_str_env(
                "STRAVA_ACCESS_TOKEN", "ACCESS_TOKEN", getenv=env_with_setup_overrides
            ),
            garmin_email=_optional_str_env("GARMIN_EMAIL", getenv=env_with_setup_overrides),
            garmin_password=_optional_str_env("GARMIN_PASSWORD", getenv=env_with_setup_overrides),
            intervals_api_key=_optional_str_env("INTERVALS_API_KEY", getenv=env_with_setup_overrides),
            intervals_user_id=_optional_str_env(
                "INTERVALS_USER_ID", "USER_ID", getenv=env_with_setup_overrides
            ),
            weather_api_key=_optional_str_env("WEATHER_API_KEY", getenv=env_with_setup_overrides),
            smashrun_access_token=_optional_str_env(
                "SMASHRUN_ACCESS_TOKEN", getenv=env_with_setup_overrides
            ),
            crono_api_base_url=_optional_str_env(
                "CRONO_API_BASE_URL", getenv=env_with_setup_overrides
            ),
            crono_api_key=_optional_str_env("CRONO_API_KEY", getenv=env_with_setup_overrides),
            poll_interval_seconds=poll_interval_seconds,
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            timezone=_str_env("TIMEZONE", "TZ", default="UTC", getenv=env_with_setup_overrides),
            api_port=api_port,
            api_workers=_int_env("API_WORKERS", 2, minimum=1, maximum=8),
            api_threads=_int_env("API_THREADS", 4, minimum=1, maximum=32),
            api_timeout_seconds=_int_env("API_TIMEOUT_SECONDS", 120, minimum=30, maximum=600),
            worker_health_max_age_seconds=_int_env("WORKER_HEALTH_MAX_AGE_SECONDS", 900, minimum=60, maximum=86400),
            run_lock_ttl_seconds=_int_env("RUN_LOCK_TTL_SECONDS", 900, minimum=30, maximum=7200),
            service_retry_count=_int_env("SERVICE_RETRY_COUNT", 2, minimum=0, maximum=5),
            service_retry_backoff_seconds=_int_env("SERVICE_RETRY_BACKOFF_SECONDS", 2, minimum=1, maximum=120),
            service_cooldown_base_seconds=_int_env("SERVICE_COOLDOWN_BASE_SECONDS", 60, minimum=5, maximum=3600),
            service_cooldown_max_seconds=_int_env("SERVICE_COOLDOWN_MAX_SECONDS", 1800, minimum=30, maximum=86400),
            enable_service_call_budget=_bool_env("ENABLE_SERVICE_CALL_BUDGET", True),
            max_optional_service_calls_per_cycle=_int_env("MAX_OPTIONAL_SERVICE_CALLS_PER_CYCLE", 10, minimum=0, maximum=50),
            enable_service_result_cache=_bool_env("ENABLE_SERVICE_RESULT_CACHE", True),
            service_cache_ttl_seconds=_int_env("SERVICE_CACHE_TTL_SECONDS", 600, minimum=0, maximum=86400),
            state_dir=state_dir,
            processed_log_file=processed_log_file,
            latest_json_file=latest_json_file,
            strava_token_file=strava_token_file,
            description_template_file=description_template_file,
            runtime_db_file=runtime_db_file,
            enable_garmin=_bool_env("ENABLE_GARMIN", True, getenv=env_with_setup_overrides),
            enable_intervals=_bool_env("ENABLE_INTERVALS", True, getenv=env_with_setup_overrides),
            enable_weather=_bool_env("ENABLE_WEATHER", True, getenv=env_with_setup_overrides),
            enable_smashrun=_bool_env("ENABLE_SMASHRUN", True, getenv=env_with_setup_overrides),
            enable_crono_api=_bool_env("ENABLE_CRONO_API", False, getenv=env_with_setup_overrides),
            enable_quiet_hours=_bool_env("ENABLE_QUIET_HOURS", True),
            quiet_hours_start_hour=_hour_env("QUIET_HOURS_START", 0),
            quiet_hours_end_hour=_hour_env("QUIET_HOURS_END", 4),
            profile_long_run_miles=_float_env("PROFILE_LONG_RUN_MILES", 10.0, minimum=1.0, maximum=100.0),
            profile_trail_gain_per_mile_ft=_float_env("PROFILE_TRAIL_GAIN_PER_MILE_FT", 220.0, minimum=10.0, maximum=5000.0),
            home_latitude=_optional_float_env("HOME_LAT"),
            home_longitude=_optional_float_env("HOME_LON"),
            home_radius_miles=_float_env("HOME_RADIUS_MILES", 8.0, minimum=0.1, maximum=250.0),
        )

    def validate(self) -> None:
        missing = []
        if not self.strava_client_id:
            missing.append("STRAVA_CLIENT_ID (or CLIENT_ID)")
        if not self.strava_client_secret:
            missing.append("STRAVA_CLIENT_SECRET (or CLIENT_SECRET)")
        if not self.strava_refresh_token:
            missing.append("STRAVA_REFRESH_TOKEN (or REFRESH_TOKEN)")
        if missing:
            missing_str = ", ".join(missing)
            raise ValueError(f"Missing required environment variables: {missing_str}")

    def ensure_state_paths(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
