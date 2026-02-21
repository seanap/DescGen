import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from chronicle.description_template import (
    PROFILE_TEMPLATE_DEFAULTS,
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
    icu_calc_form,
    icu_form_class,
    icu_form_emoji,
    import_template_repository_bundle,
    get_working_template_profile,
    list_sample_template_fixtures,
    list_template_profiles,
    list_template_repository_templates,
    list_template_versions,
    render_template_text,
    render_with_active_template,
    rollback_template_version,
    save_active_template,
    set_working_template_profile,
    update_template_profile,
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

    def test_icu_helpers(self) -> None:
        self.assertEqual(icu_calc_form({}, 72, 78), -8)
        self.assertEqual(icu_calc_form({}, "N/A", 78), "N/A")

        self.assertEqual(icu_form_class({}, -35), "High Risk")
        self.assertEqual(icu_form_class({}, -20), "Optimal")
        self.assertEqual(icu_form_class({}, -5), "Grey Zone")
        self.assertEqual(icu_form_class({}, 8), "Fresh")
        self.assertEqual(icu_form_class({}, 25), "Transition")
        self.assertEqual(
            icu_form_class({"intervals": {"form_percent": -22}}, "Transition", "Fresh", "Grey Zone", "Optimal", "High Risk"),
            "Optimal",
        )

        self.assertEqual(icu_form_emoji({}, -35), "⚠️")
        self.assertEqual(icu_form_emoji({}, -20), "🦾")
        self.assertEqual(icu_form_emoji({}, -5), "⛔")
        self.assertEqual(icu_form_emoji({}, 8), "🏁")
        self.assertEqual(icu_form_emoji({}, 25), "❄️")

    def test_render_template_with_icu_helpers(self) -> None:
        context = {"intervals": {"fitness": 72, "fatigue": 78}}
        template = "{{ icu_calc_form(intervals.fitness, intervals.fatigue) }}|{{ icu_form_class(icu_calc_form(intervals.fitness, intervals.fatigue)) }}"
        result = render_template_text(template, context)
        self.assertTrue(result["ok"])
        self.assertEqual(result["description"], "-8|Grey Zone")

    def test_validate_and_render_with_legacy_intervals_context(self) -> None:
        context = {
            "intervals": {
                "ctl": 72,
                "atl": 78,
                "training_load": 126,
            },
            "activity": {},
        }
        template = "{{ intervals.fitness }}|{{ intervals.fatigue }}|{{ intervals.load }}|{{ intervals.form_percent_display }}|{{ activity.fitness }}"
        validation = validate_template_text(template, context)
        self.assertTrue(validation["valid"])

        result = render_template_text(template, context)
        self.assertTrue(result["ok"])
        self.assertEqual(result["description"], "72|78|126|-8%|72")
        self.assertNotIn("fitness", context["intervals"])
        self.assertNotIn("fitness", context["activity"])

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
                "intervals": {
                    "summary": "N/A",
                    "fitness": "N/A",
                    "fatigue": "N/A",
                    "load": "N/A",
                    "ramp_display": "N/A",
                    "form_percent_display": "N/A",
                    "form_class": "N/A",
                    "form_class_emoji": "⚪",
                },
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

    def test_custom_template_render_can_disable_seed_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            template_path = Path(td) / "description_template.j2"
            settings = _settings_for(template_path)
            save_active_template(settings, "{{ missing_var.attribute }}")
            result = render_with_active_template(settings, {"missing_var": {}}, allow_seed_fallback=False)
            self.assertFalse(result["ok"])
            self.assertFalse(result["fallback_used"])
            self.assertTrue(isinstance(result.get("error"), str) and result["error"])

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
        self.assertIn("stability", first_field)
        self.assertIn("cost_tier", first_field)
        self.assertIn("freshness", first_field)
        self.assertIn("facets", schema)
        self.assertIn("helper_transforms", schema)
        self.assertIsInstance(schema["helper_transforms"], list)
        self.assertIn("sources", schema["facets"])
        self.assertIn("tags", schema["facets"])
        self.assertIn("types", schema["facets"])
        self.assertIn("metric_keys", schema["facets"])
        self.assertIn("stability", schema["facets"])
        self.assertIn("cost_tiers", schema["facets"])
        self.assertIn("freshness", schema["facets"])
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
        self.assertIn("misery", context)
        self.assertIn("periods", context)
        self.assertIn("crono", context)
        self.assertIn("average_net_kcal_per_day", context["crono"])
        self.assertIn("average_pace", context["activity"])
        self.assertIn("social", context["activity"])
        self.assertIn("fitness_age", context["training"])
        self.assertIn("readiness_factors", context["training"])
        self.assertIn("temp_f", context["weather"])
        self.assertIn("components", context["weather"])
        self.assertIn("training_load", context["intervals"])
        self.assertIn("garmin", context)
        self.assertIn("smashrun", context)
        self.assertIn("badges", context)
        self.assertIn("segment_notables", context)
        self.assertIn("strava_badges", context)
        self.assertIn("garmin_badges", context)
        self.assertIn("smashrun_badges", context)
        self.assertIn("strava_segment_notables", context)
        self.assertIn("garmin_segment_notables", context)
        self.assertIn("latest_activity", context["smashrun"])
        self.assertIn("badges", context["smashrun"])
        self.assertIn("last_activity", context["garmin"])
        self.assertIn("badges", context["garmin"])
        self.assertIn("segment_notables", context["activity"])
        self.assertIn("index", context["misery"])

    def test_sample_fixture_context(self) -> None:
        winter = get_sample_template_context("winter_grind")
        self.assertIn("weather", winter)
        self.assertIn("misery", winter)
        self.assertIn("misery_index", winter["weather"])
        strength = get_sample_template_context("strength_training")
        self.assertIn("raw", strength)
        self.assertIn("training", strength["raw"])
        self.assertIn("garmin_last_activity", strength["raw"]["training"])
        self.assertEqual(strength["raw"]["training"]["garmin_last_activity"].get("activity_type"), "strength_training")
        fixtures = list_sample_template_fixtures()
        self.assertGreaterEqual(len(fixtures), 2)
        self.assertTrue(any(item["name"] == "winter_grind" for item in fixtures))
        self.assertTrue(any(item["name"] == "strength_training" for item in fixtures))

    def test_strength_template_renders_clean_weight_and_labels(self) -> None:
        context = get_sample_template_context("strength_training")
        context["raw"]["training"]["garmin_last_activity"]["exercise_sets"][0]["weight"] = "Bodyweight"
        context["raw"]["training"]["garmin_last_activity"]["exercise_sets"][0]["weight_display"] = "Bodyweight"
        context["raw"]["training"]["garmin_last_activity"]["exercise_sets"][0]["weight_value"] = 0.0
        context["raw"]["training"]["garmin_last_activity"]["strength_summary_sets"][0]["sub_category"] = "N/A"
        context["raw"]["training"]["garmin_last_activity"]["strength_summary_sets"][0]["category"] = "PUSH_UP"
        template = PROFILE_TEMPLATE_DEFAULTS["strength_training"]
        result = render_template_text(template, context)
        self.assertTrue(result["ok"])
        rendered = str(result["description"])
        self.assertIn("weight Bodyweight", rendered)
        self.assertNotIn("N/a (", rendered)

    def test_misery_index_display_object_renders_value_and_emoji(self) -> None:
        context = get_sample_template_context()
        result = render_template_text("{{ misery.index }}|{{ misery.index.emoji }}|{{ misery.index.polarity }}", context)
        self.assertTrue(result["ok"])
        rendered = str(result["description"])
        self.assertEqual(rendered.split("|")[0], "14.9")
        self.assertEqual(rendered.split("|")[1], "😒")

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

    def test_profile_workspace_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            template_path = Path(td) / "description_template.j2"
            settings = _settings_for(template_path)
            profiles = list_template_profiles(settings)
            self.assertTrue(any(str(item.get("profile_id")) == "default" for item in profiles))
            default = next(item for item in profiles if str(item.get("profile_id")) == "default")
            self.assertEqual(default["label"], "Default")
            self.assertTrue(default["enabled"])
            self.assertTrue(default["locked"])
            self.assertTrue(any(str(item.get("profile_id")) == "strength_training" for item in profiles))
            strength = next(item for item in profiles if str(item.get("profile_id")) == "strength_training")
            self.assertEqual(strength["label"], "Strength Training")
            self.assertTrue(strength["enabled"])
            self.assertFalse(strength["locked"])
            self.assertTrue(any(str(item.get("profile_id")) == "incline_treadmill" for item in profiles))
            incline = next(item for item in profiles if str(item.get("profile_id")) == "incline_treadmill")
            self.assertEqual(incline["label"], "Incline Treadmill")
            self.assertTrue(incline["enabled"])
            self.assertFalse(incline["locked"])
            self.assertTrue(any(str(item.get("profile_id")) == "walk" for item in profiles))
            walk = next(item for item in profiles if str(item.get("profile_id")) == "walk")
            self.assertEqual(walk["label"], "Walk")
            self.assertTrue(walk["enabled"])
            self.assertFalse(walk["locked"])

            working = get_working_template_profile(settings)
            self.assertEqual(working["profile_id"], "default")

            strength_template = get_active_template(settings, profile_id="strength_training")
            self.assertIn("Sets:", strength_template["template"])
            self.assertIn("Reps:", strength_template["template"])
            incline_template = get_active_template(settings, profile_id="incline_treadmill")
            self.assertIn("∠ Incline: 15%", incline_template["template"])
            self.assertIn("Treadmill Elevation", incline_template["template"])
            walk_template = get_active_template(settings, profile_id="walk")
            self.assertIn("Misery Index", walk_template["template"])
            self.assertIn("Steps:", walk_template["template"])

    def test_profile_template_save_and_version_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            template_path = Path(td) / "description_template.j2"
            settings = _settings_for(template_path)

            save_active_template(settings, "Default {{ value }}", profile_id="default", author="tester")
            save_active_template(settings, "Trail {{ value }}", profile_id="trail", author="tester")
            save_active_template(settings, "Trail v2 {{ value }}", profile_id="trail", author="tester")

            default_active = get_active_template(settings, profile_id="default")
            trail_active = get_active_template(settings, profile_id="trail")
            self.assertIn("Default", default_active["template"])
            self.assertIn("Trail v2", trail_active["template"])

            default_versions = list_template_versions(settings, profile_id="default")
            trail_versions = list_template_versions(settings, profile_id="trail")
            self.assertGreaterEqual(len(default_versions), 1)
            self.assertGreaterEqual(len(trail_versions), 2)

    def test_profile_enable_disable_and_working_profile(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            template_path = Path(td) / "description_template.j2"
            settings = _settings_for(template_path)

            with self.assertRaises(ValueError):
                update_template_profile(settings, "default", enabled=False)

            updated_pet = update_template_profile(settings, "pet", enabled=True)
            self.assertTrue(updated_pet["enabled"])

            working_pet = set_working_template_profile(settings, "pet")
            self.assertEqual(working_pet["profile_id"], "pet")

            disabled_pet = update_template_profile(settings, "pet", enabled=False)
            self.assertFalse(disabled_pet["enabled"])
            working = get_working_template_profile(settings)
            self.assertEqual(working["profile_id"], "default")

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
