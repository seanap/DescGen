import unittest
from datetime import datetime, timezone

from stat_modules.smashrun import aggregate_elevation_totals, get_activity_elevation_feet


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


if __name__ == "__main__":
    unittest.main()
