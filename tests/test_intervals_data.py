import unittest
from unittest.mock import Mock, patch

import requests

from chronicle.stat_modules.intervals_data import (
    get_intervals_activity_data,
    get_intervals_dashboard_metrics,
)


def _response_with_json(payload):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


class TestIntervalsData(unittest.TestCase):
    @patch("chronicle.stat_modules.intervals_data.requests.get")
    def test_handles_null_achievements(self, mock_get) -> None:
        mock_get.side_effect = [
            _response_with_json([{"id": 12345}]),
            _response_with_json({"icu_achievements": None}),
        ]

        result = get_intervals_activity_data("athlete", "apikey")

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["achievements"], [])

    @patch("chronicle.stat_modules.intervals_data.requests.get")
    def test_skips_invalid_achievement_items(self, mock_get) -> None:
        mock_get.side_effect = [
            _response_with_json([{"id": 12345}]),
            _response_with_json(
                {
                    "icu_achievements": [
                        None,
                        "not-a-dict",
                        {"type": "BEST_POWER", "watts": 321, "secs": 75},
                        {"message": "Big day"},
                    ]
                }
            ),
        ]

        result = get_intervals_activity_data("athlete", "apikey")

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result["achievements"]), 2)
        self.assertIn("New best power: 321W for 1m 15s", result["achievements"])
        self.assertIn("Big day", result["achievements"])

    @patch("chronicle.stat_modules.intervals_data.requests.get")
    def test_handles_dict_activities_payload(self, mock_get) -> None:
        mock_get.side_effect = [
            _response_with_json({"activities": [{"id": 222}]}),
            _response_with_json({}),
        ]

        result = get_intervals_activity_data("athlete", "apikey")

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["achievements"], [])
        self.assertEqual(result["norm_power"], "N/A")
        self.assertEqual(result["avg_pace"], "N/A")
        self.assertEqual(result["zone_summary"], "N/A")

    @patch("chronicle.stat_modules.intervals_data.requests.get")
    def test_formats_extended_metrics(self, mock_get) -> None:
        mock_get.side_effect = [
            _response_with_json([{"id": 888}]),
            _response_with_json(
                {
                    "icu_ctl": 71.6,
                    "icu_atl": 78.2,
                    "icu_training_load": 129.4,
                    "ramp_rate": -3.64,
                    "strain_score": 143.3,
                    "pace_load": 55.9,
                    "hr_load": 60.1,
                    "power_load": 58.8,
                    "average_speed": 3.5,
                    "max_speed": 5.5,
                    "distance": 10000,
                    "moving_time": 2488,
                    "elapsed_time": 2610,
                    "average_heartrate": 149,
                    "max_heartrate": 173,
                    "total_elevation_gain": 190.5,
                    "total_elevation_loss": 183.2,
                    "average_temp": 63.2,
                    "max_temp": 67.4,
                    "min_temp": 58.1,
                    "icu_zone_times": [{"id": 1, "secs": 320}, {"id": 2, "secs": 821}],
                    "icu_hr_zone_times": [280, 901, 0],
                    "pace_zone_times": [601, 702],
                    "gap_zone_times": [450, 640],
                    "icu_achievements": [],
                }
            ),
        ]

        result = get_intervals_activity_data("athlete", "apikey")

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["ctl"], 72)
        self.assertEqual(result["atl"], 78)
        self.assertEqual(result["training_load"], 129)
        self.assertEqual(result["fitness"], 72)
        self.assertEqual(result["fatigue"], 78)
        self.assertEqual(result["load"], 129)
        self.assertEqual(result["ramp"], -3.6)
        self.assertEqual(result["ramp_display"], "-3.6")
        self.assertEqual(result["form_percent"], -9)
        self.assertEqual(result["form_percent_display"], "-9%")
        self.assertEqual(result["form_class"], "Grey Zone")
        self.assertEqual(result["form_class_emoji"], "⛔")
        self.assertEqual(result["avg_pace"], "7:40/mi")
        self.assertEqual(result["distance_miles"], "6.21 mi")
        self.assertEqual(result["moving_time"], "41:28")
        self.assertEqual(result["elevation_gain_feet"], 625)
        self.assertEqual(result["average_temp_f"], "63.2F")
        self.assertIn("Z1", result["zone_summary"])

    @patch("chronicle.stat_modules.intervals_data.requests.get")
    def test_dashboard_metrics_extracts_strava_match_and_fields(self, mock_get) -> None:
        mock_get.return_value = _response_with_json(
            [
                {
                    "strava_activity_id": 17455368360,
                    "start_date": "2026-02-21T10:05:00Z",
                    "average_speed": 3.2,
                    "moving_time": 3600,
                    "icu_efficiency_factor": 1.23,
                    "icu_ctl": 71.0,
                    "icu_atl": 76.0,
                }
            ]
        )

        records = get_intervals_dashboard_metrics(
            "athlete",
            "apikey",
            oldest="2026-01-01T00:00:00Z",
            newest="2026-12-31T23:59:59Z",
        )

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["strava_activity_id"], "17455368360")
        self.assertEqual(record["start_date"], "2026-02-21T10:05:00Z")
        self.assertEqual(record["avg_pace_mps"], 3.2)
        self.assertEqual(record["avg_efficiency_factor"], 1.23)
        self.assertEqual(record["avg_fitness"], 71.0)
        self.assertEqual(record["avg_fatigue"], 76.0)
        self.assertEqual(record["moving_time_seconds"], 3600.0)

    @patch("chronicle.stat_modules.intervals_data.requests.get")
    def test_dashboard_metrics_derives_pace_from_distance_and_time(self, mock_get) -> None:
        mock_get.return_value = _response_with_json(
            [
                {
                    "source_id": "strava:18887776666",
                    "start_date_local": "2026-02-22T11:07:00Z",
                    "distance": 5000.0,
                    "moving_time": 1000.0,
                    "efficiency_factor": 1.11,
                    "fitness": 65,
                    "fatigue": 72,
                }
            ]
        )

        records = get_intervals_dashboard_metrics(
            "athlete",
            "apikey",
            oldest="2026-01-01T00:00:00Z",
            newest="2026-12-31T23:59:59Z",
        )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["strava_activity_id"], "18887776666")
        self.assertEqual(records[0]["avg_pace_mps"], 5.0)
        self.assertEqual(records[0]["avg_efficiency_factor"], 1.11)

    @patch("chronicle.stat_modules.intervals_data.requests.get")
    def test_dashboard_metrics_handles_request_failure(self, mock_get) -> None:
        mock_get.side_effect = requests.RequestException("boom")
        records = get_intervals_dashboard_metrics(
            "athlete",
            "apikey",
            oldest="2026-01-01T00:00:00Z",
            newest="2026-12-31T23:59:59Z",
        )
        self.assertEqual(records, [])


if __name__ == "__main__":
    unittest.main()
