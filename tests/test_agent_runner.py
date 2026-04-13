import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from chronicle.agent_runner import (
    TemplateCustomizeRequest,
    agent_provider_status,
    generate_bundle_create,
    generate_plan_next_week_draft,
    generate_template_customization,
)


class TestAgentRunner(unittest.TestCase):
    def test_agent_provider_status_reports_remote_provider(self) -> None:
        settings = SimpleNamespace(
            agent_provider="remote_codex_exec",
            agent_remote_url="http://codex-vm:8788",
        )
        status = agent_provider_status(settings)
        self.assertTrue(status["available"])
        self.assertEqual(status["provider"], "remote_codex_exec")

    def test_generate_template_customization_local_exec(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_dir = Path(temp_dir) / "workspace"
            workspace_dir.mkdir(parents=True, exist_ok=True)
            settings = SimpleNamespace(
                agent_provider="local_codex_exec",
                editor_ai_codex_cli_path="/usr/bin/codex",
                editor_ai_workspace_dir=workspace_dir,
                editor_ai_timeout_seconds=30,
                editor_ai_codex_model=None,
            )

            def fake_run(cmd, input, text, capture_output, timeout, cwd, check):
                output_file = Path(cmd[cmd.index("--output-last-message") + 1])
                output_file.write_text(
                    json.dumps(
                        {
                            "suggested_text": "🌤️ {{ weather.aqi }}",
                            "placement_hint": "replace weather line",
                            "notes": "Compact version",
                        }
                    ),
                    encoding="utf-8",
                )
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch("chronicle.agent_runner.shutil.which", return_value="/usr/bin/codex"), patch(
                "chronicle.agent_runner.subprocess.run",
                side_effect=fake_run,
            ):
                result = generate_template_customization(
                    settings,
                    TemplateCustomizeRequest(
                        request_text="Make the weather line shorter.",
                        template_text="Weather {{ weather.aqi }}",
                        profile_id="default",
                        context_mode="sample",
                        available_context_keys=("activity", "weather"),
                    ),
                )

        self.assertEqual(result["placement_hint"], "replace weather line")
        self.assertEqual(result["profile_id"], "default")

    def test_generate_plan_next_week_draft_remote_provider(self) -> None:
        settings = SimpleNamespace(
            agent_provider="remote_codex_exec",
            agent_remote_url="http://codex-vm:8788",
            agent_remote_api_key="secret",
            agent_remote_timeout_seconds=30,
        )
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "status": "ok",
            "result": {
                "title": "Next week",
                "summary": "Keep volume steady.",
                "warnings": [],
                "days": [{"date_local": "2026-04-20", "planned_total_miles": 6}],
            },
        }
        with patch("chronicle.agent_runner.requests.post", return_value=response) as mock_post:
            result = generate_plan_next_week_draft(
                settings,
                user_request="Build next week.",
                week_start_local="2026-04-20",
                context_payload={"version": "abc123"},
            )
        self.assertEqual(result["title"], "Next week")
        self.assertEqual(mock_post.call_args.kwargs["headers"]["X-Chronicle-Agent-Key"], "secret")

    def test_generate_bundle_create_remote_error_raises(self) -> None:
        settings = SimpleNamespace(
            agent_provider="remote_codex_exec",
            agent_remote_url="http://codex-vm:8788",
            agent_remote_api_key=None,
            agent_remote_timeout_seconds=30,
        )
        response = Mock()
        response.status_code = 503
        response.json.return_value = {"status": "error", "error": "provider unavailable"}
        with patch("chronicle.agent_runner.requests.post", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "provider unavailable"):
                generate_bundle_create(
                    settings,
                    user_request="Create a new trail bundle.",
                    chronicle_context={},
                )


if __name__ == "__main__":
    unittest.main()
