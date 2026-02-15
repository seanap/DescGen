from __future__ import annotations

import logging
from datetime import datetime

from config import Settings


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fetch_resting_hr(target_date: str | None = None) -> int | str:
    settings = Settings.from_env()
    if not settings.garmin_email or not settings.garmin_password:
        return "N/A"

    date_string = target_date or datetime.now().strftime("%Y-%m-%d")

    try:
        from garminconnect import Garmin

        client = Garmin(settings.garmin_email, settings.garmin_password)
        client.login()
        payload = client.get_rhr_day(date_string)
        return (
            payload.get("allMetrics", {})
            .get("metricsMap", {})
            .get("WELLNESS_RESTING_HEART_RATE", [{}])[0]
            .get("value", "N/A")
        )
    except Exception as exc:
        logger.error("Failed to fetch resting HR: %s", exc)
        return "N/A"


if __name__ == "__main__":
    print(fetch_resting_hr())
