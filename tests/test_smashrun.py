import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from stat_modules.smashrun import (
    aggregate_elevation_totals,
    get_activity_elevation_feet,
    get_badges,
    get_activity_record,
)


class TestSmashrunAggregation(unittest.TestCase):
    def test_aggregate_uses_local_calendar_days(self) -> None:
        # now_utc corresponds to local midnight in America/New_York on 2026-02-15.
        now_utc = datetime(2026, 2, 15, 5, 0, 0, tzinfo=timezone.utc)
        activities = [
            {
                "startDateTimeUtc": "2026-02-08T05:30:00Z",  # Feb 8 local, outside past 7 local days
                "elevationGainFeet": 100,
            },
            {
                "startDateTimeUtc": "2026-02-09T05:30:00Z",  # Feb 9 local, included
                "elevationGainFeet": 200,
            },
        ]

        totals = aggregate_elevation_totals(
            activities,
            now_utc=now_utc,
            timezone_name="America/New_York",
        )
        self.assertEqual(totals["week"], 200.0)
        self.assertEqual(totals["month"], 300.0)
        self.assertEqual(totals["year"], 300.0)

    def test_aggregate_handles_string_elevation_and_alt_datetime(self) -> None:
        now_utc = datetime(2026, 2, 15, 12, 0, 0, tzinfo=timezone.utc)
        activities = [
            {
                "startDateTime": "2026-02-14T12:00:00Z",
                "elevationGain": "100",  # meters
            }
        ]

        totals = aggregate_elevation_totals(
            activities,
            now_utc=now_utc,
            timezone_name="America/New_York",
        )
        self.assertGreater(totals["week"], 300.0)

    def test_get_activity_elevation_prefers_direct_id_match(self) -> None:
        activities = [
            {
                "activityId": 10,
                "stravaActivityId": 1234,
                "elevationGainFeet": 252,
                "startDateTimeUtc": "2026-02-15T10:00:00Z",
            },
            {
                "activityId": 11,
                "elevationGainFeet": 100,
                "startDateTimeUtc": "2026-02-15T09:00:00Z",
            },
        ]
        strava_activity = {
            "id": 1234,
            "start_date": "2026-02-15T10:00:00Z",
            "distance": 10000,
        }
        self.assertEqual(get_activity_elevation_feet(activities, strava_activity), 252.0)

    def test_get_activity_elevation_falls_back_to_time_distance_match(self) -> None:
        activities = [
            {
                "activityId": 21,
                "elevationGainFeet": 120,
                "startDateTimeUtc": "2026-02-15T10:10:00Z",
                "distanceKm": 5.0,
            },
            {
                "activityId": 22,
                "elevationGainFeet": 250,
                "startDateTimeUtc": "2026-02-15T11:01:00Z",
                "distanceKm": 10.05,
            },
        ]
        strava_activity = {
            "id": 9999,
            "start_date": "2026-02-15T11:00:00Z",
            "distance": 10000.0,
        }
        self.assertEqual(get_activity_elevation_feet(activities, strava_activity), 250.0)

    def test_get_activity_record_returns_best_match(self) -> None:
        activities = [
            {
                "activityId": 31,
                "startDateTimeUtc": "2026-02-15T12:30:00Z",
                "distance": 5000.0,
            },
            {
                "activityId": 32,
                "startDateTimeUtc": "2026-02-15T13:00:00Z",
                "distance": 10050.0,
            },
        ]
        strava_activity = {
            "id": 54321,
            "start_date": "2026-02-15T13:00:00Z",
            "distance": 10000.0,
        }
        matched = get_activity_record(activities, strava_activity)
        self.assertIsNotNone(matched)
        assert matched is not None
        self.assertEqual(matched["activityId"], 32)


class TestSmashrunBadges(unittest.TestCase):
    @patch("stat_modules.smashrun.requests.get")
    def test_get_badges_handles_list_payload(self, mock_get: Mock) -> None:
        response = Mock()
        response.json.return_value = [{"badgeName": "Milestone"}, {"badgeName": "Elevation"}]
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        badges = get_badges("token")
        self.assertEqual(len(badges), 2)
        self.assertEqual(badges[0]["badgeName"], "Milestone")

    @patch("stat_modules.smashrun.requests.get")
    def test_get_badges_handles_wrapped_payload(self, mock_get: Mock) -> None:
        response = Mock()
        response.json.return_value = {"badges": [{"badgeName": "Consistency"}]}
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        badges = get_badges("token")
        self.assertEqual(len(badges), 1)
        self.assertEqual(badges[0]["badgeName"], "Consistency")


if __name__ == "__main__":
    unittest.main()
