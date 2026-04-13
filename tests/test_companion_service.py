import os
import unittest
from unittest.mock import patch

from ai.chronicle_companion import service as companion_service


class TestCompanionService(unittest.TestCase):
    def setUp(self) -> None:
        self.client = companion_service.app.test_client()

    def test_handshake_endpoint(self) -> None:
        response = self.client.get("/v1/handshake")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertIn("bundle_create", payload["capabilities"])

    def test_execute_task_requires_api_key_when_configured(self) -> None:
        with patch.dict(os.environ, {"CHRONICLE_COMPANION_API_KEY": "secret"}, clear=False):
            response = self.client.post(
                "/v1/tasks/execute",
                json={"task": "template_customize", "payload": {}},
            )
        self.assertEqual(response.status_code, 401)

    def test_plan_next_week_fetches_context_payload_from_chronicle(self) -> None:
        with patch.dict(os.environ, {}, clear=False), patch.object(
            companion_service,
            "_chronicle_get",
            return_value={"status": "ok", "context": {"week_start_local": "2026-04-20", "version": "abc123"}},
        ) as mock_get, patch.object(
            companion_service,
            "generate_plan_next_week_draft",
            return_value={
                "title": "Next week",
                "summary": "Hold volume.",
                "warnings": [],
                "days": [{"date_local": "2026-04-20", "planned_total_miles": 6}],
            },
        ) as mock_generate:
            response = self.client.post(
                "/v1/tasks/execute",
                json={
                    "protocol_version": companion_service.COMPANION_PROTOCOL_VERSION,
                    "task": "plan_next_week_draft",
                    "payload": {
                        "user_request": "Build next week.",
                        "week_start_local": "2026-04-20",
                        "chronicle_context": {"base_url": "http://chronicle:1609", "api_key": "read-key"},
                    },
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_get.call_count, 1)
        self.assertEqual(
            mock_generate.call_args.kwargs["context_payload"]["week_start_local"],
            "2026-04-20",
        )


if __name__ == "__main__":
    unittest.main()
