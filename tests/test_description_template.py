import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from description_template import (
    build_context_schema,
    create_template_repository_template,
    duplicate_template_repository_template,
    export_template_repository_bundle,
    get_template_repository_template,
    get_template_version,
    get_editor_snippets,
    get_starter_templates,
    get_active_template,
    get_default_template,
    get_sample_template_context,
    import_template_repository_bundle,
    list_sample_template_fixtures,
    list_template_repository_templates,
    list_template_versions,
    render_template_text,
    render_with_active_template,
    rollback_template_version,
    save_active_template,
    update_template_repository_template,
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
            self.assertTrue(active.get("current_version"))

    def test_validate_and_render(self) -> None:
        context = {"name": "Runner"}
        validation = validate_template_text("Hello {{ name }}", context)
        self.assertTrue(validation["valid"])

        result = render_template_text("Hello {{ name }}", context)
        self.assertTrue(result["ok"])
        self.assertEqual(result["description"], "Hello Runner")

    def test_validate_rejects_forbidden_constructs(self) -> None:
        context = {"value": "ok"}
        validation = validate_template_text("{% include 'x' %}", context)
        self.assertFalse(validation["valid"])
        self.assertTrue(validation["errors"])

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
            "raw": {"activity": {"distance_miles": 8.02}},
        }
        schema = build_context_schema(context)
        self.assertEqual(schema["group_count"], 3)
        self.assertGreaterEqual(schema["field_count"], 2)
        activity_group = next(group for group in schema["groups"] if group["group"] == "activity")
        self.assertIn("source", activity_group)
        first_field = activity_group["fields"][0]
        self.assertIn("source", first_field)
        self.assertIn("source_note", first_field)
        self.assertIn("facets", schema)
        self.assertIn("helper_transforms", schema)
        self.assertIsInstance(schema["helper_transforms"], list)
        self.assertIn("sources", schema["facets"])
        self.assertIn("tags", schema["facets"])
        self.assertIn("types", schema["facets"])
        self.assertIn("metric_keys", schema["facets"])
        raw_group = next(group for group in schema["groups"] if group["group"] == "raw")
        raw_field = next(field for field in raw_group["fields"] if field["path"] == "raw.activity.distance_miles")
        self.assertFalse(raw_field["curated"])

    def test_schema_overlap_detection(self) -> None:
        context = {
            "activity": {"beers": "5.1"},
            "periods": {"week": {"beers": "21"}},
        }
        schema = build_context_schema(context)
        self.assertIn("overlaps", schema)
        overlaps = schema["overlaps"]
        self.assertIsInstance(overlaps, list)
        for entry in overlaps:
            self.assertIn("metric_key", entry)
            self.assertIn("paths", entry)

    def test_sample_context_shape(self) -> None:
        context = get_sample_template_context()
        self.assertIn("activity", context)
        self.assertIn("training", context)
        self.assertIn("weather", context)
        self.assertIn("periods", context)
        self.assertIn("crono", context)
        self.assertIn("average_net_kcal_per_day", context["crono"])

    def test_sample_fixture_context(self) -> None:
        winter = get_sample_template_context("winter_grind")
        self.assertIn("weather", winter)
        self.assertIn("misery_index", winter["weather"])
        fixtures = list_sample_template_fixtures()
        self.assertGreaterEqual(len(fixtures), 2)
        self.assertTrue(any(item["name"] == "winter_grind" for item in fixtures))

    def test_template_versions_and_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            template_path = Path(td) / "description_template.j2"
            settings = _settings_for(template_path)
            first = save_active_template(settings, "First {{ value }}", author="alice", source="test")
            second = save_active_template(settings, "Second {{ value }}", author="bob", source="test")
            self.assertNotEqual(first.get("saved_version"), second.get("saved_version"))

            versions = list_template_versions(settings)
            self.assertGreaterEqual(len(versions), 2)
            version_id = versions[0]["version_id"]
            loaded = get_template_version(settings, version_id)
            self.assertIsNotNone(loaded)
            self.assertIn("template", loaded)

            rolled = rollback_template_version(settings, version_id=versions[-1]["version_id"], author="tester")
            self.assertTrue(rolled["is_custom"])
            self.assertIn("saved_version", rolled)

    def test_editor_snippets_shape(self) -> None:
        snippets = get_editor_snippets()
        self.assertGreater(len(snippets), 0)
        first = snippets[0]
        self.assertIn("id", first)
        self.assertIn("label", first)
        self.assertIn("template", first)

    def test_starter_templates_shape(self) -> None:
        templates = get_starter_templates()
        self.assertGreater(len(templates), 1)
        first = templates[0]
        self.assertIn("id", first)
        self.assertIn("label", first)
        self.assertIn("description", first)
        self.assertIn("template", first)

    def test_template_repository_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            template_path = Path(td) / "description_template.j2"
            settings = _settings_for(template_path)

            created = create_template_repository_template(
                settings,
                template_text="Hello {{ activity.distance_miles }}",
                name="My Template",
                author="tester",
                description="Repository template",
            )
            self.assertIn("template_id", created)
            self.assertFalse(created["is_builtin"])

            listed = list_template_repository_templates(settings)
            self.assertGreaterEqual(len(listed), 1)
            self.assertTrue(any(item["template_id"] == created["template_id"] for item in listed))

            loaded = get_template_repository_template(settings, created["template_id"])
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded["name"], "My Template")
            self.assertEqual(loaded["author"], "tester")

            updated = update_template_repository_template(
                settings,
                template_id=created["template_id"],
                template_text="Hi {{ activity.distance_miles }}",
                name="My Template v2",
                author="tester2",
            )
            self.assertEqual(updated["name"], "My Template v2")
            self.assertEqual(updated["author"], "tester2")

            duplicated = duplicate_template_repository_template(
                settings,
                template_id=created["template_id"],
            )
            self.assertNotEqual(duplicated["template_id"], created["template_id"])

            exported = export_template_repository_bundle(
                settings,
                template_id=created["template_id"],
            )
            self.assertEqual(exported["name"], "My Template v2")
            self.assertEqual(exported["author"], "tester2")
            self.assertIn("template", exported)

            imported = import_template_repository_bundle(
                settings,
                bundle=exported,
            )
            self.assertIn("template_id", imported)
            self.assertEqual(imported["name"], "My Template v2")


if __name__ == "__main__":
    unittest.main()
