from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config import Settings
from main_strava_update import run_once


logger = logging.getLogger(__name__)


def _in_quiet_hours(hour: int, start_hour: int, end_hour: int) -> bool:
    if start_hour == end_hour:
        return False
    if start_hour < end_hour:
        return start_hour <= hour < end_hour
    return hour >= start_hour or hour < end_hour


def _seconds_until_quiet_end(
    now_local: datetime, start_hour: int, end_hour: int
) -> int:
    if not _in_quiet_hours(now_local.hour, start_hour, end_hour):
        return 0

    quiet_end = now_local.replace(
        hour=end_hour,
        minute=0,
        second=0,
        microsecond=0,
    )

    if start_hour < end_hour:
        if now_local >= quiet_end:
            quiet_end += timedelta(days=1)
    else:
        if now_local.hour >= start_hour:
            quiet_end += timedelta(days=1)

    delta = int((quiet_end - now_local).total_seconds())
    return max(60, delta)


def main() -> None:
    settings = Settings.from_env()
    settings.ensure_state_paths()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    interval = settings.poll_interval_seconds
    try:
        local_tz = ZoneInfo(settings.timezone)
    except ZoneInfoNotFoundError:
        logger.warning("Unknown timezone '%s'. Falling back to UTC.", settings.timezone)
        local_tz = ZoneInfo("UTC")

    logger.info("Worker started with poll interval: %ss", interval)
    if settings.enable_quiet_hours:
        logger.info(
            "Quiet hours enabled: %02d:00-%02d:00 (%s)",
            settings.quiet_hours_start_hour,
            settings.quiet_hours_end_hour,
            local_tz,
        )

    while True:
        now_local = datetime.now(local_tz)
        if settings.enable_quiet_hours and _in_quiet_hours(
            now_local.hour,
            settings.quiet_hours_start_hour,
            settings.quiet_hours_end_hour,
        ):
            sleep_seconds = _seconds_until_quiet_end(
                now_local,
                settings.quiet_hours_start_hour,
                settings.quiet_hours_end_hour,
            )
            logger.info(
                "In quiet hours at %s, sleeping for %ss",
                now_local.isoformat(timespec="seconds"),
                sleep_seconds,
            )
            time.sleep(sleep_seconds)
            continue

        try:
            result = run_once(force_update=False)
            logger.info("Cycle result: %s", result)
        except Exception:
            logger.exception("Worker cycle failed.")
        time.sleep(interval)


if __name__ == "__main__":
    main()
