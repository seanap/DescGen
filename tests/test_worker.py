import unittest
from datetime import datetime, timezone

from worker import _in_quiet_hours, _seconds_until_quiet_end


class TestWorkerTiming(unittest.TestCase):
    def test_quiet_hours_simple_range(self) -> None:
        self.assertTrue(_in_quiet_hours(0, 0, 4))
        self.assertTrue(_in_quiet_hours(3, 0, 4))
        self.assertFalse(_in_quiet_hours(4, 0, 4))
        self.assertFalse(_in_quiet_hours(23, 0, 4))

    def test_quiet_hours_wrap_range(self) -> None:
        self.assertTrue(_in_quiet_hours(23, 22, 3))
        self.assertTrue(_in_quiet_hours(1, 22, 3))
        self.assertFalse(_in_quiet_hours(12, 22, 3))

    def test_seconds_until_quiet_end(self) -> None:
        now = datetime(2026, 2, 15, 1, 30, 0, tzinfo=timezone.utc)
        seconds = _seconds_until_quiet_end(now, 0, 4)
        self.assertEqual(seconds, 9000)


if __name__ == "__main__":
    unittest.main()
