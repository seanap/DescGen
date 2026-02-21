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
        self.assertEqual(payload.get("name"), "Strength Workout")
        self.assertEqual(payload.get("type"), "Workout")

    def test_strength_profile_matches_workout_sport_type(self) -> None:
        settings = SimpleNamespace(
            profile_trail_gain_per_mile_ft=220.0,
            profile_long_run_miles=10.0,
            home_latitude=None,
            home_longitude=None,
            home_radius_miles=10.0,
        )
        activity = {
            "sport_type": "Workout",
            "type": "Workout",
            "trainer": True,
            "start_latlng": [],
            "distance": 0.0,
            "moving_time": 900,
        }
        reasons = _profile_match_reasons("strength_training", activity, settings)
        self.assertIn("sport_type=Workout", reasons)

    def test_strength_profile_matches_strength_like_walk_session(self) -> None:
        settings = SimpleNamespace(
            profile_trail_gain_per_mile_ft=220.0,
            profile_long_run_miles=10.0,
            home_latitude=None,
            home_longitude=None,
            home_radius_miles=10.0,
        )
        activity = {
            "sport_type": "Walk",
            "type": "Walk",
            "trainer": True,
            "start_latlng": [],
            "distance": 0.0,
            "moving_time": 137,
            "name": "Afternoon Strength Training",
            "external_id": "garmin_ping_537343661503",
            "device_name": "Garmin Forerunner 955",
        }
        reasons = _profile_match_reasons("strength_training", activity, settings)
        self.assertIn("strength keyword + indoor no-gps shape", reasons)

    def test_strength_profile_matches_from_aligned_garmin_strength_context(self) -> None:
        settings = SimpleNamespace(
            profile_trail_gain_per_mile_ft=220.0,
            profile_long_run_miles=10.0,
            home_latitude=None,
            home_longitude=None,
            home_radius_miles=10.0,
        )
        activity = {
            "sport_type": "Run",
            "type": "Run",
            "trainer": True,
            "start_latlng": [],
            "distance": 0.0,
            "moving_time": 137,
            "name": "Morning",
        }
        training = {
            "_garmin_activity_aligned": True,
            "garmin_last_activity": {
                "activity_type": "strength_training",
                "total_sets": 12,
                "total_reps": 96,
            },
        }
        reasons = _profile_match_reasons("strength_training", activity, settings, training=training)
        self.assertIn("garmin activity indicates strength", reasons)

    def test_strength_profile_handles_na_strings_without_type_error(self) -> None:
        settings = SimpleNamespace(
            profile_trail_gain_per_mile_ft=220.0,
            profile_long_run_miles=10.0,
            home_latitude=None,
            home_longitude=None,
            home_radius_miles=10.0,
        )
        activity = {
            "sport_type": "Run",
            "type": "Run",
            "trainer": True,
            "start_latlng": [],
            "distance": 0.0,
            "moving_time": 137,
            "name": "Morning",
        }
        training = {
            "_garmin_activity_aligned": True,
            "garmin_last_activity": {
                "activity_type": "running",
                "total_sets": "N/A",
                "active_sets": "N/A",
                "total_reps": "N/A",
                "strength_summary_sets": [],
                "exercise_sets": [{"set_type": "REST", "reps": "N/A"}],
            },
        }
        reasons = _profile_match_reasons("strength_training", activity, settings, training=training)
        self.assertEqual(reasons, [])


class TestInclineTreadmillProfileBehavior(unittest.TestCase):
    def test_incline_treadmill_profile_matches_garmin_indoor_signals(self) -> None:
        settings = SimpleNamespace(
            profile_trail_gain_per_mile_ft=220.0,
            profile_long_run_miles=10.0,
            home_latitude=None,
            home_longitude=None,
            home_radius_miles=10.0,
        )
        activity = {
            "sport_type": "Run",
            "type": "Run",
            "trainer": True,
            "start_latlng": [],
            "distance": 2575.0,
            "moving_time": 2402,
            "external_id": "garmin_ping_476817910857",
            "device_name": "Garmin Forerunner 955",
            "name": "Low Aerobic 140-150 HR",
        }
        reasons = _profile_match_reasons("incline_treadmill", activity, settings)
        self.assertTrue(reasons)
        self.assertIn("garmin_ping external_id + no GPS", reasons)

    def test_incline_treadmill_profile_skips_short_non_treadmill_trainer_walk(self) -> None:
        settings = SimpleNamespace(
            profile_trail_gain_per_mile_ft=220.0,
            profile_long_run_miles=10.0,
            home_latitude=None,
            home_longitude=None,
            home_radius_miles=10.0,
        )
        activity = {
            "sport_type": "Walk",
            "type": "Walk",
            "trainer": True,
            "start_latlng": [],
            "distance": 0.0,
            "moving_time": 137,
            "external_id": "garmin_ping_537343661503",
            "device_name": "Garmin Forerunner 955",
            "name": "Afternoon Strength Training",
        }
        reasons = _profile_match_reasons("incline_treadmill", activity, settings)
        self.assertEqual(reasons, [])

    def test_incline_treadmill_profile_skips_when_aligned_garmin_strength_context(self) -> None:
        settings = SimpleNamespace(
            profile_trail_gain_per_mile_ft=220.0,
            profile_long_run_miles=10.0,
            home_latitude=None,
            home_longitude=None,
            home_radius_miles=10.0,
        )
        activity = {
            "sport_type": "Run",
            "type": "Run",
            "trainer": True,
            "start_latlng": [],
            "distance": 0.0,
            "moving_time": 137,
            "external_id": "garmin_ping_537343661503",
            "device_name": "Garmin Forerunner 955",
            "name": "Morning Session",
        }
        training = {
            "_garmin_activity_aligned": True,
            "garmin_last_activity": {
                "activity_type": "strength_training",
                "total_sets": 10,
            },
        }
        reasons = _profile_match_reasons("incline_treadmill", activity, settings, training=training)
        self.assertEqual(reasons, [])

    def test_incline_treadmill_profile_update_payload_sets_walk_title_and_trainer(self) -> None:
        payload = _profile_activity_update_payload(
            "incline_treadmill",
            {"id": 123, "sport_type": "Run", "type": "Run", "average_speed": 1.07},
            "∠ Incline: 15%",
        )
        self.assertEqual(payload.get("description"), "∠ Incline: 15%")
        self.assertEqual(payload.get("type"), "Walk")
        self.assertEqual(payload.get("name"), "Max Incline Treadmill Walk")
        self.assertTrue(payload.get("trainer"))


class TestWalkProfileBehavior(unittest.TestCase):
    def test_walk_profile_matches_outdoor_walk_with_gps(self) -> None:
        settings = SimpleNamespace(
            profile_trail_gain_per_mile_ft=220.0,
            profile_long_run_miles=10.0,
            home_latitude=None,
            home_longitude=None,
            home_radius_miles=10.0,
        )
        activity = {
            "sport_type": "Walk",
            "type": "Walk",
            "trainer": False,
            "start_latlng": [34.241946, -83.964154],
        }
        reasons = _profile_match_reasons("walk", activity, settings)
        self.assertEqual(reasons, ["sport_type=Walk + GPS + trainer=false"])

    def test_walk_profile_does_not_match_treadmill_walk(self) -> None:
        settings = SimpleNamespace(
            profile_trail_gain_per_mile_ft=220.0,
            profile_long_run_miles=10.0,
            home_latitude=None,
            home_longitude=None,
            home_radius_miles=10.0,
        )
        activity = {
            "sport_type": "Walk",
            "type": "Walk",
            "trainer": True,
            "start_latlng": [],
        }
        reasons = _profile_match_reasons("walk", activity, settings)
        self.assertEqual(reasons, [])

    def test_treadmill_profile_does_not_match_short_stationary_strength_like_session(self) -> None:
        settings = SimpleNamespace(
            profile_trail_gain_per_mile_ft=220.0,
            profile_long_run_miles=10.0,
            home_latitude=None,
            home_longitude=None,
            home_radius_miles=10.0,
        )
        activity = {
            "sport_type": "Walk",
            "type": "Walk",
            "trainer": True,
            "start_latlng": [],
            "distance": 0.0,
            "moving_time": 137,
            "name": "Afternoon Strength Training",
        }
        reasons = _profile_match_reasons("treadmill", activity, settings)
        self.assertEqual(reasons, [])


if __name__ == "__main__":
    unittest.main()
