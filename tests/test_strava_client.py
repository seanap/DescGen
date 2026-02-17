import unittest

from strava_client import StravaClient, get_gap_speed_mps, mps_to_pace


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


if __name__ == "__main__":
    unittest.main()
