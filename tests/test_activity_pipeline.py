import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from chronicle.activity_pipeline import (
    CHALLENGE_300_30_PROFILE_ID,
    GARMIN_LOGIN_BLOCKED_UNTIL_KEY,
    GARMIN_LOGIN_LAST_ERROR_KEY,
    ROYALE_HILL_LATITUDE,
    ROYALE_HILL_LONGITUDE,
    _build_300_30_challenge_context,
    _build_description_context,
    _count_radius_entries,
    _extract_activity_smashrun_badges,
    _extract_strava_badges,
    _extract_activity_garmin_badges,
    _extract_strava_segment_notables,
    _ensure_garmin_ready,
    _get_garmin_client,
    _profile_activity_update_payload,
    _profile_match_reasons,
    _resolve_cycle_time_context,
    _select_activity_profile,
    preview_specific_profile_against_activity,
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

    def test_description_context_uses_aligned_garmin_activity_hr_and_cadence(self) -> None:
        context = _build_description_context(
            detailed_activity={
                "id": 17455368360,
                "name": "Lunch Run",
                "type": "Run",
                "sport_type": "Run",
                "distance": 8046.72,
                "moving_time": 2400,
                "elapsed_time": 2460,
                "average_speed": 3.3528,
                "average_heartrate": 151,
                "average_cadence": 88.0,
                "start_latlng": [33.75, -84.39],
            },
            training={
                "average_hr": 143,
                "running_cadence": 176,
                "_garmin_activity_aligned": True,
                "garmin_last_activity": {
                    "activity_id": 3002,
                    "average_hr": 167,
                    "cadence_spm": 182,
                },
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
        )

        self.assertEqual(context.get("activity", {}).get("average_hr"), 167)
        self.assertEqual(context.get("activity", {}).get("cadence_spm"), 182)


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


class TestCycleTimeContext(unittest.TestCase):
    def test_resolve_cycle_time_context_uses_reference_activity_date(self) -> None:
        settings = SimpleNamespace(timezone="America/New_York")
        reference_utc = datetime(2026, 2, 15, 5, 30, 0, tzinfo=timezone.utc)

        _local_tz, now_local, now_utc, year_start_utc = _resolve_cycle_time_context(
            settings,
            reference_utc=reference_utc,
        )

        self.assertEqual(now_utc, reference_utc)
        self.assertEqual((now_local.year, now_local.month, now_local.day), (2026, 2, 15))
        self.assertEqual(year_start_utc.isoformat(), "2026-01-01T05:00:00+00:00")

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


class TestChallenge30030Context(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self._old_runtime = os.environ.get("RUNTIME_DB_FILE")
        os.environ["RUNTIME_DB_FILE"] = "runtime_state.db"
        self.settings = SimpleNamespace(
            timezone="America/New_York",
            processed_log_file=Path(self.temp_dir.name) / "processed_activities.log",
            enable_service_result_cache=False,
            enable_service_call_budget=False,
            service_cache_ttl_seconds=600,
            service_retry_count=0,
            service_retry_backoff_seconds=1,
            service_cooldown_base_seconds=60,
            service_cooldown_max_seconds=1800,
        )

    def tearDown(self) -> None:
        if self._old_runtime is None:
            os.environ.pop("RUNTIME_DB_FILE", None)
        else:
            os.environ["RUNTIME_DB_FILE"] = self._old_runtime
        self.temp_dir.cleanup()

    def test_count_radius_entries_counts_outside_to_inside_transitions(self) -> None:
        points = [
            (34.24500, ROYALE_HILL_LONGITUDE),
            (ROYALE_HILL_LATITUDE, ROYALE_HILL_LONGITUDE),
            (ROYALE_HILL_LATITUDE, ROYALE_HILL_LONGITUDE),
            (34.24500, ROYALE_HILL_LONGITUDE),
            (ROYALE_HILL_LATITUDE, ROYALE_HILL_LONGITUDE),
        ]

        self.assertEqual(
            _count_radius_entries(
                points,
                latitude=ROYALE_HILL_LATITUDE,
                longitude=ROYALE_HILL_LONGITUDE,
                radius_feet=60.0,
            ),
            2,
        )

    def test_build_300_30_challenge_context_sums_run_day_totals_and_summits(self) -> None:
        detailed = {
            "id": 3003,
            "sport_type": "TrailRun",
            "type": "TrailRun",
            "start_date": "2026-05-02T12:00:00Z",
            "distance": 5 * 1609.34,
            "moving_time": 2400,
        }
        strava_activities = [
            {
                "id": "3001",
                "sport_type": "Run",
                "type": "Run",
                "start_date": "2026-05-01T12:00:00Z",
                "distance": 10 * 1609.34,
                "moving_time": 4800,
            },
            {
                "id": "3002",
                "sport_type": "Run",
                "type": "Run",
                "start_date": "2026-05-02T10:00:00Z",
                "distance": 4 * 1609.34,
                "moving_time": 1920,
            },
            {
                "id": "ride",
                "sport_type": "Ride",
                "type": "Ride",
                "start_date": "2026-05-02T11:00:00Z",
                "distance": 20 * 1609.34,
                "moving_time": 3600,
            },
        ]
        smashrun_activities = [
            {"activityId": 1, "startDateTimeUtc": "2026-05-01T12:00:00Z", "elevationGainFeet": 1000},
            {"activityId": 2, "startDateTimeUtc": "2026-05-02T10:00:00Z", "elevationGainFeet": 300},
            {"activityId": 3, "startDateTimeUtc": "2026-05-02T12:00:00Z", "elevationGainFeet": 400},
            {"activityId": 4, "startDateTimeUtc": "2026-06-01T12:00:00Z", "elevationGainFeet": 9999},
        ]
        strava_client = MagicMock()
        strava_client.get_activity_streams.return_value = {
            "latlng": {
                "data": [
                    [34.24500, ROYALE_HILL_LONGITUDE],
                    [ROYALE_HILL_LATITUDE, ROYALE_HILL_LONGITUDE],
                    [34.24500, ROYALE_HILL_LONGITUDE],
                    [ROYALE_HILL_LATITUDE, ROYALE_HILL_LONGITUDE],
                ]
            }
        }

        context = _build_300_30_challenge_context(
            self.settings,
            strava_client,
            detailed,
            strava_activities,
            smashrun_activities,
            profile_id=CHALLENGE_300_30_PROFILE_ID,
            service_state={},
        )

        self.assertTrue(context["active"])
        self.assertEqual(context["day"], 2)
        self.assertAlmostEqual(context["today"]["distance_miles"], 9.0)
        self.assertAlmostEqual(context["totals"]["distance_miles"], 19.0)
        self.assertEqual(context["today"]["elevation_feet"], 700)
        self.assertEqual(context["totals"]["elevation_feet"], 1700)
        self.assertEqual(context["today"]["run_count"], 2)
        self.assertEqual(context["totals"]["run_count"], 3)
        self.assertEqual(context["pace"]["daily_distance_miles"], 9.7)
        self.assertEqual(context["pace"]["daily_elevation_feet"], 937)
        self.assertEqual(context["pace"]["distance_delta_display"], "-0.4mi")
        self.assertEqual(context["pace"]["elevation_delta_display"], "-174'")
        self.assertEqual(context["pace"]["distance_status_emoji"], "🟡")
        self.assertEqual(context["pace"]["elevation_status_emoji"], "🔴")
        self.assertEqual(context["royale_hill"]["current_activity_summits"], 2)
        self.assertEqual(context["today"]["royale_hill_summits"], 2)
        self.assertEqual(context["totals"]["royale_hill_summits"], 2)
        strava_client.get_activity_streams.assert_called_once_with(3003)


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

    def test_onewheel_profile_update_payload_sets_ebike_title(self) -> None:
        payload = _profile_activity_update_payload(
            "onewheel",
            {"id": 123, "sport_type": "Ride", "type": "Ride"},
            "Onewheel metrics",
        )
        self.assertEqual(payload.get("description"), "Onewheel metrics")
        self.assertEqual(payload.get("type"), "EBikeRide")
        self.assertEqual(payload.get("name"), "Onewheel Float 🛹")

    def test_default_profile_update_payload_reverts_stale_onewheel_title_and_type_from_garmin(self) -> None:
        payload = _profile_activity_update_payload(
            "default",
            {"id": 123, "sport_type": "EBikeRide", "type": "EBikeRide", "name": "Onewheel Float 🛹"},
            "Miles 1.01",
            training={
                "_garmin_activity_aligned": True,
                "garmin_last_activity": {
                    "activity_type": "running",
                    "activity_name": "Forsyth County - Zone 2",
                },
            },
        )
        self.assertEqual(payload.get("description"), "Miles 1.01")
        self.assertEqual(payload.get("type"), "Run")
        self.assertEqual(payload.get("name"), "Forsyth County - Zone 2")

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


class TestProfileActivityPreview(unittest.TestCase):
    def test_preview_specific_profile_against_activity_respects_disabled_status(self) -> None:
        settings = SimpleNamespace(
            profile_trail_gain_per_mile_ft=220.0,
            profile_long_run_miles=10.0,
            home_latitude=None,
            home_longitude=None,
            home_radius_miles=10.0,
            timezone="America/New_York",
        )
        activity = {
            "id": 17571492798,
            "sport_type": "Walk",
            "type": "Walk",
            "name": "Neighborhood Walk",
            "moving_time": 1800,
            "start_date_local": "2026-03-06T18:10:00-05:00",
            "start_latlng": [34.24, -83.96],
        }
        profile = {
            "profile_id": "walk",
            "label": "Walk",
            "enabled": True,
            "priority": 40,
            "criteria": {
                "sport_type": ["walk"],
            },
        }

        preview = preview_specific_profile_against_activity(
            settings,
            activity,
            profile,
            training={"_garmin_activity_aligned": False},
            enabled_override=False,
        )

        self.assertTrue(preview["matched"])
        self.assertFalse(preview["would_process"])
        self.assertEqual(preview["reasons"][0], "profile disabled")

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

    def test_incline_treadmill_profile_ignores_unaligned_garmin_incline_context(self) -> None:
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
            "distance": 4200.0,
            "moving_time": 2100,
            "external_id": "garmin_ping_999",
            "device_name": "Garmin Forerunner 955",
            "name": "Morning Session",
        }
        training = {
            "_garmin_activity_aligned": False,
            "garmin_last_activity": {
                "activity_name": "Treadmill Incline",
                "activity_type": "incline_treadmill",
            },
        }
        reasons = _profile_match_reasons("incline_treadmill", activity, settings, training=training)
        self.assertEqual(reasons, [])

    def test_incline_treadmill_profile_uses_aligned_garmin_incline_context(self) -> None:
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
            "distance": 4200.0,
            "moving_time": 2100,
            "external_id": "garmin_ping_1000",
            "device_name": "Garmin Forerunner 955",
            "name": "Morning Session",
        }
        training = {
            "_garmin_activity_aligned": True,
            "garmin_last_activity": {
                "activity_name": "Treadmill Incline",
                "activity_type": "incline_treadmill",
            },
        }
        reasons = _profile_match_reasons("incline_treadmill", activity, settings, training=training)
        self.assertTrue(reasons)
        self.assertIn("incline treadmill activity name", reasons)

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

    def test_profile_selection_skips_disabled_profiles(self) -> None:
        settings = SimpleNamespace(
            profile_trail_gain_per_mile_ft=220.0,
            profile_long_run_miles=10.0,
            home_latitude=None,
            home_longitude=None,
            home_radius_miles=10.0,
        )
        profiles = [
            {"profile_id": "default", "label": "Default", "enabled": True, "priority": 0},
            {"profile_id": "race", "label": "Race", "enabled": False, "priority": 100},
        ]
        activity = {
            "sport_type": "Run",
            "type": "Run",
            "name": "City 10K race effort",
            "workout_type": 1,
        }

        with patch("chronicle.activity_pipeline.list_template_profiles", return_value=profiles):
            selected = _select_activity_profile(settings, activity)

        self.assertEqual(selected.get("profile_id"), "default")
        self.assertEqual(selected.get("reasons"), ["fallback"])

    def test_profile_selection_defaults_without_working_profile_fallback_for_processing(self) -> None:
        settings = SimpleNamespace(
            profile_trail_gain_per_mile_ft=220.0,
            profile_long_run_miles=10.0,
            home_latitude=None,
            home_longitude=None,
            home_radius_miles=10.0,
        )
        profiles = [
            {"profile_id": "default", "label": "Default", "enabled": True, "priority": 0},
            {"profile_id": "trail", "label": "Trail", "enabled": True, "priority": 70},
        ]
        activity = {
            "sport_type": "Run",
            "type": "Run",
            "name": "Neighborhood easy run",
            "distance": 4000.0,
            "elev_gain": 50.0,
        }

        with patch("chronicle.activity_pipeline.list_template_profiles", return_value=profiles), patch(
            "chronicle.activity_pipeline.get_working_template_profile",
            return_value={"profile_id": "trail", "label": "Trail", "enabled": True},
        ):
            selected = _select_activity_profile(settings, activity)

        self.assertEqual(selected.get("profile_id"), "default")
        self.assertEqual(selected.get("reasons"), ["fallback"])
        self.assertEqual(selected.get("working_profile_id"), "trail")
        self.assertEqual(selected.get("selection_mode"), "default_fallback")

    def test_profile_selection_can_fall_back_to_working_profile_for_preview(self) -> None:
        settings = SimpleNamespace(
            profile_trail_gain_per_mile_ft=220.0,
            profile_long_run_miles=10.0,
            home_latitude=None,
            home_longitude=None,
            home_radius_miles=10.0,
        )
        profiles = [
            {"profile_id": "default", "label": "Default", "enabled": True, "priority": 0},
            {"profile_id": "trail", "label": "Trail", "enabled": True, "priority": 70},
        ]
        activity = {
            "sport_type": "Run",
            "type": "Run",
            "name": "Neighborhood easy run",
            "distance": 4000.0,
            "elev_gain": 50.0,
        }

        with patch("chronicle.activity_pipeline.list_template_profiles", return_value=profiles), patch(
            "chronicle.activity_pipeline.get_working_template_profile",
            return_value={"profile_id": "trail", "label": "Trail", "enabled": True},
        ):
            selected = _select_activity_profile(settings, activity, allow_working_profile_fallback=True)

        self.assertEqual(selected.get("profile_id"), "trail")
        self.assertEqual(selected.get("reasons"), ["working_profile_fallback"])
        self.assertEqual(selected.get("working_profile_id"), "trail")
        self.assertEqual(selected.get("selection_mode"), "working_profile_fallback")

    def test_profile_selection_prefers_explicit_match_over_working_profile_fallback(self) -> None:
        settings = SimpleNamespace(
            profile_trail_gain_per_mile_ft=220.0,
            profile_long_run_miles=10.0,
            home_latitude=None,
            home_longitude=None,
            home_radius_miles=10.0,
        )
        profiles = [
            {"profile_id": "default", "label": "Default", "enabled": True, "priority": 0},
            {"profile_id": "trail", "label": "Trail", "enabled": True, "priority": 70},
            {"profile_id": "race", "label": "Race", "enabled": True, "priority": 100},
        ]
        activity = {
            "sport_type": "Run",
            "type": "Run",
            "name": "Neighborhood 10K race effort",
            "distance": 10000.0,
            "workout_type": 1,
        }

        with patch("chronicle.activity_pipeline.list_template_profiles", return_value=profiles), patch(
            "chronicle.activity_pipeline.get_working_template_profile",
            return_value={"profile_id": "trail", "label": "Trail", "enabled": True},
        ):
            selected = _select_activity_profile(settings, activity)

        self.assertEqual(selected.get("profile_id"), "race")
        self.assertEqual(selected.get("selection_mode"), "criteria_match")
        self.assertEqual(selected.get("working_profile_id"), "trail")

    def test_profile_selection_uses_criteria_for_custom_profile(self) -> None:
        settings = SimpleNamespace(
            profile_trail_gain_per_mile_ft=220.0,
            profile_long_run_miles=10.0,
            home_latitude=None,
            home_longitude=None,
            home_radius_miles=10.0,
        )
        profiles = [
            {"profile_id": "default", "label": "Default", "enabled": True, "priority": 0},
            {
                "profile_id": "custom_distance_run",
                "label": "Custom Distance Run",
                "enabled": True,
                "priority": 200,
                "criteria": {
                    "sport_type": "run",
                    "distance_miles_min": 5,
                    "trainer": False,
                },
            },
        ]
        activity = {
            "sport_type": "Run",
            "type": "Run",
            "distance": 10000.0,
            "trainer": False,
            "start_latlng": [40.0, -74.0],
        }

        with patch("chronicle.activity_pipeline.list_template_profiles", return_value=profiles):
            selected = _select_activity_profile(settings, activity)

        self.assertEqual(selected.get("profile_id"), "custom_distance_run")
        self.assertTrue(selected.get("reasons"))

    def test_profile_selection_criteria_can_override_builtin_matching(self) -> None:
        settings = SimpleNamespace(
            profile_trail_gain_per_mile_ft=220.0,
            profile_long_run_miles=10.0,
            home_latitude=None,
            home_longitude=None,
            home_radius_miles=10.0,
        )
        profiles = [
            {"profile_id": "default", "label": "Default", "enabled": True, "priority": 0},
            {
                "profile_id": "treadmill",
                "label": "Treadmill",
                "enabled": True,
                "priority": 120,
                "criteria": {"sport_type": "walk", "has_gps": True, "trainer": False},
            },
        ]
        activity = {
            "sport_type": "Run",
            "type": "Run",
            "trainer": True,
            "start_latlng": [],
            "distance": 3000.0,
            "moving_time": 1800,
            "name": "Treadmill",
        }

        with patch("chronicle.activity_pipeline.list_template_profiles", return_value=profiles):
            selected = _select_activity_profile(settings, activity)

        self.assertEqual(selected.get("profile_id"), "default")

    def test_strength_activity_is_not_misidentified_as_treadmill(self) -> None:
        settings = SimpleNamespace(
            profile_trail_gain_per_mile_ft=220.0,
            profile_long_run_miles=10.0,
            home_latitude=None,
            home_longitude=None,
            home_radius_miles=10.0,
        )
        profiles = [
            {"profile_id": "default", "label": "Default", "enabled": True, "priority": 0},
            {"profile_id": "incline_treadmill", "label": "Incline Treadmill", "enabled": True, "priority": 110},
            {"profile_id": "treadmill", "label": "Treadmill", "enabled": True, "priority": 100},
            {"profile_id": "strength_training", "label": "Strength Training", "enabled": True, "priority": 75},
        ]
        activity = {
            "sport_type": "Run",
            "type": "Run",
            "trainer": True,
            "start_latlng": [],
            "distance": 0.0,
            "moving_time": 1300,
            "name": "Treadmill incline strength training",
            "external_id": "garmin_ping_strength",
            "device_name": "Garmin Forerunner",
        }
        training = {
            "_garmin_activity_aligned": True,
            "garmin_last_activity": {
                "activity_type": "strength_training",
                "total_sets": 12,
            },
        }

        with patch("chronicle.activity_pipeline.list_template_profiles", return_value=profiles):
            selected = _select_activity_profile(settings, activity, training=training)

        self.assertEqual(selected.get("profile_id"), "strength_training")
        self.assertIn("garmin activity indicates strength", selected.get("reasons", []))

    def test_profile_selection_routes_vescdash_other_activity_to_onewheel(self) -> None:
        settings = SimpleNamespace(
            profile_trail_gain_per_mile_ft=220.0,
            profile_long_run_miles=10.0,
            home_latitude=None,
            home_longitude=None,
            home_radius_miles=10.0,
        )
        profiles = [
            {"profile_id": "default", "label": "Default", "enabled": True, "priority": 0},
            {
                "profile_id": "onewheel",
                "label": "Onewheel",
                "enabled": True,
                "priority": 79,
                "criteria": {
                    "kind": "activity",
                    "all_of": [
                        {"garmin_activity_type_in": ["other"]},
                        {
                            "garmin_connectiq_app_ids_any": [
                                "0432631a-d5e3-4272-a072-fa8c7e24c483",
                            ]
                        },
                    ],
                },
            },
        ]
        activity = {
            "sport_type": "Ride",
            "type": "Ride",
            "name": "Forsyth County EUC riding",
            "distance": 1451.89,
            "moving_time": 421,
        }
        training = {
            "_garmin_activity_aligned": True,
            "garmin_last_activity": {
                "activity_type": "other",
                "connectiq_app_ids": ["0432631a-d5e3-4272-a072-fa8c7e24c483"],
            },
        }

        with patch("chronicle.activity_pipeline.list_template_profiles", return_value=profiles):
            selected = _select_activity_profile(settings, activity, training=training)

        self.assertEqual(selected.get("profile_id"), "onewheel")
        self.assertIn("garmin_connectiq_app_id match", selected.get("reasons", []))

    def test_profile_selection_does_not_route_run_to_onewheel_without_aligned_garmin_activity(self) -> None:
        settings = SimpleNamespace(
            profile_trail_gain_per_mile_ft=220.0,
            profile_long_run_miles=10.0,
            home_latitude=None,
            home_longitude=None,
            home_radius_miles=10.0,
        )
        profiles = [
            {"profile_id": "default", "label": "Default", "enabled": True, "priority": 0},
            {
                "profile_id": "onewheel",
                "label": "Onewheel",
                "enabled": True,
                "priority": 79,
                "criteria": {
                    "kind": "activity",
                    "all_of": [
                        {"garmin_activity_type_in": ["other"]},
                        {
                            "garmin_connectiq_app_ids_any": [
                                "0432631a-d5e3-4272-a072-fa8c7e24c483",
                            ]
                        },
                    ],
                },
            },
        ]
        activity = {
            "sport_type": "Run",
            "type": "Run",
            "name": "Forsyth County - Zone 2",
            "distance": 12000.0,
            "moving_time": 3600,
        }
        training = {
            "_garmin_activity_aligned": False,
            "garmin_last_activity": {
                "activity_type": "other",
                "connectiq_app_ids": ["0432631a-d5e3-4272-a072-fa8c7e24c483"],
            },
        }

        with patch("chronicle.activity_pipeline.list_template_profiles", return_value=profiles):
            selected = _select_activity_profile(settings, activity, training=training)

        self.assertEqual(selected.get("profile_id"), "default")

    def test_profile_selection_does_not_route_mutated_onewheel_title_when_garmin_alignment_is_running(self) -> None:
        settings = SimpleNamespace(
            profile_trail_gain_per_mile_ft=220.0,
            profile_long_run_miles=10.0,
            home_latitude=None,
            home_longitude=None,
            home_radius_miles=10.0,
        )
        profiles = [
            {"profile_id": "default", "label": "Default", "enabled": True, "priority": 0},
            {
                "profile_id": "onewheel",
                "label": "Onewheel",
                "enabled": True,
                "priority": 79,
                "criteria": {
                    "kind": "activity",
                    "all_of": [
                        {"garmin_activity_type_in": ["other"]},
                        {
                            "garmin_connectiq_app_ids_any": [
                                "0432631a-d5e3-4272-a072-fa8c7e24c483",
                            ]
                        },
                    ],
                },
            },
        ]
        activity = {
            "sport_type": "EBikeRide",
            "type": "EBikeRide",
            "name": "Onewheel Float 🛹",
            "description": "🛞 Onewheel ride on the N/A",
            "distance": 1622.0,
            "moving_time": 645,
        }
        training = {
            "_garmin_activity_aligned": True,
            "garmin_last_activity": {
                "activity_type": "running",
                "connectiq_app_ids": [],
            },
        }

        with patch("chronicle.activity_pipeline.list_template_profiles", return_value=profiles):
            selected = _select_activity_profile(settings, activity, training=training)

        self.assertEqual(selected.get("profile_id"), "default")


class TestExecutableProfileCriteria(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = SimpleNamespace(
            profile_trail_gain_per_mile_ft=220.0,
            profile_long_run_miles=10.0,
            home_latitude=34.241946,
            home_longitude=-83.964154,
            home_radius_miles=10.0,
            timezone="America/New_York",
        )

    def test_profile_match_reasons_supports_strava_tags_and_time_windows(self) -> None:
        activity = {
            "sport_type": "Run",
            "type": "Run",
            "name": "Evening Commute Run",
            "commute": True,
            "moving_time": 2400,
            "start_date_local": "2026-03-02T18:15:00-05:00",
            "start_latlng": [34.241946, -83.964154],
        }
        criteria = {
            "sport_type": ["run"],
            "strava_tags_any": ["commute"],
            "time_of_day_after": "17:00",
            "time_of_day_before": "20:00",
            "day_of_week_in": ["monday"],
        }

        reasons = _profile_match_reasons("evening_commute", activity, self.settings, criteria=criteria)
        self.assertIn("sport_type=Run", reasons)
        self.assertIn("strava_tags_any matched", reasons)
        self.assertIn("day_of_week=0", reasons)
        self.assertIn("time_of_day=1095 >= 1020", reasons)
        self.assertIn("time_of_day=1095 <= 1200", reasons)

    def test_profile_match_reasons_supports_local_date_windows(self) -> None:
        activity = {
            "sport_type": "TrailRun",
            "type": "TrailRun",
            "name": "May hills",
            "start_date_local": "2026-05-15T06:30:00-04:00",
            "moving_time": 3600,
        }
        criteria = {
            "sport_type": ["run", "trailrun"],
            "date_local_on_or_after": "2026-05-01",
            "date_local_before": "2026-06-01",
        }

        reasons = _profile_match_reasons("may_challenge", activity, self.settings, criteria=criteria)
        self.assertIn("sport_type=TrailRun", reasons)
        self.assertIn("date_local=2026-05-15 >= 2026-05-01", reasons)
        self.assertIn("date_local=2026-05-15 < 2026-06-01", reasons)

    def test_profile_match_reasons_supports_geofence_within(self) -> None:
        activity = {
            "sport_type": "Walk",
            "type": "Walk",
            "name": "Lunch walk",
            "start_latlng": [34.2420, -83.9640],
        }
        criteria = {
            "sport_type": ["walk"],
            "start_geofence": {
                "latitude": 34.241946,
                "longitude": -83.964154,
                "radius_miles": 0.25,
                "mode": "within",
            },
        }

        reasons = _profile_match_reasons("home_walk", activity, self.settings, criteria=criteria)
        self.assertIn("sport_type=Walk", reasons)
        self.assertIn("start_geofence within 0.25mi", reasons)

    def test_profile_match_reasons_supports_geofence_outside(self) -> None:
        activity = {
            "sport_type": "Run",
            "type": "Run",
            "name": "Destination run",
            "start_latlng": [35.241946, -84.964154],
        }
        criteria = {
            "sport_type": ["run"],
            "start_geofence": {
                "latitude": 34.241946,
                "longitude": -83.964154,
                "radius_miles": 5.0,
                "mode": "outside",
            },
        }

        reasons = _profile_match_reasons("destination_run", activity, self.settings, criteria=criteria)
        self.assertIn("start_geofence outside 5.00mi", reasons)

    def test_profile_match_reasons_supports_name_and_text_contains_any(self) -> None:
        activity = {
            "sport_type": "Run",
            "type": "Run",
            "name": "Sunrise Badge Chase",
            "description": "Trying for a local legend badge before work",
            "moving_time": 1800,
        }
        criteria = {
            "name_contains_any": ["badge", "race"],
            "text_contains_any": ["legend", "commute"],
            "moving_time_minutes_min": 25,
            "moving_time_minutes_max": 35,
        }

        reasons = _profile_match_reasons("badge_chase", activity, self.settings, criteria=criteria)
        self.assertIn("name_contains_any matched", reasons)
        self.assertIn("text_contains_any matched", reasons)
        self.assertIn("moving_time=30min >= 25min", reasons)
        self.assertIn("moving_time=30min <= 35min", reasons)


class TestGarminClientLogin(unittest.TestCase):
    def _settings(self, tmp_path: Path) -> SimpleNamespace:
        return SimpleNamespace(
            enable_garmin=True,
            garmin_email="runner@example.com",
            garmin_password="secret",
            state_dir=tmp_path,
            processed_log_file=tmp_path / "processed_activities.log",
        )

    def test_get_garmin_client_uses_tokenstore_path_and_clears_rate_limit_state(self) -> None:
        tmp_path = Path(self.id().replace(".", "_"))
        settings = self._settings(tmp_path)
        client = MagicMock()

        with patch("chronicle.activity_pipeline.get_runtime_value", return_value=None), patch(
            "chronicle.activity_pipeline.delete_runtime_value"
        ) as delete_runtime_value, patch("garminconnect.Garmin", return_value=client):
            result = _get_garmin_client(settings)

        self.assertIs(result, client)
        client.login.assert_called_once_with(str(tmp_path / "garmin_tokens"))
        delete_runtime_value.assert_has_calls(
            [
                call(settings.processed_log_file, GARMIN_LOGIN_BLOCKED_UNTIL_KEY),
                call(settings.processed_log_file, GARMIN_LOGIN_LAST_ERROR_KEY),
            ]
        )

    def test_get_garmin_client_sets_runtime_cooldown_on_rate_limit(self) -> None:
        tmp_path = Path(self.id().replace(".", "_"))
        settings = self._settings(tmp_path)

        from garminconnect import GarminConnectTooManyRequestsError

        client = MagicMock()
        client.login.side_effect = GarminConnectTooManyRequestsError("rate limited")

        with patch("chronicle.activity_pipeline.get_runtime_value", return_value=None), patch(
            "chronicle.activity_pipeline.set_runtime_values"
        ) as set_runtime_values, patch(
            "chronicle.activity_pipeline._garmin_login_retry_cooldown_seconds",
            return_value=900,
        ), patch("garminconnect.Garmin", return_value=client):
            result = _get_garmin_client(settings)

        self.assertIsNone(result)
        set_runtime_values.assert_called_once()
        _, stored_values = set_runtime_values.call_args.args
        self.assertIn(GARMIN_LOGIN_BLOCKED_UNTIL_KEY, stored_values)
        self.assertEqual(stored_values[GARMIN_LOGIN_LAST_ERROR_KEY], "rate limited")
        blocked_until = datetime.fromisoformat(stored_values[GARMIN_LOGIN_BLOCKED_UNTIL_KEY])
        self.assertGreater(blocked_until, datetime.now(timezone.utc))

    def test_get_garmin_client_skips_login_while_rate_limited(self) -> None:
        tmp_path = Path(self.id().replace(".", "_"))
        settings = self._settings(tmp_path)
        blocked_until = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

        with patch("chronicle.activity_pipeline.get_runtime_value", return_value=blocked_until), patch(
            "garminconnect.Garmin"
        ) as garmin_cls:
            result = _get_garmin_client(settings)

        self.assertIsNone(result)
        garmin_cls.assert_not_called()

    def test_ensure_garmin_ready_raises_retryable_error_while_rate_limited(self) -> None:
        tmp_path = Path(self.id().replace(".", "_"))
        settings = self._settings(tmp_path)
        blocked_until = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

        def runtime_lookup(_path: Path, key: str, default: object = None) -> object:
            if key == GARMIN_LOGIN_BLOCKED_UNTIL_KEY:
                return blocked_until
            if key == GARMIN_LOGIN_LAST_ERROR_KEY:
                return "Too many login attempts. Please wait a few minutes before trying again."
            return default

        with patch("chronicle.activity_pipeline.get_runtime_value", side_effect=runtime_lookup):
            with self.assertRaisesRegex(RuntimeError, "rate-limited until"):
                _ensure_garmin_ready(settings, None)

    def test_ensure_garmin_ready_raises_on_generic_login_failure(self) -> None:
        tmp_path = Path(self.id().replace(".", "_"))
        settings = self._settings(tmp_path)

        def runtime_lookup(_path: Path, key: str, default: object = None) -> object:
            if key == GARMIN_LOGIN_LAST_ERROR_KEY:
                return "Authentication failed (401 Unauthorized)."
            return default

        with patch("chronicle.activity_pipeline.get_runtime_value", side_effect=runtime_lookup):
            with self.assertRaisesRegex(RuntimeError, "Authentication failed"):
                _ensure_garmin_ready(settings, None)


if __name__ == "__main__":
    unittest.main()
