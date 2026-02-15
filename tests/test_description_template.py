import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from description_template import (
    build_context_schema,
    get_editor_snippets,
    get_active_template,
    get_default_template,
    get_sample_template_context,
    render_template_text,
    render_with_active_template,
    save_active_template,
    validate_template_text,
)


def _settings_for(path: Path) -> SimpleNamespace:
    return SimpleNamespace(description_template_file=path)


class TestDescriptionTemplate(unittest.TestCase):
    def test_loads_default_when_custom_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            template_path = Path(td) / "description_template.j2"
            settings = _settings_for(template_path)
            active = get_active_template(settings)
            self.assertFalse(active["is_custom"])
            self.assertEqual(active["template"], get_default_template())

    def test_save_and_load_custom_template(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            template_path = Path(td) / "description_template.j2"
            settings = _settings_for(template_path)
            save_active_template(settings, "Hello {{ name }}")
            active = get_active_template(settings)
            self.assertTrue(active["is_custom"])
            self.assertEqual(active["template"], "Hello {{ name }}")

    def test_validate_and_render(self) -> None:
        context = {"name": "Runner"}
        validation = validate_template_text("Hello {{ name }}", context)
        self.assertTrue(validation["valid"])

        result = render_template_text("Hello {{ name }}", context)
        self.assertTrue(result["ok"])
        self.assertEqual(result["description"], "Hello Runner")

    def test_validate_warns_on_unknown_top_level(self) -> None:
        context = {"name": "Runner"}
        validation = validate_template_text("Hello {{ unknown }}", context)
        self.assertFalse(validation["valid"])
        self.assertTrue(validation["errors"])

    def test_custom_template_fallback_to_default(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            template_path = Path(td) / "description_template.j2"
            settings = _settings_for(template_path)
            save_active_template(settings, "{{ missing_var }}")

            context = {
                "streak_days": "N/A",
                "notables": [],
                "achievements": [],
                "weather": {
                    "misery_index": "N/A",
                    "misery_description": "",
                    "aqi": "N/A",
                    "aqi_description": "",
                },
                "crono": {"line": None},
                "training": {
                    "readiness_score": "N/A",
                    "readiness_emoji": "⚪",
                    "resting_hr": "N/A",
                    "sleep_score": "N/A",
                    "status_emoji": "⚪",
                    "status_key": "N/A",
                    "aerobic_te": "N/A",
                    "anaerobic_te": "N/A",
                    "te_label": "N/A",
                    "chronic_load": "N/A",
                    "acute_load": "N/A",
                    "load_ratio": "N/A",
                    "acwr_status": "N/A",
                    "acwr_status_emoji": "⚪",
                    "vo2": "N/A",
                    "endurance_score": "N/A",
                    "hill_score": "N/A",
                },
                "activity": {
                    "gap_pace": "N/A",
                    "distance_miles": "0.00",
                    "elevation_feet": "N/A",
                    "time": "0:00",
                    "beers": "0.0",
                    "cadence_spm": "N/A",
                    "work": "N/A",
                    "norm_power": "N/A",
                    "average_hr": "N/A",
                    "efficiency": "N/A",
                },
                "intervals": {"summary": "N/A"},
                "periods": {
                    "week": {
                        "gap": "N/A",
                        "distance_miles": "0.0",
                        "elevation_feet": 0,
                        "duration": "0:00",
                        "beers": "0",
                    },
                    "month": {
                        "gap": "N/A",
                        "distance_miles": "0",
                        "elevation_feet": 0,
                        "duration": "0:00",
                        "beers": "0",
                    },
                    "year": {
                        "gap": "N/A",
                        "distance_miles": "0",
                        "elevation_feet": 0,
                        "duration": "0:00",
                        "beers": "0",
                    },
                },
                "raw": {},
            }

            result = render_with_active_template(settings, context)
            self.assertTrue(result["ok"])
            self.assertTrue(result["fallback_used"])

    def test_schema_builder(self) -> None:
        context = {
            "activity": {"distance_miles": "8.02", "beers": "5.1"},
            "notables": ["Longest run"],
        }
        schema = build_context_schema(context)
        self.assertEqual(schema["group_count"], 2)
        self.assertGreaterEqual(schema["field_count"], 2)

    def test_sample_context_shape(self) -> None:
        context = get_sample_template_context()
        self.assertIn("activity", context)
        self.assertIn("training", context)
        self.assertIn("weather", context)
        self.assertIn("periods", context)

    def test_editor_snippets_shape(self) -> None:
        snippets = get_editor_snippets()
        self.assertGreater(len(snippets), 0)
        first = snippets[0]
        self.assertIn("id", first)
        self.assertIn("label", first)
        self.assertIn("template", first)


if __name__ == "__main__":
    unittest.main()
