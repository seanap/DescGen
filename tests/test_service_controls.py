import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from chronicle.activity_pipeline import _new_cycle_service_state, _run_required_call, _run_service_call
from chronicle.storage import get_runtime_value


def _settings_for(path: Path, *, budget_enabled: bool = True, budget_max: int = 10) -> SimpleNamespace:
    return SimpleNamespace(
        processed_log_file=path,
        service_retry_count=0,
        service_retry_backoff_seconds=1,
        service_cooldown_base_seconds=60,
        service_cooldown_max_seconds=1800,
        enable_service_call_budget=budget_enabled,
        max_optional_service_calls_per_cycle=budget_max,
        enable_service_result_cache=True,
        service_cache_ttl_seconds=600,
    )


class TestServiceControls(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "processed_activities.log"
        self._old_runtime = os.environ.get("RUNTIME_DB_FILE")
        os.environ["RUNTIME_DB_FILE"] = "runtime_state.db"

    def tearDown(self) -> None:
        if self._old_runtime is None:
            os.environ.pop("RUNTIME_DB_FILE", None)
        else:
            os.environ["RUNTIME_DB_FILE"] = self._old_runtime
        self.temp_dir.cleanup()

    def test_optional_budget_blocks_when_exhausted(self) -> None:
        settings = _settings_for(self.path, budget_enabled=True, budget_max=0)
        state = _new_cycle_service_state(settings)
        calls = {"count": 0}

        def _fn() -> dict[str, int]:
            calls["count"] += 1
            return {"ok": 1}

        result = _run_service_call(
            settings,
            "test.optional",
            _fn,
            service_state=state,
        )
        self.assertIsNone(result)
        self.assertEqual(calls["count"], 0)
        self.assertEqual(state["budget_skipped_optional_calls"], 1)
        skipped_budget = get_runtime_value(
            settings.processed_log_file,
            "service.test.optional.events.skipped_budget",
            0,
        )
        self.assertEqual(int(skipped_budget), 1)

    def test_optional_cache_avoids_repeat_execution(self) -> None:
        settings = _settings_for(self.path, budget_enabled=False, budget_max=10)
        state = _new_cycle_service_state(settings)
        calls = {"count": 0}

        def _fn() -> dict[str, int]:
            calls["count"] += 1
            return {"count": calls["count"]}

        first = _run_service_call(
            settings,
            "test.cache",
            _fn,
            service_state=state,
            cache_key="same-key",
            cache_ttl_seconds=600,
        )
        second = _run_service_call(
            settings,
            "test.cache",
            _fn,
            service_state=state,
            cache_key="same-key",
            cache_ttl_seconds=600,
        )

        self.assertEqual(first, {"count": 1})
        self.assertEqual(second, {"count": 1})
        self.assertEqual(calls["count"], 1)
        self.assertEqual(state["optional_cache_hits"], 1)
        cache_hits = get_runtime_value(
            settings.processed_log_file,
            "service.test.cache.events.cache_hit",
            0,
        )
        self.assertEqual(int(cache_hits), 1)

    def test_required_call_records_cycle_metrics(self) -> None:
        settings = _settings_for(self.path, budget_enabled=True, budget_max=5)
        state = _new_cycle_service_state(settings)

        result = _run_required_call(
            settings,
            "test.required",
            lambda: 42,
            service_state=state,
        )
        self.assertEqual(result, 42)
        self.assertEqual(state["required_calls_executed"], 1)
        bucket = state["services"]["test.required"]
        self.assertEqual(bucket["required_calls"], 1)


if __name__ == "__main__":
    unittest.main()
