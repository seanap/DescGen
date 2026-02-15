import unittest

try:
    import api_server
except ModuleNotFoundError:
    api_server = None


@unittest.skipIf(api_server is None, "Flask is not installed in this test environment.")
class TestApiServer(unittest.TestCase):
    def setUp(self) -> None:
        self.client = api_server.app.test_client()
        self._original_run_once = api_server.run_once

    def tearDown(self) -> None:
        api_server.run_once = self._original_run_once

    def test_rerun_latest_endpoint(self) -> None:
        api_server.run_once = lambda **kwargs: {"status": "updated", "kwargs": kwargs}
        response = self.client.post("/rerun/latest")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["result"]["kwargs"]["force_update"], True)

    def test_rerun_activity_endpoint(self) -> None:
        api_server.run_once = lambda **kwargs: {"status": "updated", "kwargs": kwargs}
        response = self.client.post("/rerun/activity/123456")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["result"]["kwargs"]["activity_id"], 123456)

    def test_rerun_generic_with_invalid_id(self) -> None:
        response = self.client.post("/rerun", json={"activity_id": "abc"})
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["status"], "error")


if __name__ == "__main__":
    unittest.main()
