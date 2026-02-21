from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import chronicle.dashboard_data as dashboard_data
from chronicle.config import Settings
from chronicle.dashboard_data import dashboard_data_path, get_dashboard_payload, intervals_metrics_cache_path
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
                "DASHBOARD_WEEK_START": "sunday",
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
                with mock.patch.dict(os.environ, {"DASHBOARD_WEEK_START": "sunday"}, clear=False):
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

    def test_stale_cache_served_and_background_refresh_scheduled(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            settings = self._settings_for(td)
            stale_iso = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            stale_payload = {
                "generated_at": stale_iso,
                "validated_at": stale_iso,
                "years": [2026],
                "types": [],
                "type_meta": {},
                "other_bucket": "OtherSports",
                "aggregates": {},
                "units": {"distance": "mi", "elevation": "ft"},
                "week_start": "sunday",
                "activities": [],
                "latest_activity_id": "42",
            }
            write_json(dashboard_data_path(settings), stale_payload)

            with mock.patch("chronicle.dashboard_data._schedule_background_refresh", return_value=True) as schedule:
                payload = get_dashboard_payload(settings, force_refresh=False, max_age_seconds=60)

            self.assertEqual(payload["latest_activity_id"], "42")
            self.assertEqual(payload.get("cache_state"), "stale_revalidating")
            self.assertTrue(payload.get("revalidating"))
            schedule.assert_called_once()

    def test_cached_payload_normalizes_intervals_enabled_from_settings(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base_settings = self._settings_for(td)
            settings = replace(base_settings, enable_intervals=True)
            now_iso = datetime.now(timezone.utc).isoformat()
            cached_payload = {
                "generated_at": now_iso,
                "validated_at": now_iso,
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

            payload = get_dashboard_payload(settings, force_refresh=False, max_age_seconds=3600)

            self.assertIn("intervals", payload)
            self.assertTrue(payload["intervals"]["enabled"])
            self.assertIn("intervals_year_type_metrics", payload)

    def test_smart_revalidate_touches_payload_when_latest_activity_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            settings = self._settings_for(td)
            data_path = dashboard_data_path(settings)
            stale_iso = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            stale_payload = {
                "generated_at": stale_iso,
                "validated_at": stale_iso,
                "years": [2026],
                "types": [],
                "type_meta": {},
                "other_bucket": "OtherSports",
                "aggregates": {},
                "units": {"distance": "mi", "elevation": "ft"},
                "week_start": "sunday",
                "activities": [],
                "latest_activity_id": "1002",
                "latest_activity_start_date": "2026-02-20T10:00:00Z",
            }
            write_json(data_path, stale_payload)

            with mock.patch(
                "chronicle.dashboard_data._fetch_latest_activity_marker",
                return_value=("1002", "2026-02-20T10:00:00Z"),
            ), mock.patch("chronicle.dashboard_data.build_dashboard_payload") as build_payload:
                refreshed = dashboard_data._smart_revalidate_payload(settings, data_path, stale_payload)

            build_payload.assert_not_called()
            self.assertEqual(refreshed["latest_activity_id"], "1002")
            self.assertIn("validated_at", refreshed)
            self.assertNotEqual(refreshed["validated_at"], stale_iso)
            on_disk = dashboard_data.read_json(data_path)
            self.assertIsInstance(on_disk, dict)
            assert isinstance(on_disk, dict)
            self.assertEqual(on_disk.get("latest_activity_id"), "1002")

    def test_enriches_aggregates_with_intervals_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base_settings = self._settings_for(td)
            settings = replace(
                base_settings,
                enable_intervals=True,
                intervals_user_id="athlete",
                intervals_api_key="api-key",
            )
            fake_activities = [
                {
                    "id": 1001,
                    "start_date_local": "2026-02-01T10:15:20+00:00",
                    "sport_type": "Run",
                    "distance": 5000.0,
                    "moving_time": 1500,
                    "total_elevation_gain": 42.0,
                    "name": "Morning Run",
                },
                {
                    "id": 1002,
                    "start_date_local": "2026-02-01T18:30:44+00:00",
                    "sport_type": "Run",
                    "distance": 10000.0,
                    "moving_time": 3000,
                    "total_elevation_gain": 85.0,
                },
            ]
            intervals_records = [
                {
                    "strava_activity_id": "1001",
                    "start_date": "2026-02-01T10:15:00+00:00",
                    "avg_pace_mps": 3.0,
                    "avg_efficiency_factor": 1.2,
                    "avg_fitness": 70.0,
                    "avg_fatigue": 78.0,
                    "moving_time_seconds": 1500.0,
                },
                {
                    "strava_activity_id": None,
                    "start_date": "2026-02-01T18:30:00+00:00",
                    "avg_pace_mps": 4.0,
                    "avg_efficiency_factor": 1.0,
                    "avg_fitness": 74.0,
                    "avg_fatigue": 82.0,
                    "moving_time_seconds": 3000.0,
                },
            ]

            with mock.patch("chronicle.dashboard_data.StravaClient") as mock_client_cls, mock.patch(
                "chronicle.dashboard_data.get_intervals_dashboard_metrics",
                return_value=intervals_records,
            ):
                mock_client = mock_client_cls.return_value
                mock_client.get_activities_after.return_value = fake_activities
                payload = get_dashboard_payload(settings, force_refresh=True)

            self.assertEqual(payload["intervals"]["records"], 2)
            self.assertEqual(payload["intervals"]["matched_activities"], 2)
            entry = payload["aggregates"]["2026"]["Run"]["2026-02-01"]
            self.assertAlmostEqual(entry["avg_pace_mps"], 3.3333333, places=4)
            self.assertAlmostEqual(entry["avg_efficiency_factor"], 1.0666666, places=4)
            self.assertAlmostEqual(entry["avg_fitness"], 72.0, places=4)
            self.assertAlmostEqual(entry["avg_fatigue"], 80.0, places=4)

            totals = payload["intervals_year_type_metrics"]["2026"]["Run"]
            self.assertAlmostEqual(totals["avg_efficiency_factor"], 1.0666666, places=4)
            self.assertAlmostEqual(totals["avg_fitness"], 72.0, places=4)
            self.assertAlmostEqual(totals["avg_fatigue"], 80.0, places=4)

    def test_intervals_sync_uses_seed_then_incremental_current_year_window(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base_settings = self._settings_for(td)
            settings = replace(
                base_settings,
                enable_intervals=True,
                intervals_user_id="athlete",
                intervals_api_key="api-key",
            )
            fake_activities = [
                {
                    "id": 1001,
                    "start_date_local": "2026-02-01T10:15:20+00:00",
                    "sport_type": "Run",
                    "distance": 5000.0,
                    "moving_time": 1500,
                    "total_elevation_gain": 42.0,
                }
            ]
            seed_records = [
                {
                    "strava_activity_id": "1001",
                    "start_date": "2026-02-01T10:15:00+00:00",
                    "avg_efficiency_factor": 1.2,
                    "avg_fitness": 70.0,
                    "avg_fatigue": 78.0,
                    "moving_time_seconds": 1500.0,
                }
            ]
            incremental_records = [
                {
                    "strava_activity_id": "1001",
                    "start_date": "2026-02-01T10:15:00+00:00",
                    "avg_efficiency_factor": 1.22,
                    "avg_fitness": 71.0,
                    "avg_fatigue": 79.0,
                    "moving_time_seconds": 1500.0,
                }
            ]

            with mock.patch("chronicle.dashboard_data.StravaClient") as mock_client_cls, mock.patch(
                "chronicle.dashboard_data.get_intervals_dashboard_metrics",
                side_effect=[seed_records, incremental_records],
            ) as mock_intervals:
                mock_client = mock_client_cls.return_value
                mock_client.get_activities_after.return_value = fake_activities
                first_payload = get_dashboard_payload(settings, force_refresh=True)
                second_payload = get_dashboard_payload(settings, force_refresh=True)

            first_call = mock_intervals.call_args_list[0].kwargs
            second_call = mock_intervals.call_args_list[1].kwargs
            self.assertEqual(first_payload["intervals"].get("sync_mode"), "seed")
            self.assertEqual(second_payload["intervals"].get("sync_mode"), "incremental")
            self.assertEqual(first_call["oldest"], dashboard_data._dashboard_history_start())
            current_year_start = datetime(datetime.now(timezone.utc).year, 1, 1, tzinfo=timezone.utc)
            self.assertGreaterEqual(second_call["oldest"], current_year_start)
            cache_payload = dashboard_data.read_json(intervals_metrics_cache_path(settings))
            self.assertIsInstance(cache_payload, dict)
            assert isinstance(cache_payload, dict)
            self.assertEqual(cache_payload.get("last_fetch_mode"), "incremental")


if __name__ == "__main__":
    unittest.main()
