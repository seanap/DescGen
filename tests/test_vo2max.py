import unittest

from stat_modules.vo2max import fetch_training_status_and_scores


class _DummyGarminClient:
    def get_last_activity(self):
        return {
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
            {"badgeName": "Run Streak 400", "badgeLevel": 1},
            {"badgeName": "Weekend Warrior", "badgeLevel": 2},
        ]


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
        self.assertIn("Garmin 2nd: Hill Sprint (1:41)", metrics["garmin_segment_notables"])
        self.assertIn("Garmin PR: River Path (1:28)", metrics["garmin_segment_notables"])

        last_activity = metrics["garmin_last_activity"]
        self.assertIsInstance(last_activity, dict)
        self.assertEqual(last_activity["distance_miles"], "8.02 mi")
        self.assertEqual(last_activity["average_pace"], "7:19/mi")
        self.assertIn("Z1", last_activity["hr_zone_summary"])

        details = metrics["fitness_age_details"]
        self.assertIsInstance(details, dict)
        self.assertEqual(details["chronological_age"], 40)


if __name__ == "__main__":
    unittest.main()
