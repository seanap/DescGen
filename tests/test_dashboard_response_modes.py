from __future__ import annotations

import unittest

from chronicle.dashboard_response_modes import (
    apply_dashboard_response_mode,
    normalize_dashboard_response_mode,
)


class TestDashboardResponseModes(unittest.TestCase):
    def test_normalize_dashboard_response_mode(self) -> None:
        self.assertEqual(normalize_dashboard_response_mode(""), "full")
        self.assertEqual(normalize_dashboard_response_mode("FULL"), "full")
        self.assertEqual(normalize_dashboard_response_mode("summary"), "summary")
        self.assertEqual(normalize_dashboard_response_mode("slim"), "summary")
        self.assertEqual(normalize_dashboard_response_mode("year"), "year")
        with self.assertRaises(ValueError):
            normalize_dashboard_response_mode("bad")

    def test_apply_summary_mode_omits_activities(self) -> None:
        payload = {
            "activities": [{"id": "1"}, {"id": "2"}],
            "aggregates": {"2026": {"Run": {}}},
        }
        result = apply_dashboard_response_mode(payload, response_mode="summary", response_year=None)
        self.assertEqual(result.get("response_mode"), "summary")
        self.assertEqual(result.get("activity_count"), 2)
        self.assertEqual(result.get("activities"), [])
        self.assertIn("2026", result.get("aggregates", {}))

    def test_apply_year_mode_scopes_payload(self) -> None:
        payload = {
            "years": [2025, 2026],
            "types": ["Ride", "Run"],
            "type_meta": {
                "Ride": {"label": "Ride"},
                "Run": {"label": "Run"},
            },
            "aggregates": {
                "2025": {"Ride": {"2025-01-01": {"count": 1}}},
                "2026": {"Run": {"2026-01-01": {"count": 1}}},
            },
            "intervals_year_type_metrics": {
                "2025": {"Ride": {"avg_fitness": 50}},
                "2026": {"Run": {"avg_fitness": 70}},
            },
            "activities": [
                {"id": "1", "year": 2025, "type": "Ride"},
                {"id": "2", "year": 2026, "type": "Run"},
            ],
        }
        result = apply_dashboard_response_mode(payload, response_mode="year", response_year=2026)
        self.assertEqual(result.get("response_mode"), "year")
        self.assertEqual(result.get("response_year"), 2026)
        self.assertEqual(result.get("years"), [2026])
        self.assertEqual(set(result.get("aggregates", {}).keys()), {"2026"})
        self.assertEqual(set(result.get("intervals_year_type_metrics", {}).keys()), {"2026"})
        self.assertEqual(result.get("types"), ["Run"])
        self.assertEqual(len(result.get("activities", [])), 1)
        self.assertEqual(result["activities"][0]["id"], "2")

    def test_apply_year_mode_requires_year(self) -> None:
        with self.assertRaises(ValueError):
            apply_dashboard_response_mode(
                {"activities": []},
                response_mode="year",
                response_year=None,
            )


if __name__ == "__main__":
    unittest.main()
