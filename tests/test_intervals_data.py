import unittest
from unittest.mock import Mock, patch

from stat_modules.intervals_data import get_intervals_activity_data


def _response_with_json(payload):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


class TestIntervalsData(unittest.TestCase):
    @patch("stat_modules.intervals_data.requests.get")
    def test_handles_null_achievements(self, mock_get) -> None:
        mock_get.side_effect = [
            _response_with_json([{"id": 12345}]),
            _response_with_json({"icu_achievements": None}),
        ]

        result = get_intervals_activity_data("athlete", "apikey")

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["achievements"], [])

    @patch("stat_modules.intervals_data.requests.get")
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

    @patch("stat_modules.intervals_data.requests.get")
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


if __name__ == "__main__":
    unittest.main()
