from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

from chronicle.config import Settings
from chronicle.dashboard_data import get_dashboard_payload


class TestDashboardPayloadContract(unittest.TestCase):
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

    def test_payload_contract_shape_and_types(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            settings = self._settings_for(td)
            fake_activities = [
                {
                    "id": 9001,
                    "start_date_local": "2025-12-31T23:55:00+00:00",
                    "sport_type": "Run",
                    "distance": 8046.72,
                    "moving_time": 2400,
                    "total_elevation_gain": 123.4,
                    "name": "Tempo",
                },
                {
                    "id": 9002,
                    "start_date_local": "2026-01-01T07:00:00+00:00",
                    "sport_type": "Ride",
                    "distance": 32186.88,
                    "moving_time": 3600,
                    "total_elevation_gain": 456.7,
                },
            ]

            with mock.patch("chronicle.dashboard_data.StravaClient") as mock_client_cls:
                mock_client = mock_client_cls.return_value
                mock_client.get_activities_after.return_value = fake_activities
                payload = get_dashboard_payload(settings, force_refresh=True)

            required_root_keys = {
                "source",
                "generated_at",
                "validated_at",
                "years",
                "types",
                "type_meta",
                "other_bucket",
                "aggregates",
                "units",
                "week_start",
                "activities",
                "intervals",
                "intervals_year_type_metrics",
            }
            self.assertTrue(required_root_keys.issubset(payload.keys()))

            parsed_generated = datetime.fromisoformat(str(payload["generated_at"]).replace("Z", "+00:00"))
            self.assertIsNotNone(parsed_generated.tzinfo)
            self.assertEqual(payload["source"], "strava")

            self.assertIsInstance(payload["years"], list)
            self.assertTrue(all(isinstance(year, int) for year in payload["years"]))
            self.assertEqual(payload["years"], sorted(payload["years"]))

            self.assertIsInstance(payload["types"], list)
            self.assertTrue(all(isinstance(item, str) for item in payload["types"]))
            self.assertIn("Run", payload["types"])
            self.assertIn("Ride", payload["types"])

            self.assertIsInstance(payload["type_meta"], dict)
            for type_name in payload["types"]:
                self.assertIn(type_name, payload["type_meta"])
                meta = payload["type_meta"][type_name]
                self.assertIsInstance(meta.get("label"), str)
                self.assertIsInstance(meta.get("accent"), str)

            self.assertEqual(payload["units"], {"distance": "mi", "elevation": "ft"})
            self.assertIn(payload["week_start"], {"sunday", "monday"})
            self.assertIsInstance(payload["intervals"], dict)
            self.assertIn("enabled", payload["intervals"])
            self.assertIn("records", payload["intervals"])
            self.assertIn("matched_activities", payload["intervals"])
            self.assertIsInstance(payload["intervals_year_type_metrics"], dict)

            self.assertIsInstance(payload["aggregates"], dict)
            for year_key, year_bucket in payload["aggregates"].items():
                self.assertTrue(year_key.isdigit())
                self.assertIsInstance(year_bucket, dict)
                for type_key, type_bucket in year_bucket.items():
                    self.assertIsInstance(type_key, str)
                    self.assertIsInstance(type_bucket, dict)
                    for date_key, entry in type_bucket.items():
                        self.assertRegex(date_key, r"^\d{4}-\d{2}-\d{2}$")
                        self.assertIsInstance(entry.get("count"), int)
                        self.assertIsInstance(entry.get("distance"), float)
                        self.assertIsInstance(entry.get("moving_time"), float)
                        self.assertIsInstance(entry.get("elevation_gain"), float)
                        self.assertIsInstance(entry.get("activity_ids"), list)
                        self.assertTrue(all(isinstance(activity_id, str) for activity_id in entry["activity_ids"]))
                        optional_metric_keys = (
                            "avg_pace_mps",
                            "avg_efficiency_factor",
                            "avg_fitness",
                            "avg_fatigue",
                        )
                        for metric_key in optional_metric_keys:
                            if metric_key in entry:
                                self.assertIsInstance(entry[metric_key], float)

            self.assertIsInstance(payload["activities"], list)
            self.assertEqual(len(payload["activities"]), 2)
            for activity in payload["activities"]:
                self.assertRegex(str(activity.get("date")), r"^\d{4}-\d{2}-\d{2}$")
                self.assertIsInstance(activity.get("year"), int)
                self.assertIsInstance(activity.get("type"), str)
                self.assertIsInstance(activity.get("raw_type"), str)
                self.assertIsInstance(activity.get("start_date_local"), str)
                self.assertIsInstance(activity.get("hour"), int)
                self.assertTrue(str(activity.get("url", "")).startswith("https://www.strava.com/activities/"))


if __name__ == "__main__":
    unittest.main()
