from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from chronicle.config import Settings
from chronicle.dashboard_data import dashboard_data_path, get_dashboard_payload
from chronicle.storage import write_json


class TestDashboardData(unittest.TestCase):
    def _settings_for(self, state_dir: str) -> Settings:
        with mock.patch.dict(
            os.environ,
            {
                "STATE_DIR": state_dir,
                "STRAVA_CLIENT_ID": "test-client-id",
                "STRAVA_CLIENT_SECRET": "test-client-secret",
                "STRAVA_REFRESH_TOKEN": "test-refresh-token",
            },
            clear=False,
        ):
            settings = Settings.from_env()
            settings.ensure_state_paths()
        return settings

    def test_builds_expected_payload_shape(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            settings = self._settings_for(td)
            fake_activities = [
                {
                    "id": 1001,
                    "start_date_local": "2026-02-01T10:15:00+00:00",
                    "sport_type": "Run",
                    "distance": 5000.0,
                    "moving_time": 1500,
                    "total_elevation_gain": 42.0,
                    "name": "Morning Run",
                },
                {
                    "id": 1002,
                    "start_date_local": "2026-02-01T18:30:00+00:00",
                    "sport_type": "Run",
                    "distance": 10000.0,
                    "moving_time": 3200,
                    "total_elevation_gain": 85.0,
                },
            ]

            with mock.patch("chronicle.dashboard_data.StravaClient") as mock_client_cls:
                mock_client = mock_client_cls.return_value
                mock_client.get_activities_after.return_value = fake_activities
                payload = get_dashboard_payload(settings, force_refresh=True)

            self.assertEqual(payload["source"], "strava")
            self.assertIn("generated_at", payload)
            self.assertEqual(payload["week_start"], "sunday")
            self.assertEqual(payload["units"], {"distance": "mi", "elevation": "ft"})
            self.assertIn("Run", payload["types"])
            self.assertEqual(len(payload["activities"]), 2)
            self.assertEqual(payload["activities"][0]["hour"], 10)
            self.assertTrue(payload["activities"][0]["url"].endswith("/1001"))

            entry = payload["aggregates"]["2026"]["Run"]["2026-02-01"]
            self.assertEqual(entry["count"], 2)
            self.assertEqual(entry["activity_ids"], ["1001", "1002"])

    def test_uses_fresh_cache_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            settings = self._settings_for(td)
            now_iso = datetime.now(timezone.utc).isoformat()
            cached_payload = {
                "generated_at": now_iso,
                "years": [2026],
                "types": [],
                "type_meta": {},
                "other_bucket": "OtherSports",
                "aggregates": {},
                "units": {"distance": "mi", "elevation": "ft"},
                "week_start": "sunday",
                "activities": [],
            }
            write_json(dashboard_data_path(settings), cached_payload)

            with mock.patch("chronicle.dashboard_data.build_dashboard_payload") as mock_build:
                payload = get_dashboard_payload(settings, force_refresh=False, max_age_seconds=3600)

            self.assertEqual(payload["generated_at"], now_iso)
            mock_build.assert_not_called()

    def test_returns_stale_cache_if_rebuild_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            settings = self._settings_for(td)
            stale_iso = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            stale_payload = {
                "generated_at": stale_iso,
                "years": [2024],
                "types": [],
                "type_meta": {},
                "other_bucket": "OtherSports",
                "aggregates": {},
                "units": {"distance": "mi", "elevation": "ft"},
                "week_start": "sunday",
                "activities": [],
            }
            path = dashboard_data_path(settings)
            write_json(path, stale_payload)

            with mock.patch(
                "chronicle.dashboard_data.build_dashboard_payload",
                side_effect=RuntimeError("boom"),
            ):
                payload = get_dashboard_payload(settings, force_refresh=True)

            self.assertEqual(payload["generated_at"], stale_iso)
            self.assertTrue(Path(path).exists())

    def test_returns_empty_payload_if_rebuild_fails_without_cache(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            settings = self._settings_for(td)
            with mock.patch(
                "chronicle.dashboard_data.build_dashboard_payload",
                side_effect=RuntimeError("boom"),
            ):
                payload = get_dashboard_payload(settings, force_refresh=True)

            self.assertIn("years", payload)
            self.assertIn("types", payload)
            self.assertIn("activities", payload)
            self.assertEqual(payload.get("error"), "dashboard_build_failed")


if __name__ == "__main__":
    unittest.main()
