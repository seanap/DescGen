import unittest
from datetime import datetime, timezone

from stat_modules.week_stats import get_garmin_period_fallback, get_period_stats, summarize_period


class TestWeekStats(unittest.TestCase):
    def test_summarize_period_uses_strava_gap_and_inputs(self) -> None:
        activities = [
            {
                "start_date": "2026-02-10T12:00:00Z",
                "sport_type": "Run",
                "type": "Run",
                "distance": 1609.34,
                "moving_time": 360,
                "calories": 150,
                "average_grade_adjusted_speed": 4.470388,
            },
            {
                "start_date": "2026-02-11T12:00:00Z",
                "sport_type": "Run",
                "type": "Run",
                "distance": 1609.34,
                "moving_time": 600,
                "calories": 300,
                "average_grade_adjusted_speed": 4.470388,
            },
        ]

        start_utc = datetime(2026, 2, 1, tzinfo=timezone.utc)
        end_utc = datetime(2026, 2, 15, tzinfo=timezone.utc)
        summary = summarize_period(activities, start_utc, end_utc, elevation_feet=1234.0)

        self.assertEqual(summary["gap"], "6:00")
        self.assertAlmostEqual(summary["distance"], 2.0, places=2)
        self.assertEqual(summary["duration"], "0h:16m")
        self.assertEqual(summary["elevation"], 1234.0)
        self.assertEqual(summary["beers_earned"], 3.0)

    def test_get_period_stats_uses_local_calendar_days(self) -> None:
        # Fixed "now" in UTC: 2026-02-15 05:00Z == 2026-02-15 00:00 in America/New_York (EST).
        now_utc = datetime(2026, 2, 15, 5, 0, 0, tzinfo=timezone.utc)
        activities = [
            {
                # 2026-02-08 00:30 local -> included in past 7 local days (Feb 9-15?) no
                # Actually this is Feb 8 local and should be excluded from 7-day window.
                "start_date": "2026-02-08T05:30:00Z",
                "sport_type": "Run",
                "type": "Run",
                "distance": 1609.34,
                "moving_time": 600,
                "calories": 150,
                "average_grade_adjusted_speed": 4.470388,
            },
            {
                # 2026-02-09 00:30 local -> included.
                "start_date": "2026-02-09T05:30:00Z",
                "sport_type": "Run",
                "type": "Run",
                "distance": 1609.34,
                "moving_time": 600,
                "calories": 150,
                "average_grade_adjusted_speed": 4.470388,
            },
        ]

        period_stats = get_period_stats(
            activities,
            {"week": 100.0, "month": 200.0, "year": 300.0},
            now_utc=now_utc,
            timezone_name="America/New_York",
        )

        week = period_stats["week"]
        self.assertAlmostEqual(week["distance"], 1.0, places=2)
        self.assertEqual(week["elevation"], 100.0)

    def test_missing_summary_calories_stays_zero(self) -> None:
        activities = [
            {
                "start_date": "2026-02-11T12:00:00Z",
                "sport_type": "Run",
                "type": "Run",
                "distance": 1609.34,
                "moving_time": 600,
                "average_grade_adjusted_speed": 4.0,
            }
        ]

        start_utc = datetime(2026, 2, 1, tzinfo=timezone.utc)
        end_utc = datetime(2026, 2, 15, tzinfo=timezone.utc)
        summary = summarize_period(activities, start_utc, end_utc, elevation_feet=0.0)

        self.assertEqual(summary["beers_earned"], 0.0)

    def test_period_stats_apply_garmin_fallback_for_gap_and_beers(self) -> None:
        activities = [
            {
                "start_date": "2026-02-12T12:00:00Z",
                "sport_type": "Run",
                "type": "Run",
                "distance": 5000,
                "moving_time": 1800,
                "average_speed": 2.8,  # no Strava GAP key
            }
        ]
        now_utc = datetime(2026, 2, 15, 12, 0, 0, tzinfo=timezone.utc)
        fallback = {
            "week": {"gap": "9:50", "beers_earned": 36.0},
            "month": {"gap": "10:01", "beers_earned": 155.0},
            "year": {"gap": "10:20", "beers_earned": 230.0},
        }

        period_stats = get_period_stats(
            activities,
            {"week": 100.0, "month": 200.0, "year": 300.0},
            now_utc=now_utc,
            timezone_name="America/New_York",
            garmin_period_fallback=fallback,
        )

        self.assertEqual(period_stats["week"]["gap"], "9:50")
        self.assertEqual(period_stats["month"]["gap"], "10:01")
        self.assertEqual(period_stats["year"]["gap"], "10:20")
        self.assertEqual(period_stats["week"]["beers_earned"], 36.0)
        self.assertEqual(period_stats["month"]["beers_earned"], 155.0)
        self.assertEqual(period_stats["year"]["beers_earned"], 230.0)

    def test_get_garmin_period_fallback_from_activity_list(self) -> None:
        class DummyClient:
            def get_activities_by_date(self, _start: str, _end: str):
                return [
                    {
                        "startTimeGMT": "2026-02-15 10:00:00",
                        "activityType": {"typeKey": "running"},
                        "calories": 300,
                        "avgGradeAdjustedSpeed": 2.728,  # ~9:50
                    },
                    {
                        "startTimeGMT": "2026-02-10 10:00:00",
                        "activityType": {"typeKey": "running"},
                        "calories": 450,
                        "avgGradeAdjustedSpeed": 2.677,  # ~10:00
                    },
                ]

        now_utc = datetime(2026, 2, 15, 12, 0, 0, tzinfo=timezone.utc)
        fallback = get_garmin_period_fallback(
            DummyClient(),
            now_utc=now_utc,
            timezone_name="America/New_York",
        )

        self.assertIsNotNone(fallback)
        assert fallback is not None
        self.assertGreater(fallback["week"]["beers_earned"], 0.0)
        self.assertNotEqual(fallback["week"]["gap"], "N/A")


if __name__ == "__main__":
    unittest.main()
