import unittest

from strava_utils import mps_to_pace


class TestStravaUtils(unittest.TestCase):
    def test_mps_to_pace_handles_missing(self) -> None:
        self.assertEqual(mps_to_pace(None), "N/A")
        self.assertEqual(mps_to_pace(0), "N/A")

    def test_mps_to_pace_formats_minutes_seconds(self) -> None:
        # 4.470388 m/s is about 6:00 min/mi
        self.assertEqual(mps_to_pace(4.470388), "6:00")


if __name__ == "__main__":
    unittest.main()
