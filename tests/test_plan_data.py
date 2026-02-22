from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from chronicle.plan_data import METERS_PER_MILE, get_plan_payload


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        timezone="UTC",
        processed_log_file=Path("/tmp/plan_test_runtime.log"),
    )


def _miles_to_meters(value: float) -> float:
    return value * METERS_PER_MILE


class TestPlanData(unittest.TestCase):
    def test_get_plan_payload_uses_actual_for_past_and_planned_for_future(self) -> None:
        payload = get_plan_payload(
            _settings(),
            center_date="2026-02-22",
            window_days=7,
            today_local=date(2026, 2, 22),
            dashboard_payload={
                "activities": [
                    {"date": "2026-02-16", "type": "Run", "distance": _miles_to_meters(7.2)},
                    {"date": "2026-02-17", "type": "Run", "distance": _miles_to_meters(9.0)},
                    {"date": "2026-02-18", "type": "Run", "distance": _miles_to_meters(7.1)},
                    {"date": "2026-02-19", "type": "Run", "distance": _miles_to_meters(4.5)},
                    {"date": "2026-02-20", "type": "Run", "distance": _miles_to_meters(4.5)},
                    {"date": "2026-02-21", "type": "Run", "distance": _miles_to_meters(13.1)},
                    {"date": "2026-02-19", "type": "Ride", "distance": _miles_to_meters(60.0)},
                ]
            },
            plan_day_rows=[
                {
                    "date_local": "2026-02-22",
                    "run_type": "Easy",
                    "planned_total_miles": 6.2,
                    "is_complete": False,
                },
                {
                    "date_local": "2026-02-23",
                    "run_type": "Recovery",
                    "planned_total_miles": 3.5,
                    "is_complete": False,
                },
            ],
        )

        rows = payload["rows"]
        by_date = {str(item["date"]): item for item in rows}

        today_row = by_date["2026-02-22"]
        self.assertAlmostEqual(today_row["actual_miles"], 0.0, places=3)
        self.assertAlmostEqual(today_row["planned_miles"], 6.2, places=3)
        self.assertAlmostEqual(today_row["effective_miles"], 6.2, places=3)
        self.assertEqual(today_row["run_type"], "Easy")
        self.assertFalse(today_row["is_complete"])
        self.assertEqual(today_row["completion_source"], "manual")
        self.assertEqual(today_row["planned_input"], "6.2")
        self.assertAlmostEqual(today_row["weekly_total"], 51.6, places=1)
        self.assertAlmostEqual(today_row["long_pct"], 13.1 / 51.6, places=3)
        self.assertEqual(today_row["bands"]["long_pct"], "good")

        future_row = by_date["2026-02-23"]
        self.assertFalse(future_row["is_past_or_today"])
        self.assertAlmostEqual(future_row["effective_miles"], 3.5, places=3)
        self.assertEqual(future_row["run_type"], "Recovery")
        self.assertEqual(future_row["is_complete"], False)

        past_row = by_date["2026-02-21"]
        self.assertTrue(past_row["is_past_or_today"])
        self.assertAlmostEqual(past_row["actual_miles"], 13.1, places=2)
        self.assertAlmostEqual(past_row["effective_miles"], 13.1, places=2)
        self.assertEqual(past_row["completion_source"], "auto")
        self.assertIn("run_type_options", payload)
        self.assertIn("Easy", payload["run_type_options"])
        self.assertIn("summary", payload)
        self.assertIn("week_planned", payload["summary"])

    def test_get_plan_payload_uses_session_sum_for_planned_and_planned_input(self) -> None:
        payload = get_plan_payload(
            _settings(),
            center_date="2026-02-22",
            window_days=7,
            today_local=date(2026, 2, 22),
            dashboard_payload={"activities": []},
            plan_day_rows=[
                {
                    "date_local": "2026-02-23",
                    "run_type": "Easy",
                    "planned_total_miles": 9.0,
                    "is_complete": False,
                },
            ],
            plan_sessions_by_day={
                "2026-02-23": [
                    {"ordinal": 1, "planned_miles": 6.0},
                    {"ordinal": 2, "planned_miles": 4.0},
                ]
            },
        )
        row = next(item for item in payload["rows"] if item["date"] == "2026-02-23")
        self.assertAlmostEqual(row["planned_miles"], 10.0, places=3)
        self.assertEqual(row["planned_input"], "6+4")
        self.assertEqual(row["planned_sessions"], [6.0, 4.0])
        self.assertAlmostEqual(row["day_delta"], -10.0, places=3)

    def test_get_plan_payload_rejects_invalid_center_date(self) -> None:
        with self.assertRaises(ValueError):
            get_plan_payload(
                _settings(),
                center_date="02/22/2026",
                window_days=14,
                today_local=date(2026, 2, 22),
                dashboard_payload={"activities": []},
                plan_day_rows=[],
            )

    def test_window_days_is_clamped(self) -> None:
        payload = get_plan_payload(
            _settings(),
            center_date="2026-02-22",
            window_days=1,
            today_local=date(2026, 2, 22),
            dashboard_payload={"activities": []},
            plan_day_rows=[],
        )
        self.assertEqual(payload["window_days"], 7)
        self.assertEqual(len(payload["rows"]), 15)


if __name__ == "__main__":
    unittest.main()
