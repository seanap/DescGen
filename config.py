from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - fallback for minimal environments
    def load_dotenv() -> None:
        return None


load_dotenv()


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _hour_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value.strip())
    except ValueError:
        return default
    if 0 <= parsed <= 23:
        return parsed
    return default


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

    state_dir: Path
    processed_log_file: Path
    latest_json_file: Path
    strava_token_file: Path

    enable_garmin: bool
    enable_intervals: bool
    enable_weather: bool
    enable_smashrun: bool
    enable_crono_api: bool
    enable_quiet_hours: bool
    quiet_hours_start_hour: int
    quiet_hours_end_hour: int

    @classmethod
    def from_env(cls) -> "Settings":
        state_dir = Path(os.getenv("STATE_DIR", "state")).resolve()
        processed_log_file = state_dir / os.getenv(
            "PROCESSED_LOG_FILE", "processed_activities.log"
        )
        latest_json_file = state_dir / os.getenv(
            "LATEST_JSON_FILE", "latest_activity.json"
        )
        strava_token_file = state_dir / os.getenv("STRAVA_TOKEN_FILE", "strava_tokens.json")

        poll_interval_raw = os.getenv("POLL_INTERVAL_SECONDS", "300")
        try:
            poll_interval_seconds = max(60, int(poll_interval_raw))
        except ValueError:
            poll_interval_seconds = 300

        api_port_raw = os.getenv("API_PORT", "1609")
        try:
            api_port = int(api_port_raw)
            if not (1 <= api_port <= 65535):
                api_port = 1609
        except ValueError:
            api_port = 1609

        return cls(
            strava_client_id=os.getenv("CLIENT_ID", "").strip(),
            strava_client_secret=os.getenv("CLIENT_SECRET", "").strip(),
            strava_refresh_token=os.getenv("REFRESH_TOKEN", "").strip(),
            strava_access_token=os.getenv("ACCESS_TOKEN", "").strip() or None,
            garmin_email=os.getenv("GARMIN_EMAIL", "").strip() or None,
            garmin_password=os.getenv("GARMIN_PASSWORD", "").strip() or None,
            intervals_api_key=os.getenv("INTERVALS_API_KEY", "").strip() or None,
            intervals_user_id=os.getenv("USER_ID", "").strip() or None,
            weather_api_key=os.getenv("WEATHER_API_KEY", "").strip() or None,
            smashrun_access_token=os.getenv("SMASHRUN_ACCESS_TOKEN", "").strip() or None,
            crono_api_base_url=os.getenv("CRONO_API_BASE_URL", "").strip() or None,
            crono_api_key=os.getenv("CRONO_API_KEY", "").strip() or None,
            poll_interval_seconds=poll_interval_seconds,
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            timezone=os.getenv("TZ", "UTC"),
            api_port=api_port,
            state_dir=state_dir,
            processed_log_file=processed_log_file,
            latest_json_file=latest_json_file,
            strava_token_file=strava_token_file,
            enable_garmin=_bool_env("ENABLE_GARMIN", True),
            enable_intervals=_bool_env("ENABLE_INTERVALS", True),
            enable_weather=_bool_env("ENABLE_WEATHER", True),
            enable_smashrun=_bool_env("ENABLE_SMASHRUN", True),
            enable_crono_api=_bool_env("ENABLE_CRONO_API", False),
            enable_quiet_hours=_bool_env("ENABLE_QUIET_HOURS", True),
            quiet_hours_start_hour=_hour_env("QUIET_HOURS_START", 0),
            quiet_hours_end_hour=_hour_env("QUIET_HOURS_END", 4),
        )

    def validate(self) -> None:
        missing = []
        if not self.strava_client_id:
            missing.append("CLIENT_ID")
        if not self.strava_client_secret:
            missing.append("CLIENT_SECRET")
        if not self.strava_refresh_token:
            missing.append("REFRESH_TOKEN")
        if missing:
            missing_str = ", ".join(missing)
            raise ValueError(f"Missing required environment variables: {missing_str}")

    def ensure_state_paths(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
