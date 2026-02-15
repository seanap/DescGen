import unittest
from datetime import datetime, timezone

from stat_modules.smashrun import aggregate_elevation_totals


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


if __name__ == "__main__":
    unittest.main()
