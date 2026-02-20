import unittest
from types import SimpleNamespace

from chronicle.activity_pipeline import (
    _extract_strava_badges,
    _extract_strava_segment_notables,
    _profile_activity_update_payload,
    _profile_match_reasons,
)


class TestStravaSegmentNotables(unittest.TestCase):
    def test_extract_segment_notables_dedupes_by_best_rank(self) -> None:
        activity = {
            "segment_efforts": [
                {
                    "name": "Hill Climb",
                    "segment": {"id": 111, "name": "Hill Climb"},
                    "pr_rank": 3,
                    "elapsed_time": 130,
                },
                {
                    "name": "Hill Climb",
                    "segment": {"id": 111, "name": "Hill Climb"},
                    "pr_rank": 2,
                    "elapsed_time": 124,
                },
                {
                    "name": "River Path",
                    "segment": {"id": 222, "name": "River Path"},
                    "pr_rank": 1,
                    "elapsed_time": 88,
                },
                {
                    "name": "No Medal",
                    "segment": {"id": 333, "name": "No Medal"},
                    "pr_rank": None,
                    "elapsed_time": 75,
                },
            ]
        }

        lines = _extract_strava_segment_notables(activity)
        self.assertEqual(lines[0], "Strava PR: River Path (1:28)")
        self.assertEqual(lines[1], "Strava 2nd: Hill Climb (2:04)")
        self.assertEqual(len(lines), 2)

    def test_extract_strava_badges_from_achievements_and_notables(self) -> None:
        activity = {
            "achievement_count": 2,
            "segment_efforts": [
                {
                    "name": "Bridge Sprint",
                    "segment": {"id": 999, "name": "Bridge Sprint"},
                    "achievements": [
                        {"type": "segment_effort_pr", "rank": 1},
                    ],
                }
            ],
        }
        segment_notables = ["Strava PR: Bridge Sprint (1:15)"]
        badges = _extract_strava_badges(activity, segment_notables=segment_notables)
        self.assertIn("Strava: Segment Effort Pr PR - Bridge Sprint", badges)
        self.assertIn("Strava PR: Bridge Sprint (1:15)", badges)


class TestStrengthProfileBehavior(unittest.TestCase):
    def test_strength_profile_matches_weight_training_sport_type(self) -> None:
        settings = SimpleNamespace(
            profile_trail_gain_per_mile_ft=220.0,
            profile_long_run_miles=10.0,
            home_latitude=None,
            home_longitude=None,
            home_radius_miles=10.0,
        )
        activity = {
            "sport_type": "Weight Training",
            "type": "Workout",
        }
        reasons = _profile_match_reasons("strength_training", activity, settings)
        self.assertTrue(reasons)
        self.assertIn("sport_type=Weight Training", reasons)

    def test_strength_profile_update_payload_sets_private_and_title(self) -> None:
        payload = _profile_activity_update_payload(
            "strength_training",
            {"id": 123, "sport_type": "WeightTraining"},
            "Sets: 5 | Reps: 5",
        )
        self.assertEqual(payload.get("description"), "Sets: 5 | Reps: 5")
        self.assertTrue(payload.get("private"))
        self.assertEqual(payload.get("name"), "Strength Training")


if __name__ == "__main__":
    unittest.main()
