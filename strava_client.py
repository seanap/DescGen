from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import requests

from config import Settings
from storage import read_json, write_json


logger = logging.getLogger(__name__)

BASE_URL = "https://www.strava.com"
API_URL = f"{BASE_URL}/api/v3"
TIMEOUT_SECONDS = 30
MAX_ACTIVITY_PAGES = 60


class StravaClient:
    def __init__(self, settings: Settings):
        self.client_id = settings.strava_client_id
        self.client_secret = settings.strava_client_secret
        self.refresh_token = settings.strava_refresh_token
        self.access_token = settings.strava_access_token
        self.token_file = settings.strava_token_file
        self.session = requests.Session()
        self._load_tokens_from_cache()

    def _load_tokens_from_cache(self) -> None:
        cached = read_json(self.token_file)
        if not cached:
            return
        cached_access = cached.get("access_token")
        cached_refresh = cached.get("refresh_token")
        if isinstance(cached_access, str) and cached_access.strip():
            self.access_token = cached_access.strip()
        if isinstance(cached_refresh, str) and cached_refresh.strip():
            self.refresh_token = cached_refresh.strip()

    def _save_tokens_to_cache(self) -> None:
        if not self.access_token or not self.refresh_token:
            return
        write_json(
            self.token_file,
            {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
            },
        )

    def refresh_access_token(self) -> str:
        response = self.session.post(
            f"{BASE_URL}/oauth/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise RuntimeError("Strava token refresh succeeded without access_token.")
        self.access_token = token
        next_refresh = payload.get("refresh_token")
        if isinstance(next_refresh, str) and next_refresh.strip():
            self.refresh_token = next_refresh.strip()
        self._save_tokens_to_cache()
        logger.info("Strava access token refreshed.")
        return token

    def _request(
        self, method: str, path: str, *, params: dict[str, Any] | None = None, data: dict[str, Any] | None = None
    ) -> requests.Response:
        if not self.access_token:
            self.refresh_access_token()

        response = self.session.request(
            method,
            f"{API_URL}{path}",
            headers={"Authorization": f"Bearer {self.access_token}"},
            params=params,
            data=data,
            timeout=TIMEOUT_SECONDS,
        )
        if response.status_code == 401:
            self.refresh_access_token()
            response = self.session.request(
                method,
                f"{API_URL}{path}",
                headers={"Authorization": f"Bearer {self.access_token}"},
                params=params,
                data=data,
                timeout=TIMEOUT_SECONDS,
            )
        response.raise_for_status()
        return response

    def get_recent_activities(self, per_page: int = 1) -> list[dict[str, Any]]:
        response = self._request(
            "GET",
            "/athlete/activities",
            params={"per_page": per_page, "page": 1},
        )
        return response.json()

    def get_activity_details(self, activity_id: int) -> dict[str, Any]:
        response = self._request(
            "GET",
            f"/activities/{activity_id}",
            params={"include_all_efforts": "true"},
        )
        return response.json()

    def get_activities_after(self, after_dt: datetime, per_page: int = 200) -> list[dict[str, Any]]:
        activities: list[dict[str, Any]] = []
        page = 1
        while page <= MAX_ACTIVITY_PAGES:
            response = self._request(
                "GET",
                "/athlete/activities",
                params={
                    "per_page": per_page,
                    "page": page,
                    "after": int(after_dt.timestamp()),
                },
            )
            page_items = response.json()
            if not page_items:
                break
            activities.extend(page_items)
            if len(page_items) < per_page:
                break
            page += 1
        else:
            logger.warning(
                "Strava activities pagination hit cap (%s pages, per_page=%s). Results may be truncated.",
                MAX_ACTIVITY_PAGES,
                per_page,
            )
        return activities

    def update_activity(self, activity_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._request("PUT", f"/activities/{activity_id}", data=payload)
        return response.json()


def mps_to_pace(speed_mps: float | int | None) -> str:
    if not speed_mps or speed_mps <= 0:
        return "N/A"
    pace_min_per_mile = (1609.34 / float(speed_mps)) / 60.0
    minutes = int(pace_min_per_mile)
    seconds = int(round((pace_min_per_mile - minutes) * 60))
    if seconds == 60:
        minutes += 1
        seconds = 0
    return f"{minutes}:{seconds:02d}"


def get_gap_speed_mps(activity: dict[str, Any]) -> float | None:
    for key in ("average_grade_adjusted_speed", "avgGradeAdjustedSpeed"):
        value = activity.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    return None
