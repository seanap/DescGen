import unittest
from types import SimpleNamespace
from unittest.mock import patch

from chronicle.activity_pipeline import (
    _build_description_context,
    _extract_activity_smashrun_badges,
    _extract_strava_badges,
    _extract_activity_garmin_badges,
    _extract_strava_segment_notables,
    _profile_activity_update_payload,
    _profile_match_reasons,
    _select_activity_profile,
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


class TestActivityGarminBadges(unittest.TestCase):
    def test_extract_activity_garmin_badges_filters_by_activity_id_and_dedupes(self) -> None:
        rows = [
            {
                "badgeName": "February Weekend 10K",
                "badgeAssocType": "activityId",
                "badgeAssocDataId": "21939412525",
            },
            {
                "badgeName": "February Weekend 10K",
                "badgeAssocType": "activityId",
                "badgeAssocDataId": "18340434430",
            },
            {
                "badgeName": "February Weekend 10K",
                "badgeAssocType": "activityId",
                "badgeAssocDataId": "21939412525",
            },
            {
                "badgeName": "Run Streak 400",
                "badgeAssocType": "daily",
                "badgeAssocDataId": "2026-02-22",
            },
        ]
        badges = _extract_activity_garmin_badges(rows, garmin_activity_id=21939412525)
        self.assertEqual(badges, ["February Weekend 10K"])

    def test_extract_activity_garmin_badges_supports_normalized_keys(self) -> None:
        rows = [
            {
                "badge_name": "March Weekend 5K",
                "badge_assoc_type": "activityId",
                "badge_assoc_data_id": "21939412525",
            },
        ]
        badges = _extract_activity_garmin_badges(rows, garmin_activity_id="21939412525")
        self.assertEqual(badges, ["March Weekend 5K"])

    def test_description_context_exposes_activity_badges(self) -> None:
        context = _build_description_context(
            detailed_activity={
                "id": 777,
                "name": "Treadmill",
                "type": "Run",
                "sport_type": "Run",
                "distance": 3218.68,
                "moving_time": 1500,
                "elapsed_time": 1500,
                "average_speed": 2.145,
                "trainer": True,
                "start_latlng": [],
            },
            training={
                "garmin_badges": ["Garmin: February Weekend 10K"],
                "garmin_badges_raw": [
                    {
                        "badgeName": "February Weekend 10K",
                        "badgeAssocType": "activityId",
                        "badgeAssocDataId": "21939412525",
                    },
                    {
                        "badgeName": "March Weekend 5K",
                        "badgeAssocType": "activityId",
                        "badgeAssocDataId": "19999999999",
                    },
                ],
                "garmin_last_activity": {"activity_id": 21939412525},
                "garmin_segment_notables": [],
            },
            intervals_payload={},
            week={"gap": "8:00/mi", "distance": 10.0, "elevation": 100.0, "duration": "1:20:00", "beers_earned": 6.0, "calories": 1000, "run_count": 2},
            month={"gap": "8:10/mi", "distance": 40.0, "elevation": 400.0, "duration": "5:20:00", "beers_earned": 25.0, "calories": 4000, "run_count": 8},
            year={"gap": "8:20/mi", "distance": 80.0, "elevation": 800.0, "duration": "10:40:00", "beers_earned": 50.0, "calories": 8000, "run_count": 16},
            longest_streak=None,
            notables=[],
            latest_elevation_feet=None,
            misery_index=None,
            misery_index_description=None,
            air_quality_index=None,
            aqi_description=None,
            smashrun_activity={"activityId": 99887766, "distance": 3218.68, "duration": 1500},
            smashrun_badges=[
                {"badgeName": "Two by 365 by 10k", "activityId": 99887766},
                {"badgeName": "Not This Badge", "activityId": 99887765},
            ],
        )
        self.assertEqual(context.get("activity_badges"), ["February Weekend 10K"])
        self.assertEqual(context.get("garmin", {}).get("activity_badges"), ["February Weekend 10K"])
        self.assertEqual(context.get("smashrun_activity_badges"), ["Two by 365 by 10k"])
        self.assertEqual(context.get("smashrun", {}).get("activity_badges"), ["Two by 365 by 10k"])


class TestActivitySmashrunBadges(unittest.TestCase):
    def test_extract_activity_smashrun_badges_matches_smashrun_and_strava_ids(self) -> None:
        rows = [
            {"badgeName": "Two by 365 by 10k", "activityId": 99887766},
            {"badgeName": "Smashrun and Strava Linked", "stravaActivityId": "777"},
            {"badgeName": "Not This One", "activityId": 111111},
            {"badgeName": "Two by 365 by 10k", "activityId": 99887766},
            {"badgeName": "No Association"},
        ]

        badges = _extract_activity_smashrun_badges(
            rows,
            smashrun_activity_id=99887766,
            strava_activity_id=777,
        )
        self.assertEqual(badges, ["Two by 365 by 10k", "Smashrun and Strava Linked"])

    def test_extract_activity_smashrun_badges_supports_activity_list_shapes(self) -> None:
        rows = [
            {"badgeName": "List Associated Badge", "activityIds": ["99887766", "123"]},
            {"badgeName": "Nested Associated Badge", "activities": [{"id": 777}, {"id": 42}]},
        ]

        badges = _extract_activity_smashrun_badges(
            rows,
            smashrun_activity_id="99887766",
            strava_activity_id="777",
        )
        self.assertEqual(badges, ["List Associated Badge", "Nested Associated Badge"])


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
    def test_incline_treadmill_profile_matches_custom_name_and_garmin_indoor_signals(self) -> None:
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
            "name": "Treadmill incline",
        }
        reasons = _profile_match_reasons("incline_treadmill", activity, settings)
        self.assertTrue(reasons)
        self.assertIn("incline treadmill activity name", reasons)
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
        self.assertEqual(payload.get("name"), "Max Incline Treadmill")
        self.assertTrue(payload.get("trainer"))

    def test_incline_treadmill_profile_skips_standard_treadmill_name(self) -> None:
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
            "name": "Treadmill",
        }
        reasons = _profile_match_reasons("incline_treadmill", activity, settings)
        self.assertEqual(reasons, [])


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

    def test_treadmill_profile_update_payload_uses_generic_treadmill_title(self) -> None:
        payload = _profile_activity_update_payload(
            "treadmill",
            {"id": 123, "sport_type": "Run", "type": "Run", "average_speed": 1.07},
            "Treadmill steady effort",
        )
        self.assertEqual(payload.get("description"), "Treadmill steady effort")
        self.assertEqual(payload.get("type"), "Walk")
        self.assertEqual(payload.get("name"), "Treadmill Walk")
        self.assertTrue(payload.get("trainer"))


class TestTreadmillProfileRoutingBehavior(unittest.TestCase):
    def test_profile_selection_routes_standard_and_incline_treadmill_deterministically(self) -> None:
        settings = SimpleNamespace(
            profile_trail_gain_per_mile_ft=220.0,
            profile_long_run_miles=10.0,
            home_latitude=None,
            home_longitude=None,
            home_radius_miles=10.0,
        )
        enabled_profiles = [
            {"profile_id": "default", "label": "Default", "enabled": True, "priority": 0},
            {"profile_id": "incline_treadmill", "label": "Incline Treadmill", "enabled": True, "priority": 110},
            {"profile_id": "treadmill", "label": "Treadmill", "enabled": True, "priority": 100},
        ]
        standard_activity = {
            "sport_type": "Run",
            "type": "Run",
            "trainer": True,
            "start_latlng": [],
            "distance": 3000.0,
            "moving_time": 1800,
            "external_id": "garmin_ping_standard",
            "device_name": "Garmin Forerunner",
            "name": "Treadmill",
        }
        incline_activity = {
            "sport_type": "Run",
            "type": "Run",
            "trainer": True,
            "start_latlng": [],
            "distance": 3000.0,
            "moving_time": 1800,
            "external_id": "garmin_ping_incline",
            "device_name": "Garmin Forerunner",
            "name": "Treadmill incline",
        }

        with patch("chronicle.activity_pipeline.list_template_profiles", return_value=enabled_profiles):
            standard_selected = _select_activity_profile(settings, standard_activity)
            incline_selected = _select_activity_profile(settings, incline_activity)

        self.assertEqual(standard_selected.get("profile_id"), "treadmill")
        self.assertEqual(incline_selected.get("profile_id"), "incline_treadmill")


if __name__ == "__main__":
    unittest.main()
