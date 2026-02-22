from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from chronicle.activity_pipeline import (
    PERIOD_STATS_ACTIVITIES_CACHE_KEY,
    _get_period_stats_activities,
)
from chronicle.storage import get_runtime_value, set_runtime_value


def _settings_for(path: Path) -> SimpleNamespace:
    return SimpleNamespace(processed_log_file=path)


class TestPeriodStatsIncrementalSync(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "processed_activities.log"
        self._old_runtime = os.environ.get("RUNTIME_DB_FILE")
        os.environ["RUNTIME_DB_FILE"] = "runtime_state.db"
        self.year_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.settings = _settings_for(self.path)
        self.strava_client = mock.Mock()

    def tearDown(self) -> None:
        if self._old_runtime is None:
            os.environ.pop("RUNTIME_DB_FILE", None)
        else:
            os.environ["RUNTIME_DB_FILE"] = self._old_runtime
        self.temp_dir.cleanup()

    def test_period_stats_sync_uses_cache_when_marker_is_unchanged(self) -> None:
        set_runtime_value(
            self.settings.processed_log_file,
            PERIOD_STATS_ACTIVITIES_CACHE_KEY,
            {
                "year_start_utc": self.year_start.isoformat(),
                "latest_activity_id": "1002",
                "latest_activity_start_date": "2026-02-20T10:00:00Z",
                "activities": [
                    {
                        "id": "1001",
                        "start_date": "2026-02-19T10:00:00Z",
                        "sport_type": "Run",
                        "type": "Run",
                        "distance": 5000.0,
                        "moving_time": 1500.0,
                        "calories": 400.0,
                    },
                    {
                        "id": "1002",
                        "start_date": "2026-02-20T10:00:00Z",
                        "sport_type": "Run",
                        "type": "Run",
                        "distance": 6000.0,
                        "moving_time": 1800.0,
                        "calories": 500.0,
                    },
                ],
            },
        )

        with mock.patch("chronicle.activity_pipeline._run_required_call") as required_call:
            activities, sync = _get_period_stats_activities(
                self.settings,
                self.strava_client,
                year_start_utc=self.year_start,
                latest_marker=("1002", "2026-02-20T10:00:00Z"),
                service_state={},
            )

        required_call.assert_not_called()
        self.assertEqual(sync["mode"], "cache_hit")
        self.assertEqual(sync["fetched_records"], 0)
        self.assertEqual({item["id"] for item in activities}, {"1001", "1002"})

    def test_period_stats_sync_incrementally_merges_recent_activities(self) -> None:
        set_runtime_value(
            self.settings.processed_log_file,
            PERIOD_STATS_ACTIVITIES_CACHE_KEY,
            {
                "year_start_utc": self.year_start.isoformat(),
                "latest_activity_id": "1001",
                "latest_activity_start_date": "2026-02-19T10:00:00Z",
                "activities": [
                    {
                        "id": "1001",
                        "start_date": "2026-02-19T10:00:00Z",
                        "sport_type": "Run",
                        "type": "Run",
                        "distance": 5000.0,
                        "moving_time": 1500.0,
                        "calories": 400.0,
                    }
                ],
            },
        )
        latest_start = "2026-02-20T10:00:00Z"

        with mock.patch(
            "chronicle.activity_pipeline._run_required_call",
            return_value=[
                {
                    "id": 1002,
                    "start_date": latest_start,
                    "sport_type": "Run",
                    "distance": 8000.0,
                    "moving_time": 2400,
                    "calories": 650.0,
                }
            ],
        ) as required_call:
            activities, sync = _get_period_stats_activities(
                self.settings,
                self.strava_client,
                year_start_utc=self.year_start,
                latest_marker=("1002", latest_start),
                service_state={},
            )

        expected_after = datetime.fromisoformat(latest_start.replace("Z", "+00:00")) - timedelta(hours=48)
        self.assertEqual(sync["mode"], "incremental")
        self.assertEqual(sync["fetched_records"], 1)
        self.assertEqual({item["id"] for item in activities}, {"1001", "1002"})
        self.assertEqual(required_call.call_count, 1)
        self.assertEqual(required_call.call_args.args[3], expected_after)

        cached = get_runtime_value(self.settings.processed_log_file, PERIOD_STATS_ACTIVITIES_CACHE_KEY)
        self.assertIsInstance(cached, dict)
        assert isinstance(cached, dict)
        self.assertEqual(cached.get("latest_activity_id"), "1002")
        self.assertEqual(len(cached.get("activities", [])), 2)

    def test_period_stats_sync_falls_back_to_full_rebuild_when_incremental_misses_latest(self) -> None:
        set_runtime_value(
            self.settings.processed_log_file,
            PERIOD_STATS_ACTIVITIES_CACHE_KEY,
            {
                "year_start_utc": self.year_start.isoformat(),
                "latest_activity_id": "1001",
                "latest_activity_start_date": "2026-02-19T10:00:00Z",
                "activities": [
                    {
                        "id": "1001",
                        "start_date": "2026-02-19T10:00:00Z",
                        "sport_type": "Run",
                        "type": "Run",
                        "distance": 5000.0,
                        "moving_time": 1500.0,
                        "calories": 400.0,
                    }
                ],
            },
        )

        with mock.patch(
            "chronicle.activity_pipeline._run_required_call",
            side_effect=[
                [
                    {
                        "id": 1110,
                        "start_date": "2026-02-18T10:00:00Z",
                        "sport_type": "Run",
                        "distance": 3000.0,
                        "moving_time": 1100,
                    }
                ],
                [
                    {
                        "id": 1110,
                        "start_date": "2026-02-18T10:00:00Z",
                        "sport_type": "Run",
                        "distance": 3000.0,
                        "moving_time": 1100,
                    },
                    {
                        "id": 2002,
                        "start_date": "2026-02-20T10:00:00Z",
                        "sport_type": "Run",
                        "distance": 9000.0,
                        "moving_time": 2600,
                    },
                ],
            ],
        ) as required_call:
            activities, sync = _get_period_stats_activities(
                self.settings,
                self.strava_client,
                year_start_utc=self.year_start,
                latest_marker=("2002", "2026-02-20T10:00:00Z"),
                service_state={},
            )

        self.assertEqual(required_call.call_count, 2)
        self.assertEqual(sync["mode"], "full")
        self.assertEqual(sync.get("fallback_reason"), "incremental_missing_latest_marker")
        self.assertIn("2002", {item["id"] for item in activities})


if __name__ == "__main__":
    unittest.main()
