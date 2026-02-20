import unittest
from datetime import datetime

import chronicle.strava_client as strava_client
from chronicle.strava_client import StravaClient, get_gap_speed_mps, mps_to_pace


class _DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _DummyClient:
    def __init__(self):
        self.calls = []

    def _request(self, method, path, *, params=None, data=None):
        self.calls.append(
            {
                "method": method,
                "path": path,
                "params": params,
                "data": data,
            }
        )
        return _DummyResponse({"ok": True})


class TestStravaUtils(unittest.TestCase):
    def test_mps_to_pace_handles_missing(self) -> None:
        self.assertEqual(mps_to_pace(None), "N/A")
        self.assertEqual(mps_to_pace(0), "N/A")

    def test_mps_to_pace_formats_minutes_seconds(self) -> None:
        # 4.470388 m/s is about 6:00 min/mi
        self.assertEqual(mps_to_pace(4.470388), "6:00")

    def test_get_gap_speed_prefers_grade_adjusted_keys(self) -> None:
        activity = {
            "avgGradeAdjustedSpeed": 4.2,
            "average_speed": 3.9,
        }
        self.assertEqual(get_gap_speed_mps(activity), 4.2)

    def test_get_gap_speed_does_not_fallback_to_average_speed(self) -> None:
        activity = {"average_speed": 4.0}
        self.assertIsNone(get_gap_speed_mps(activity))

    def test_get_activity_details_requests_all_segment_efforts(self) -> None:
        client = _DummyClient()
        payload = StravaClient.get_activity_details(client, 12345)
        self.assertEqual(payload, {"ok": True})
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0]["method"], "GET")
        self.assertEqual(client.calls[0]["path"], "/activities/12345")
        self.assertEqual(client.calls[0]["params"], {"include_all_efforts": "true"})

    def test_get_activities_after_honors_max_page_cap(self) -> None:
        class _PagedClient:
            def __init__(self):
                self.calls = []

            def _request(self, method, path, *, params=None, data=None):
                self.calls.append({"method": method, "path": path, "params": params, "data": data})
                per_page = int(params["per_page"])
                return _DummyResponse([{"id": len(self.calls) * 1000 + idx} for idx in range(per_page)])

        original_cap = strava_client.MAX_ACTIVITY_PAGES
        strava_client.MAX_ACTIVITY_PAGES = 3
        try:
            client = _PagedClient()
            activities = StravaClient.get_activities_after(
                client,
                datetime(2026, 1, 1),
                per_page=2,
            )
            self.assertEqual(len(client.calls), 3)
            self.assertEqual(len(activities), 6)
        finally:
            strava_client.MAX_ACTIVITY_PAGES = original_cap


if __name__ == "__main__":
    unittest.main()
