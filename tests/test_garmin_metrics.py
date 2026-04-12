import unittest

from chronicle.stat_modules.garmin_metrics import (
    build_garmin_activity_context,
    fetch_training_status_and_scores,
    get_activity_context_for_strava_activity,
)


class _DummyGarminClient:
    def get_last_activity(self):
        return {
            "activityId": 21922402831,
            "startTimeGMT": "2026-02-15 11:42:00",
            "duration": 3519,
            "movingDuration": 3490,
            "elapsedDuration": 3724,
            "distance": 12912.0,
            "averageSpeed": 3.67,
            "maxSpeed": 5.46,
            "avgGradeAdjustedSpeed": 3.74,
            "averageHR": 149,
            "maxHR": 173,
            "averageRunningCadenceInStepsPerMinute": 176,
            "aerobicTrainingEffect": 4.1,
            "anaerobicTrainingEffect": 0.1,
            "trainingEffectLabel": "TEMPO",
            "avgPower": 262,
            "normPower": 271,
            "maxPower": 487,
            "elevationGain": 186.5,
            "elevationLoss": 184.2,
            "avgElevation": 156.0,
            "maxElevation": 226.0,
            "minElevation": 125.0,
            "avgGroundContactTime": 238.4,
            "avgVerticalRatio": 7.9,
            "avgVerticalOscillation": 85.0,
            "avgStrideLength": 1.2,
            "avgRespirationRate": 34.2,
            "maxRespirationRate": 47.8,
            "steps": 10341,
            "lapCount": 8,
            "totalSets": 2,
            "activeSets": 2,
            "totalReps": 47,
            "summarizedExerciseSets": [
                {
                    "category": "ROW",
                    "subCategory": "SEATED_CABLE_ROW",
                    "reps": 29,
                    "sets": 1,
                    "maxWeight": 80,
                    "duration": 52696,
                },
                {
                    "category": "DIP",
                    "subCategory": "BENCH_DIP",
                    "reps": 18,
                    "sets": 1,
                    "maxWeight": 0,
                    "duration": 53096,
                },
            ],
            "hrTimeInZone_1": 372,
            "hrTimeInZone_2": 1124,
            "powerTimeInZone_1": 298,
            "powerTimeInZone_2": 1244,
            "activityName": "Morning Run",
            "activityType": {"typeKey": "running"},
            "startTimeLocal": "2026-02-15 06:42:00",
            "segmentEfforts": [
                {
                    "segment": {"id": 1, "name": "Hill Sprint"},
                    "pr_rank": 3,
                    "elapsed_time": 107,
                },
                {
                    "segment": {"id": 1, "name": "Hill Sprint"},
                    "pr_rank": 2,
                    "elapsed_time": 101,
                },
                {
                    "segment": {"id": 2, "name": "River Path"},
                    "pr_rank": 1,
                    "elapsed_time": 88,
                },
            ],
        }

    def get_training_status(self, _end_date):
        return {
            "mostRecentVO2Max": {"generic": {"vo2MaxPreciseValue": 57.2}},
            "mostRecentTrainingStatus": {
                "latestTrainingStatusData": {
                    "3417115846": {
                        "trainingStatusFeedbackPhrase": "PRODUCTIVE_BUILDING",
                        "fitnessTrend": "IMPROVING",
                        "loadLevelTrend": "WITHIN_RANGE",
                        "weeklyTrainingLoad": 568,
                        "loadTunnelMin": 60,
                        "loadTunnelMax": 92,
                        "acuteTrainingLoadDTO": {
                            "acwrStatus": "OPTIMAL",
                            "dailyTrainingLoadChronic": 72,
                            "dailyTrainingLoadAcute": 78,
                            "dailyAcuteChronicWorkloadRatio": 1.12,
                            "acwrPercent": 112,
                        },
                    }
                }
            },
        }

    def get_rhr_day(self, _start_date):
        return {
            "allMetrics": {
                "metricsMap": {
                    "WELLNESS_RESTING_HEART_RATE": [{"value": 47}],
                }
            }
        }

    def get_training_readiness(self, _start_date):
        return [
            {
                "level": "HIGH",
                "score": 83,
                "sleepScore": 86,
                "feedbackShort": "Recovering well",
                "recoveryTime": 34200,
                "sleepScoreFactorPercent": 82,
                "sleepHistoryFactorPercent": 77,
                "hrvFactorPercent": 69,
                "stressHistoryFactorPercent": 74,
                "acwrFactorPercent": 88,
                "recoveryTimeFactorPercent": 71,
            }
        ]

    def get_activity_exercise_sets(self, _activity_id):
        return {
            "activityId": 21922402831,
            "exerciseSets": [
                {
                    "setType": "ACTIVE",
                    "repetitionCount": 18,
                    "weight": 80,
                    "duration": 53.096,
                    "exercises": [{"name": "BENCH_DIP"}],
                },
                {
                    "setType": "REST",
                    "repetitionCount": None,
                    "weight": None,
                    "duration": 23.207,
                    "exercises": [],
                },
                {
                    "setType": "ACTIVE",
                    "repetitionCount": 29,
                    "weight": 75,
                    "duration": 52.696,
                    "exercises": [{"name": "SEATED_CABLE_ROW"}],
                },
            ],
        }

    def get_endurance_score(self, _end_date):
        return {"overallScore": 7312}

    def get_hill_score(self, _end_date):
        return {"overallScore": 102}

    def get_fitnessage_data(self, _date):
        return {
            "fitnessAge": 34,
            "chronologicalAge": 40,
            "achievableFitnessAge": 32,
            "previousFitnessAge": 35,
            "components": {
                "bodyFat": {"value": 14.8},
                "rhr": {"value": 47},
                "vigorousDaysAvg": {"value": 4.7},
                "vigorousMinutesAvg": {"value": 271},
            },
        }

    def get_earned_badges(self):
        return [
            {
                "badgeName": "Run Streak 400",
                "badgeLevel": 1,
                "badgeAssocType": "activityId",
                "badgeAssocDataId": "21922402831",
            },
            {
                "badgeName": "Weekend Warrior",
                "badgeLevel": 2,
                "badgeAssocType": "activityId",
                "badgeAssocDataId": "21900000000",
            },
        ]

    def get_activities_by_date(self, _start_date, _end_date):
        return [
            {
                "activityId": 3001,
                "startTimeGMT": "2026-02-16 11:01:14",
                "duration": 2712,
                "movingDuration": 2588,
                "distance": 0.0,
                "activityType": {"typeKey": "strength_training"},
                "activityName": "Strength",
            },
            {
                "activityId": 3002,
                "startTimeGMT": "2026-02-16 12:40:00",
                "duration": 2520,
                "movingDuration": 2520,
                "distance": 4412.0,
                "activityType": {"typeKey": "running"},
                "activityName": "Lunch Run",
            },
        ]

    def get_activity_details(self, activity_id):
        if int(activity_id) != 3001:
            return {}
        return {
            "activityId": 3001,
            "startTimeGMT": "2026-02-16 11:01:14",
            "duration": 2712,
            "movingDuration": 2588,
            "distance": 0.0,
            "activityType": {"typeKey": "strength_training"},
            "activityName": "Strength",
            "totalSets": 18,
            "activeSets": 16,
            "totalReps": 142,
            "summarizedExerciseSets": [
                {
                    "category": "PRESS",
                    "subCategory": "BENCH_PRESS",
                    "sets": 5,
                    "reps": 35,
                    "maxWeight": 205,
                    "duration": 686000,
                }
            ],
        }


class _ExerciseSetEdgeClient:
    def get_activity_exercise_sets(self, _activity_id):
        return {
            "exerciseSets": [
                {
                    "setType": "ACTIVE",
                    "repetitionCount": 20,
                    "weight": 0.0,
                    "duration": 53.096,
                    "exercises": [
                        {"category": "PUSH_UP", "name": None},
                    ],
                },
                {
                    "setType": "REST",
                    "repetitionCount": None,
                    "weight": -1.0,
                    "duration": 23.207,
                    "exercises": [],
                },
            ]
        }


class _DynamicGarminClient(_DummyGarminClient):
    def get_last_activity(self):
        payload = dict(super().get_last_activity())
        payload["deviceId"] = 999999999
        return payload

    def get_training_status(self, _end_date):
        return {
            "mostRecentVO2Max": {"generic": {"vo2MaxPreciseValue": 57.2}},
            "mostRecentTrainingStatus": {
                "latestTrainingStatusData": {
                    "999999999": {
                        "trainingStatusFeedbackPhrase": "PRODUCTIVE_BUILDING",
                        "fitnessTrend": "IMPROVING",
                        "loadLevelTrend": "WITHIN_RANGE",
                        "weeklyTrainingLoad": 568,
                        "loadTunnelMin": 60,
                        "loadTunnelMax": 92,
                        "acuteTrainingLoadDTO": {
                            "acwrStatus": "OPTIMAL",
                            "dailyTrainingLoadChronic": 72,
                            "dailyTrainingLoadAcute": 78,
                            "dailyAcuteChronicWorkloadRatio": 1.12,
                            "acwrPercent": 112,
                        },
                    }
                }
            },
        }

    def get_training_readiness(self, _start_date):
        return {
            "dailyReadiness": {
                "level": "HIGH",
                "score": 83,
                "sleepScore": 86,
                "feedbackShort": "Recovering well",
                "recoveryTime": 34200,
                "sleepScoreFactorPercent": 82,
                "sleepHistoryFactorPercent": 77,
                "hrvFactorPercent": 69,
                "stressHistoryFactorPercent": 74,
                "acwrFactorPercent": 88,
                "recoveryTimeFactorPercent": 71,
            }
        }


class _ReferenceActivityGarminClient(_DummyGarminClient):
    def get_last_activity(self):
        payload = dict(super().get_last_activity())
        payload.update(
            {
                "activityId": 9001,
                "startTimeGMT": "2026-03-20 11:42:00",
                "duration": 1800,
                "averageHR": 111,
                "averageRunningCadenceInStepsPerMinute": 171,
                "aerobicTrainingEffect": 1.1,
                "anaerobicTrainingEffect": 0.0,
                "trainingEffectLabel": "RECOVERY",
                "avgGradeAdjustedSpeed": 2.5,
            }
        )
        return payload

    def get_training_status(self, end_date):
        feedback = "PRODUCTIVE_BUILDING" if end_date == "2026-02-12" else "RECOVERY_EASY"
        return {
            "mostRecentVO2Max": {"generic": {"vo2MaxPreciseValue": 57.2}},
            "mostRecentTrainingStatus": {
                "latestTrainingStatusData": {
                    "3417115846": {
                        "trainingStatusFeedbackPhrase": feedback,
                        "fitnessTrend": "IMPROVING",
                        "loadLevelTrend": "WITHIN_RANGE",
                        "weeklyTrainingLoad": 568,
                        "loadTunnelMin": 60,
                        "loadTunnelMax": 92,
                        "acuteTrainingLoadDTO": {
                            "acwrStatus": "OPTIMAL",
                            "dailyTrainingLoadChronic": 72,
                            "dailyTrainingLoadAcute": 78,
                            "dailyAcuteChronicWorkloadRatio": 1.12,
                            "acwrPercent": 112,
                        },
                    }
                }
            },
        }

    def get_rhr_day(self, start_date):
        value = 44 if start_date == "2026-02-12" else 55
        return {
            "allMetrics": {
                "metricsMap": {
                    "WELLNESS_RESTING_HEART_RATE": [{"value": value}],
                }
            }
        }

    def get_training_readiness(self, start_date):
        return {
            "dailyReadiness": {
                "level": "HIGH" if start_date == "2026-02-12" else "POOR",
                "score": 77 if start_date == "2026-02-12" else 12,
                "sleepScore": 81 if start_date == "2026-02-12" else 40,
                "feedbackShort": "Recovered",
                "recoveryTime": 21600,
            }
        }

    def get_endurance_score(self, end_date):
        return {"overallScore": 7001 if end_date == "2026-02-12" else 6000}

    def get_hill_score(self, end_date):
        return {"overallScore": 99 if end_date == "2026-02-12" else 50}


class TestVo2MaxExpandedMetrics(unittest.TestCase):
    def test_fetch_training_status_returns_expanded_fields(self) -> None:
        metrics = fetch_training_status_and_scores(_DummyGarminClient())

        self.assertEqual(metrics["training_status_key"], "Productive")
        self.assertEqual(metrics["readiness_level"], "HIGH")
        self.assertEqual(metrics["recovery_time_hours"], 9.5)
        self.assertEqual(metrics["weekly_training_load"], 568)
        self.assertEqual(metrics["daily_acwr_ratio"], 1.12)
        self.assertEqual(metrics["acwr_percent"], 112)
        self.assertEqual(metrics["fitness_age"], "34 yr")
        self.assertTrue(metrics["garmin_badges"])
        self.assertIn("Garmin: Run Streak 400 (L1)", metrics["garmin_badges"])
        self.assertTrue(metrics["garmin_badges_raw"])
        self.assertEqual(metrics["garmin_badges_raw"][0]["badgeName"], "Run Streak 400")
        self.assertEqual(metrics["garmin_badges_raw"][0]["badgeAssocType"], "activityId")
        self.assertEqual(metrics["garmin_badges_raw"][0]["badgeAssocDataId"], "21922402831")
        self.assertIn("Garmin 2nd: Hill Sprint (1:41)", metrics["garmin_segment_notables"])
        self.assertIn("Garmin PR: River Path (1:28)", metrics["garmin_segment_notables"])

        last_activity = metrics["garmin_last_activity"]
        self.assertIsInstance(last_activity, dict)
        self.assertEqual(last_activity["distance_miles"], "8.02 mi")
        self.assertEqual(last_activity["activity_id"], 21922402831)
        self.assertEqual(last_activity["average_pace"], "7:19/mi")
        self.assertEqual(last_activity["cadence_spm"], 176)
        self.assertIn("Z1", last_activity["hr_zone_summary"])
        self.assertEqual(last_activity["total_sets"], 2)
        self.assertEqual(last_activity["active_sets"], 2)
        self.assertEqual(last_activity["total_reps"], 47)
        self.assertEqual(last_activity["max_weight"], 80.0)
        self.assertEqual(len(last_activity["strength_summary_sets"]), 2)
        self.assertEqual(len(last_activity["exercise_sets"]), 3)

        details = metrics["fitness_age_details"]
        self.assertIsInstance(details, dict)
        self.assertEqual(details["chronological_age"], 40)

    def test_fetch_training_status_handles_dynamic_device_id_and_dict_readiness(self) -> None:
        metrics = fetch_training_status_and_scores(_DynamicGarminClient())

        self.assertEqual(metrics["training_status_key"], "Productive")
        self.assertEqual(metrics["readiness_level"], "HIGH")
        self.assertEqual(metrics["training_readiness_score"], 83)
        self.assertEqual(metrics["sleep_score"], 86)
        self.assertEqual(metrics["weekly_training_load"], 568)
        self.assertEqual(metrics["daily_acwr_ratio"], 1.12)

    def test_fetch_training_status_uses_reference_activity_for_historical_rerun(self) -> None:
        reference_activity = {
            "activityId": 5555,
            "startTimeGMT": "2026-02-12 11:42:00",
            "duration": 2400,
            "distance": 8000.0,
            "averageSpeed": 3.4,
            "averageHR": 167,
            "averageRunningCadenceInStepsPerMinute": 182,
            "aerobicTrainingEffect": 3.5,
            "anaerobicTrainingEffect": 0.7,
            "trainingEffectLabel": "TEMPO",
            "avgGradeAdjustedSpeed": 3.5,
            "activityName": "Historical Run",
            "activityType": {"typeKey": "running"},
            "startTimeLocal": "2026-02-12 06:42:00",
        }

        metrics = fetch_training_status_and_scores(
            _ReferenceActivityGarminClient(),
            reference_activity=reference_activity,
            reference_date="2026-02-12T11:42:00Z",
        )

        self.assertEqual(metrics["training_status_key"], "Productive")
        self.assertEqual(metrics["training_readiness_score"], 77)
        self.assertEqual(metrics["resting_hr"], 44)
        self.assertEqual(metrics["endurance_overall_score"], 7001)
        self.assertEqual(metrics["hill_overall_score"], 99)
        self.assertEqual(metrics["average_hr"], 167)
        self.assertEqual(metrics["running_cadence"], 182)
        self.assertEqual(metrics["garmin_last_activity"]["activity_id"], 5555)

    def test_get_activity_context_for_strava_activity_matches_strength_session(self) -> None:
        strava_activity = {
            "id": 17455368360,
            "start_date": "2026-02-16T11:01:08Z",
            "moving_time": 2588,
            "elapsed_time": 2712,
            "distance": 0.0,
            "sport_type": "Run",
            "type": "Run",
        }
        context = get_activity_context_for_strava_activity(_DummyGarminClient(), strava_activity)
        self.assertIsInstance(context, dict)
        assert context is not None
        self.assertEqual(context["activity_type"], "strength_training")
        self.assertEqual(context["total_sets"], 18)
        self.assertEqual(context["total_reps"], 142)

    def test_strength_set_normalization_handles_bodyweight_and_negative_sentinel(self) -> None:
        context = build_garmin_activity_context(
            _ExerciseSetEdgeClient(),
            {
                "activityId": 919191,
                "activityType": {"typeKey": "strength_training"},
                "summarizedExerciseSets": [
                    {
                        "category": "PUSH_UP",
                        "subCategory": None,
                        "reps": 20,
                        "sets": 1,
                        "maxWeight": 0,
                        "duration": 53096,
                    }
                ],
            },
        )
        self.assertEqual(context["strength_summary_sets"][0]["sub_category"], "PUSH_UP")
        active_set = context["exercise_sets"][0]
        self.assertEqual(active_set["weight"], "Bodyweight")
        self.assertEqual(active_set["weight_value"], 0.0)
        self.assertEqual(active_set["weight_display"], "Bodyweight")
        self.assertEqual(active_set["exercise_names"], ["PUSH_UP"])
        rest_set = context["exercise_sets"][1]
        self.assertEqual(rest_set["weight"], "N/A")
        self.assertEqual(rest_set["weight_value"], "N/A")
        self.assertEqual(rest_set["weight_display"], "N/A")

    def test_build_garmin_activity_context_exposes_vescdash_metrics(self) -> None:
        context = build_garmin_activity_context(
            None,
            {
                "activityId": 22132894377,
                "activityName": "Forsyth County EUC riding",
                "activityTypeDTO": {"typeKey": "other"},
                "summaryDTO": {
                    "averageHR": 65.0,
                    "maxHR": 85.0,
                    "distance": 1451.89,
                    "duration": 561.418,
                    "movingDuration": 421.0,
                    "averageSpeed": 2.5859999656677246,
                    "maxSpeed": 7.241000175476074,
                    "calories": 15.0,
                    "waterEstimated": 51.0,
                },
                "connectIQMeasurements": [
                    {
                        "appID": "0432631a-d5e3-4272-a072-fa8c7e24c483",
                        "developerFieldNumber": 21,
                        "value": "Profile 1",
                    },
                    {
                        "appID": "0432631a-d5e3-4272-a072-fa8c7e24c483",
                        "developerFieldNumber": 23,
                        "value": "4.2",
                    },
                    {
                        "appID": "0432631a-d5e3-4272-a072-fa8c7e24c483",
                        "developerFieldNumber": 24,
                        "value": "17.8",
                    }
                ],
                "metricDescriptors": [
                    {
                        "appID": "0432631a-d5e3-4272-a072-fa8c7e24c483",
                        "developerFieldNumber": 4,
                        "key": "connectIQDeveloperField-20",
                        "metricsIndex": 0,
                    },
                    {
                        "appID": "0432631a-d5e3-4272-a072-fa8c7e24c483",
                        "developerFieldNumber": 26,
                        "key": "connectIQDeveloperField-21",
                        "metricsIndex": 1,
                    }
                ],
                "activityDetailMetrics": [
                    {"metrics": [125.0, 12.0]},
                    {"metrics": [180.0, 18.0]},
                ],
            },
        )

        self.assertEqual(context["activity_type"], "other")
        self.assertEqual(context["average_hr"], 65)
        self.assertEqual(context["calories"], 15)
        self.assertEqual(context["connectiq_app_ids"], ["0432631a-d5e3-4272-a072-fa8c7e24c483"])
        self.assertEqual(context["connectiq_measurements"][0]["developer_field_number"], 21)
        self.assertEqual(context["connectiq_detail_metrics"][0]["last_value"], 180.0)
        self.assertEqual(context["vescdash"]["profile_name"], "Profile 1")
        self.assertEqual(context["vescdash"]["trip_distance_miles"], "4.2 mi")
        self.assertEqual(context["vescdash"]["max_speed_mph"], "17.8 mph")
        self.assertEqual(context["vescdash"]["current_power_w"], "180 W")
        self.assertEqual(context["vescdash"]["current_temperature_f"], "18°F")
        self.assertTrue(context["vescdash_detected"])
        self.assertTrue(context["wheeldash_detected"])


if __name__ == "__main__":
    unittest.main()
