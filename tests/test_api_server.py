import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import chronicle.api_server as api_server
except ModuleNotFoundError:
    api_server = None


@unittest.skipIf(api_server is None, "Flask is not installed in this test environment.")
class TestApiServer(unittest.TestCase):
    def setUp(self) -> None:
        self.client = api_server.app.test_client()
        self._original_run_once = api_server.run_once
        self._original_is_worker_healthy = api_server.is_worker_healthy
        self._original_get_dashboard_payload = api_server.get_dashboard_payload
        self._original_get_plan_payload = api_server.get_plan_payload
        self._original_settings = api_server.settings
        self._original_state_dir_env = os.environ.get("STATE_DIR")
        self._original_setup_env_file = os.environ.get("SETUP_ENV_FILE")

    def tearDown(self) -> None:
        api_server.run_once = self._original_run_once
        api_server.is_worker_healthy = self._original_is_worker_healthy
        api_server.get_dashboard_payload = self._original_get_dashboard_payload
        api_server.get_plan_payload = self._original_get_plan_payload
        api_server.settings = self._original_settings
        if self._original_state_dir_env is None:
            os.environ.pop("STATE_DIR", None)
        else:
            os.environ["STATE_DIR"] = self._original_state_dir_env
        if self._original_setup_env_file is None:
            os.environ.pop("SETUP_ENV_FILE", None)
        else:
            os.environ["SETUP_ENV_FILE"] = self._original_setup_env_file

    def _set_temp_state_dir(self, temp_dir: str) -> None:
        os.environ["STATE_DIR"] = temp_dir
        os.environ["SETUP_ENV_FILE"] = str(Path(temp_dir) / ".env")
        api_server.settings = api_server.Settings.from_env()
        api_server.settings.ensure_state_paths()

    def test_rerun_latest_endpoint(self) -> None:
        refresh_calls: list[tuple[tuple, dict]] = []
        api_server.run_once = lambda **kwargs: {"status": "updated", "kwargs": kwargs}
        api_server.get_dashboard_payload = lambda *args, **kwargs: refresh_calls.append((args, kwargs)) or {
            "generated_at": "2026-02-19T00:00:00+00:00",
            "years": [2026],
            "types": [],
            "type_meta": {},
            "other_bucket": "OtherSports",
            "aggregates": {},
            "units": {"distance": "mi", "elevation": "ft"},
            "week_start": "sunday",
            "activities": [],
        }
        response = self.client.post("/rerun/latest")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["result"]["kwargs"]["force_update"], True)
        self.assertEqual(payload.get("dashboard_refresh"), "updated")
        self.assertEqual(len(refresh_calls), 1)
        self.assertTrue(refresh_calls[0][1].get("force_refresh"))

    def test_rerun_activity_endpoint(self) -> None:
        refresh_calls: list[tuple[tuple, dict]] = []
        api_server.run_once = lambda **kwargs: {"status": "updated", "kwargs": kwargs}
        api_server.get_dashboard_payload = lambda *args, **kwargs: refresh_calls.append((args, kwargs)) or {
            "generated_at": "2026-02-19T00:00:00+00:00",
            "years": [2026],
            "types": [],
            "type_meta": {},
            "other_bucket": "OtherSports",
            "aggregates": {},
            "units": {"distance": "mi", "elevation": "ft"},
            "week_start": "sunday",
            "activities": [],
        }
        response = self.client.post("/rerun/activity/123456")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["result"]["kwargs"]["activity_id"], 123456)
        self.assertEqual(payload.get("dashboard_refresh"), "updated")
        self.assertEqual(len(refresh_calls), 1)

    def test_rerun_latest_skips_dashboard_refresh_when_not_updated(self) -> None:
        refresh_calls: list[tuple[tuple, dict]] = []
        api_server.run_once = lambda **kwargs: {"status": "already_processed", "kwargs": kwargs}
        api_server.get_dashboard_payload = lambda *args, **kwargs: refresh_calls.append((args, kwargs)) or {}
        response = self.client.post("/rerun/latest")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertNotIn("dashboard_refresh", payload)
        self.assertEqual(len(refresh_calls), 0)

    def test_rerun_generic_with_invalid_id(self) -> None:
        response = self.client.post("/rerun", json={"activity_id": "abc"})
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["status"], "error")

    def test_editor_schema_endpoint(self) -> None:
        response = self.client.get("/editor/schema")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(str(payload.get("context_source")).startswith("sample"))

    def test_editor_catalog_endpoint(self) -> None:
        response = self.client.get("/editor/catalog?context_mode=fixture&fixture_name=humid_hammer")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["has_context"])
        self.assertIn("catalog", payload)
        self.assertIn("fixtures", payload)
        self.assertIn("context_modes", payload)
        self.assertIn("helper_transforms", payload["catalog"])
        self.assertTrue(str(payload.get("context_source")).startswith("sample:"))

    def test_ready_endpoint(self) -> None:
        response = self.client.get("/ready")
        self.assertIn(response.status_code, {200, 503})
        payload = response.get_json()
        self.assertIn(payload["status"], {"ready", "not_ready"})
        self.assertIn("checks", payload)

    def test_ready_endpoint_requires_worker_heartbeat(self) -> None:
        api_server.is_worker_healthy = lambda *_args, **_kwargs: False
        response = self.client.get("/ready")
        self.assertEqual(response.status_code, 503)
        payload = response.get_json()
        self.assertEqual(payload["status"], "not_ready")
        self.assertFalse(payload["checks"]["worker_heartbeat_healthy"])

    def test_service_metrics_endpoint(self) -> None:
        response = self.client.get("/service-metrics")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertIn("cycle_service_calls", payload)

    def test_setup_page_endpoint(self) -> None:
        response = self.client.get("/setup")
        self.assertEqual(response.status_code, 200)

    def test_root_redirects_to_dashboard(self) -> None:
        response = self.client.get("/", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers.get("Location"), "/dashboard")

    def test_dashboard_page_endpoint(self) -> None:
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)

    def test_control_page_endpoint(self) -> None:
        response = self.client.get("/control")
        self.assertEqual(response.status_code, 200)

    def test_plan_page_endpoint(self) -> None:
        response = self.client.get("/plan")
        self.assertEqual(response.status_code, 200)

    def test_dashboard_data_endpoint(self) -> None:
        api_server.get_dashboard_payload = lambda *_args, **_kwargs: {
            "generated_at": "2026-02-19T00:00:00+00:00",
            "years": [2026],
            "types": ["Run"],
            "type_meta": {"Run": {"label": "Run", "accent": "#01cdfe"}},
            "other_bucket": "OtherSports",
            "aggregates": {},
            "units": {"distance": "mi", "elevation": "ft"},
            "week_start": "sunday",
            "activities": [],
        }
        response = self.client.get("/dashboard/data.json")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("years", payload)
        self.assertIn("types", payload)
        self.assertIn("activities", payload)

    def test_dashboard_data_endpoint_passes_response_mode_and_year(self) -> None:
        calls: list[dict] = []

        def _payload(*_args, **kwargs):
            calls.append(kwargs)
            return {
                "generated_at": "2026-02-19T00:00:00+00:00",
                "years": [2026],
                "types": ["Run"],
                "type_meta": {"Run": {"label": "Run", "accent": "#01cdfe"}},
                "other_bucket": "OtherSports",
                "aggregates": {},
                "units": {"distance": "mi", "elevation": "ft"},
                "week_start": "sunday",
                "activities": [],
            }

        api_server.get_dashboard_payload = _payload
        response = self.client.get("/dashboard/data.json?mode=year&year=2026&force=true")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].get("response_mode"), "year")
        self.assertEqual(calls[0].get("response_year"), "2026")
        self.assertTrue(bool(calls[0].get("force_refresh")))

    def test_dashboard_data_endpoint_returns_400_for_invalid_mode(self) -> None:
        def _raise(*_args, **_kwargs):
            raise ValueError("Invalid dashboard mode")

        api_server.get_dashboard_payload = _raise
        response = self.client.get("/dashboard/data.json?mode=bad")
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload.get("status"), "error")
        self.assertIn("Invalid dashboard mode", str(payload.get("error")))

    def test_plan_data_endpoint(self) -> None:
        calls: list[dict] = []

        def _payload(*_args, **kwargs):
            calls.append(kwargs)
            return {
                "status": "ok",
                "center_date": "2026-02-22",
                "window_days": 14,
                "rows": [],
            }

        api_server.get_plan_payload = _payload
        response = self.client.get("/plan/data.json?center_date=2026-02-22&window_days=14")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload.get("status"), "ok")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].get("center_date"), "2026-02-22")
        self.assertEqual(calls[0].get("window_days"), "14")

    def test_plan_data_endpoint_returns_400_for_invalid_center_date(self) -> None:
        def _raise(*_args, **_kwargs):
            raise ValueError("center_date must be YYYY-MM-DD.")

        api_server.get_plan_payload = _raise
        response = self.client.get("/plan/data.json?center_date=02/22/2026")
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload.get("status"), "error")
        self.assertIn("center_date", str(payload.get("error")))

    def test_plan_day_put_persists_distance_and_run_type(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self._set_temp_state_dir(temp_dir)
            response = self.client.put(
                "/plan/day/2026-02-22",
                json={
                    "distance": "6+4",
                    "run_type": "Easy",
                    "is_complete": False,
                },
            )
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload.get("status"), "ok")
            self.assertEqual(payload.get("session_count"), 2)
            self.assertEqual(payload.get("distance_saved"), "6+4")
            self.assertEqual(payload.get("run_type"), "Easy")

    def test_plan_day_put_rejects_invalid_distance_format(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self._set_temp_state_dir(temp_dir)
            response = self.client.put(
                "/plan/day/2026-02-22",
                json={
                    "distance": "6++4",
                    "run_type": "Easy",
                },
            )
            self.assertEqual(response.status_code, 400)
            payload = response.get_json()
            self.assertEqual(payload.get("status"), "error")
            self.assertIn("distance", str(payload.get("error")))

    def test_plan_day_put_accepts_is_complete_null_for_auto_reset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self._set_temp_state_dir(temp_dir)
            first = self.client.put(
                "/plan/day/2026-02-22",
                json={
                    "distance": "6",
                    "run_type": "Easy",
                    "is_complete": True,
                },
            )
            self.assertEqual(first.status_code, 200)
            second = self.client.put(
                "/plan/day/2026-02-22",
                json={
                    "distance": "6",
                    "run_type": "Easy",
                    "is_complete": None,
                },
            )
            self.assertEqual(second.status_code, 200)
            payload = second.get_json()
            self.assertEqual(payload.get("status"), "ok")
            self.assertIsNone(payload.get("is_complete"))

    def test_setup_config_and_env_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self._set_temp_state_dir(temp_dir)
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "TIMEZONE=UTC\nENABLE_WEATHER=true\n",
                encoding="utf-8",
            )

            get_response = self.client.get("/setup/api/config")
            self.assertEqual(get_response.status_code, 200)
            get_payload = get_response.get_json()
            self.assertEqual(get_payload["status"], "ok")
            self.assertIn("provider_fields", get_payload)
            self.assertIn("values", get_payload)
            self.assertEqual(get_payload["env_file"]["path"], str(env_path))

            put_response = self.client.put(
                "/setup/api/config",
                json={
                    "values": {
                        "TIMEZONE": "America/Chicago",
                        "ENABLE_WEATHER": False,
                        "WEATHER_API_KEY": "weather-secret",
                    }
                },
            )
            self.assertEqual(put_response.status_code, 200)
            put_payload = put_response.get_json()
            self.assertEqual(put_payload["status"], "ok")
            self.assertEqual(put_payload["values"]["TIMEZONE"], "America/Chicago")
            self.assertFalse(put_payload["values"]["ENABLE_WEATHER"])
            self.assertEqual(put_payload["values"]["WEATHER_API_KEY"], "")
            self.assertTrue(put_payload["secret_presence"]["WEATHER_API_KEY"])

            env_response = self.client.get("/setup/api/env")
            self.assertEqual(env_response.status_code, 200)
            env_payload = env_response.get_json()
            self.assertEqual(env_payload["status"], "ok")
            self.assertIn("TIMEZONE=America/Chicago", env_payload["env"])
            self.assertIn("ENABLE_WEATHER=false", env_payload["env"])
            self.assertIn("WEATHER_API_KEY=weather-secret", env_payload["env"])

            overrides_path = Path(temp_dir) / "setup_overrides.json"
            self.assertTrue(overrides_path.exists())
            env_written = env_path.read_text(encoding="utf-8")
            self.assertIn("TIMEZONE=America/Chicago", env_written)
            self.assertIn("ENABLE_WEATHER=false", env_written)
            self.assertIn("WEATHER_API_KEY=weather-secret", env_written)

    def test_setup_strava_oauth_start_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self._set_temp_state_dir(temp_dir)

            with patch.dict(
                os.environ,
                {
                    "STRAVA_CLIENT_ID": "",
                    "STRAVA_CLIENT_SECRET": "",
                    "CLIENT_ID": "",
                    "CLIENT_SECRET": "",
                },
                clear=False,
            ):
                missing_response = self.client.post("/setup/api/strava/oauth/start", json={})
                self.assertEqual(missing_response.status_code, 400)

            self.client.put(
                "/setup/api/config",
                json={
                    "values": {
                        "STRAVA_CLIENT_ID": "12345",
                        "STRAVA_CLIENT_SECRET": "secret-abc",
                    }
                },
            )

            start_response = self.client.post(
                "/setup/api/strava/oauth/start",
                json={"redirect_uri": "http://localhost:1609/setup/strava/callback"},
            )
            self.assertEqual(start_response.status_code, 200)
            start_payload = start_response.get_json()
            self.assertEqual(start_payload["status"], "ok")
            self.assertIn("strava.com/oauth/authorize", start_payload["authorize_url"])
            self.assertIn("client_id=12345", start_payload["authorize_url"])
            self.assertIn("state", start_payload)

    def test_editor_schema_sample_context_endpoint(self) -> None:
        response = self.client.get("/editor/schema?context_mode=sample")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["has_context"])
        self.assertTrue(str(payload["context_source"]).startswith("sample"))

    def test_editor_snippets_endpoint(self) -> None:
        response = self.client.get("/editor/snippets")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertIn("snippets", payload)

    def test_editor_starter_templates_endpoint(self) -> None:
        response = self.client.get("/editor/starter-templates")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertIn("starter_templates", payload)
        self.assertIn("count", payload)
        self.assertGreaterEqual(payload["count"], 1)

    def test_editor_profiles_endpoints(self) -> None:
        list_response = self.client.get("/editor/profiles")
        self.assertEqual(list_response.status_code, 200)
        list_payload = list_response.get_json()
        self.assertEqual(list_payload["status"], "ok")
        self.assertIn("profiles", list_payload)
        self.assertTrue(any(str(item.get("profile_id")) == "default" for item in list_payload["profiles"]))

        update_response = self.client.put(
            "/editor/profiles/pet",
            json={"enabled": True},
        )
        self.assertEqual(update_response.status_code, 200)
        update_payload = update_response.get_json()
        self.assertEqual(update_payload["status"], "ok")
        self.assertTrue(update_payload["profile"]["enabled"])

        working_response = self.client.post(
            "/editor/profiles/working",
            json={"profile_id": "pet"},
        )
        self.assertEqual(working_response.status_code, 200)
        working_payload = working_response.get_json()
        self.assertEqual(working_payload["status"], "ok")
        self.assertEqual(working_payload["working_profile_id"], "pet")

        reset_response = self.client.post(
            "/editor/profiles/working",
            json={"profile_id": "default"},
        )
        self.assertEqual(reset_response.status_code, 200)
        self.client.put("/editor/profiles/pet", json={"enabled": False})

    def test_editor_profile_put_accepts_string_false(self) -> None:
        response = self.client.put(
            "/editor/profiles/long_run",
            json={"enabled": "false"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertFalse(payload["profile"]["enabled"])

    def test_editor_profile_put_rejects_invalid_enabled_value(self) -> None:
        response = self.client.put(
            "/editor/profiles/long_run",
            json={"enabled": "not-a-bool"},
        )
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["status"], "error")

    def test_editor_repository_endpoints(self) -> None:
        list_response = self.client.get("/editor/repository/templates")
        self.assertEqual(list_response.status_code, 200)
        list_payload = list_response.get_json()
        self.assertEqual(list_payload["status"], "ok")
        self.assertIn("templates", list_payload)

        save_as_response = self.client.post(
            "/editor/repository/save_as",
            json={
                "template": "Repo {{ activity.distance_miles }}",
                "name": "Repo Template",
                "author": "tester",
                "context_mode": "sample",
            },
        )
        self.assertEqual(save_as_response.status_code, 200)
        save_payload = save_as_response.get_json()
        self.assertEqual(save_payload["status"], "ok")
        template_id = save_payload["template_record"]["template_id"]

        get_response = self.client.get(f"/editor/repository/template/{template_id}")
        self.assertEqual(get_response.status_code, 200)
        get_payload = get_response.get_json()
        self.assertEqual(get_payload["status"], "ok")
        self.assertEqual(get_payload["template_record"]["name"], "Repo Template")

        update_response = self.client.put(
            f"/editor/repository/template/{template_id}",
            json={
                "template": "Repo Updated {{ activity.distance_miles }}",
                "name": "Repo Template v2",
                "author": "tester2",
                "context_mode": "sample",
            },
        )
        self.assertEqual(update_response.status_code, 200)
        update_payload = update_response.get_json()
        self.assertEqual(update_payload["status"], "ok")
        self.assertEqual(update_payload["template_record"]["author"], "tester2")

        duplicate_response = self.client.post(
            f"/editor/repository/template/{template_id}/duplicate",
            json={"name": "Repo Copy"},
        )
        self.assertEqual(duplicate_response.status_code, 200)
        duplicate_payload = duplicate_response.get_json()
        self.assertEqual(duplicate_payload["status"], "ok")
        self.assertNotEqual(duplicate_payload["template_record"]["template_id"], template_id)

        export_response = self.client.get(f"/editor/repository/template/{template_id}/export")
        self.assertEqual(export_response.status_code, 200)
        export_payload = export_response.get_json()
        self.assertEqual(export_payload["status"], "ok")
        self.assertEqual(export_payload["name"], "Repo Template v2")
        self.assertEqual(export_payload["author"], "tester2")

        import_response = self.client.post(
            "/editor/repository/import",
            json={
                "bundle": export_payload,
                "author": "importer",
                "context_mode": "sample",
            },
        )
        self.assertEqual(import_response.status_code, 200)
        import_payload = import_response.get_json()
        self.assertEqual(import_payload["status"], "ok")
        self.assertIn("template_id", import_payload["template_record"])

    def test_editor_sample_context_endpoint(self) -> None:
        response = self.client.get("/editor/context/sample")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertIn("context", payload)

    def test_editor_page_endpoint(self) -> None:
        response = self.client.get("/editor")
        self.assertEqual(response.status_code, 200)

    def test_editor_default_template_endpoint(self) -> None:
        response = self.client.get("/editor/template/default")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertIn("template", payload)

    def test_editor_template_export_endpoint(self) -> None:
        response = self.client.get("/editor/template/export")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertIn("bundle_version", payload)
        self.assertIn("template", payload)
        self.assertIn("exported_at_utc", payload)

    def test_editor_template_import_endpoint(self) -> None:
        response = self.client.post(
            "/editor/template/import",
            json={
                "bundle": {
                    "template": "Imported {{ activity.distance_miles }}",
                    "name": "Imported Template",
                    "exported_at_utc": "2026-02-16T00:00:00Z",
                },
                "author": "tester",
                "context_mode": "sample",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertIn("saved_version", payload)
        self.assertIn("active", payload)

    def test_editor_template_import_rejects_invalid_payload(self) -> None:
        response = self.client.post(
            "/editor/template/import",
            json={"bundle": {"name": "Missing template"}},
        )
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["status"], "error")

    def test_editor_fixtures_endpoint(self) -> None:
        response = self.client.get("/editor/fixtures")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertIn("fixtures", payload)

    def test_editor_validate_endpoint(self) -> None:
        response = self.client.post(
            "/editor/validate",
            json={"template": "Hello {{ activity.distance_miles }}"},
        )
        # Can be 200 if context exists, 400 if strict validation fails due missing context vars.
        self.assertIn(response.status_code, {200, 400})

    def test_editor_preview_sample_context(self) -> None:
        response = self.client.post(
            "/editor/preview",
            json={
                "context_mode": "sample",
                "template": "Miles {{ activity.distance_miles }}",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(str(payload["context_source"]).startswith("sample"))

    def test_editor_preview_fixture_context(self) -> None:
        response = self.client.post(
            "/editor/preview",
            json={
                "context_mode": "fixture",
                "fixture_name": "winter_grind",
                "template": "MI {{ weather.misery_index }}",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(str(payload["context_source"]).startswith("sample:"))

    def test_editor_preview_invalid_context_mode(self) -> None:
        response = self.client.post(
            "/editor/preview",
            json={"context_mode": "nope", "template": "{{ streak_days }}"},
        )
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["status"], "error")

    def test_editor_template_put_respects_context_mode(self) -> None:
        response = self.client.put(
            "/editor/template",
            json={
                "template": "Fitness {{ intervals.fitness }}",
                "author": "tester",
                "name": "Mode Aware Template",
                "source": "test",
                "context_mode": "sample",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(str(payload.get("context_source")).startswith("sample"))

    def test_editor_template_profile_scoping(self) -> None:
        save_response = self.client.put(
            "/editor/template",
            json={
                "template": "Trail {{ activity.distance_miles }}",
                "author": "tester",
                "name": "Trail Template",
                "source": "test",
                "context_mode": "sample",
                "profile_id": "trail",
            },
        )
        self.assertEqual(save_response.status_code, 200)
        save_payload = save_response.get_json()
        self.assertEqual(save_payload["status"], "ok")
        self.assertEqual(save_payload["profile_id"], "trail")

        load_response = self.client.get("/editor/template?profile_id=trail")
        self.assertEqual(load_response.status_code, 200)
        load_payload = load_response.get_json()
        self.assertEqual(load_payload["status"], "ok")
        self.assertEqual(load_payload["profile_id"], "trail")
        self.assertIn("Trail", load_payload["template"])

    def test_editor_template_put_rejects_invalid_context_mode(self) -> None:
        response = self.client.put(
            "/editor/template",
            json={
                "template": "Miles {{ activity.distance_miles }}",
                "context_mode": "nope",
            },
        )
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["status"], "error")

    def test_editor_template_versions_and_rollback_endpoints(self) -> None:
        put_response = self.client.put(
            "/editor/template",
            json={
                "template": "Miles {{ activity.distance_miles }}",
                "author": "tester",
                "name": "Unit Test Template",
                "source": "test",
            },
        )
        self.assertEqual(put_response.status_code, 200)

        versions_response = self.client.get("/editor/template/versions")
        self.assertEqual(versions_response.status_code, 200)
        versions_payload = versions_response.get_json()
        self.assertEqual(versions_payload["status"], "ok")
        self.assertGreaterEqual(len(versions_payload["versions"]), 1)
        version_id = versions_payload["versions"][0]["version_id"]

        version_response = self.client.get(f"/editor/template/version/{version_id}")
        self.assertEqual(version_response.status_code, 200)
        version_payload = version_response.get_json()
        self.assertEqual(version_payload["status"], "ok")
        self.assertIn("template", version_payload["version"])

        rollback_response = self.client.post(
            "/editor/template/rollback",
            json={"version_id": version_id, "author": "tester"},
        )
        self.assertEqual(rollback_response.status_code, 200)
        rollback_payload = rollback_response.get_json()
        self.assertEqual(rollback_payload["status"], "ok")


if __name__ == "__main__":
    unittest.main()
