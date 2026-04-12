from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from chronicle.pipeline_context_collectors import (
    collect_crono_context,
    collect_smashrun_context,
    collect_weather_context,
)


def _settings(**overrides: Any) -> SimpleNamespace:
    base = {
        "enable_smashrun": False,
        "smashrun_access_token": None,
        "service_cache_ttl_seconds": 600,
        "timezone": "UTC",
        "enable_weather": False,
        "weather_api_key": None,
        "enable_crono_api": False,
        "crono_api_base_url": None,
        "crono_api_key": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class TestPipelineContextCollectors(unittest.TestCase):
    def test_collect_smashrun_context_disabled_returns_defaults(self) -> None:
        calls: list[str] = []

        def _run_service_call(*_args, **_kwargs):
            calls.append("called")
            return None

        result = collect_smashrun_context(
            _settings(enable_smashrun=False),
            {"id": 123},
            selected_activity_id=123,
            latest_activity_id=123,
            now_utc=datetime.now(timezone.utc),
            service_state={},
            run_service_call=_run_service_call,
            as_float=lambda value: float(value) if isinstance(value, (int, float)) else None,
        )
        self.assertEqual(result["notables"], [])
        self.assertEqual(result["smashrun_badges"], [])
        self.assertEqual(calls, [])

    def test_collect_smashrun_context_fetches_notables_for_matched_historical_activity(self) -> None:
        calls: list[tuple[str, dict[str, Any]]] = []

        def _run_service_call(_settings, service_name, *_args, **kwargs):
            calls.append((service_name, kwargs))
            if service_name == "smashrun.activities":
                return [
                    {
                        "activityId": 998877,
                        "stravaActivityId": 123,
                        "startDateTimeUtc": "2026-02-10T12:00:00Z",
                        "distance": 5000.0,
                    },
                    {
                        "activityId": 445566,
                        "stravaActivityId": 999,
                        "startDateTimeUtc": "2026-02-12T12:00:00Z",
                        "distance": 7000.0,
                    },
                ]
            if service_name == "smashrun.notables":
                self.assertEqual(kwargs.get("latest_activity_id"), 998877)
                return ["Historic notable"]
            if service_name == "smashrun.stats":
                return {"longestStreak": 14}
            if service_name == "smashrun.badges":
                return []
            return None

        result = collect_smashrun_context(
            _settings(enable_smashrun=True, smashrun_access_token="token"),
            {"id": 123, "start_date": "2026-02-10T12:00:00Z", "distance": 5000.0},
            selected_activity_id=123,
            latest_activity_id=999,
            now_utc=datetime.now(timezone.utc),
            service_state={},
            run_service_call=_run_service_call,
            as_float=lambda value: float(value) if isinstance(value, (int, float)) else None,
        )

        self.assertEqual(result["notables"], ["Historic notable"])
        self.assertEqual(result["longest_streak"], 14)
        self.assertTrue(any(name == "smashrun.notables" for name, _kwargs in calls))

    def test_collect_weather_context_uses_details_then_skips_fallback(self) -> None:
        calls: list[str] = []

        def _run_service_call(_settings, service_name, *_args, **_kwargs):
            calls.append(service_name)
            if service_name == "weather.details":
                return {
                    "misery_index": 5.0,
                    "misery_description": "Fair",
                    "aqi": 42,
                    "aqi_description": "Good",
                }
            return None

        result = collect_weather_context(
            _settings(enable_weather=True, weather_api_key="key"),
            {"id": 123},
            selected_activity_id=123,
            service_state={},
            run_service_call=_run_service_call,
        )
        self.assertEqual(result["misery_index"], 5.0)
        self.assertEqual(result["aqi"], 42)
        self.assertEqual(calls, ["weather.details"])

    def test_collect_weather_context_uses_fallback_when_details_missing(self) -> None:
        calls: list[str] = []

        def _run_service_call(_settings, service_name, *_args, **_kwargs):
            calls.append(service_name)
            if service_name == "weather.details":
                return None
            if service_name == "weather.fallback":
                return (6.1, "Warm", 55, "Moderate")
            return None

        result = collect_weather_context(
            _settings(enable_weather=True, weather_api_key="key"),
            {"id": 123},
            selected_activity_id=123,
            service_state={},
            run_service_call=_run_service_call,
        )
        self.assertEqual(result["misery_index"], 6.1)
        self.assertEqual(result["aqi"], 55)
        self.assertEqual(calls, ["weather.details", "weather.fallback"])

    def test_collect_crono_context_disabled(self) -> None:
        calls: list[str] = []

        def _run_service_call(*_args, **_kwargs):
            calls.append("called")
            return {}

        summary, line = collect_crono_context(
            _settings(enable_crono_api=False),
            {"id": 123},
            selected_activity_id=123,
            service_state={},
            run_service_call=_run_service_call,
        )
        self.assertIsNone(summary)
        self.assertIsNone(line)
        self.assertEqual(calls, [])

    def test_collect_crono_context_enabled(self) -> None:
        calls: list[str] = []
        summary_payload = {
            "average_net_kcal_per_day": 123.4,
            "average_status": "Deficit",
            "protein_g": 160,
            "carbs_g": 220,
        }

        def _run_service_call(_settings, service_name, *_args, **_kwargs):
            calls.append(service_name)
            return summary_payload

        summary, line = collect_crono_context(
            _settings(enable_crono_api=True, timezone="UTC"),
            {"id": 123},
            selected_activity_id=123,
            service_state={},
            run_service_call=_run_service_call,
        )
        self.assertEqual(summary, summary_payload)
        self.assertIn("crono.summary", calls)
        self.assertTrue(line is None or isinstance(line, str))


if __name__ == "__main__":
    unittest.main()
