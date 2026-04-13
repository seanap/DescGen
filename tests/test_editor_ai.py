import unittest
from types import SimpleNamespace
from unittest.mock import patch

from chronicle.editor_ai import (
    EditorAssistantRequest,
    editor_assistant_status,
    generate_editor_customization,
)


class TestEditorAi(unittest.TestCase):
    def test_editor_assistant_status_reports_provider_state(self) -> None:
        settings = SimpleNamespace(enable_editor_ai=True)
        with patch(
            "chronicle.editor_ai.agent_provider_status",
            return_value={
                "provider": "remote_codex_exec",
                "available": True,
                "reason": None,
                "remote_url": "http://codex-vm:8788",
                "protocol_version": "1",
            },
        ):
            status = editor_assistant_status(settings)
        self.assertTrue(status["enabled"])
        self.assertTrue(status["available"])
        self.assertEqual(status["provider"], "remote_codex_exec")
        self.assertEqual(status["remote_url"], "http://codex-vm:8788")

    def test_generate_editor_customization_requires_enable_flag(self) -> None:
        request = EditorAssistantRequest(
            request_text="Shorten the weather line.",
            template_text="Weather {{ weather.aqi }}",
            profile_id="default",
            context_mode="sample",
        )
        with self.assertRaisesRegex(RuntimeError, "disabled"):
            generate_editor_customization(SimpleNamespace(enable_editor_ai=False), request)

    def test_generate_editor_customization_delegates_to_agent_runner(self) -> None:
        settings = SimpleNamespace(enable_editor_ai=True)
        request = EditorAssistantRequest(
            request_text="Shorten the readiness line.",
            template_text="Readiness {{ training.readiness_score }}",
            profile_id="default",
            context_mode="sample",
            available_context_keys=("activity", "training"),
        )
        with patch(
            "chronicle.editor_ai.generate_template_customization",
            return_value={
                "suggested_text": "TR {{ training.readiness_score }}",
                "placement_hint": "replace readiness line",
                "notes": "Compact output",
            },
        ) as mock_generate:
            result = generate_editor_customization(settings, request)
        self.assertEqual(result["placement_hint"], "replace readiness line")
        passed_request = mock_generate.call_args.args[1]
        self.assertEqual(passed_request.profile_id, "default")
        self.assertEqual(passed_request.available_context_keys, ("activity", "training"))


if __name__ == "__main__":
    unittest.main()
