import unittest
from datetime import datetime, timezone

from worker import _in_quiet_hours, _seconds_until_quiet_end, _should_refresh_dashboard


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


class TestWorkerDashboardRefresh(unittest.TestCase):
    def test_should_refresh_dashboard_on_updated_status(self) -> None:
        self.assertTrue(_should_refresh_dashboard({"status": "updated"}))
        self.assertTrue(_should_refresh_dashboard({"status": "UPDATED"}))

    def test_should_not_refresh_dashboard_for_non_updated_status(self) -> None:
        self.assertFalse(_should_refresh_dashboard({"status": "already_processed"}))
        self.assertFalse(_should_refresh_dashboard({"status": "no_activities"}))
        self.assertFalse(_should_refresh_dashboard({"status": "locked"}))
        self.assertFalse(_should_refresh_dashboard({"status": "error"}))
        self.assertFalse(_should_refresh_dashboard({}))
        self.assertFalse(_should_refresh_dashboard(None))


if __name__ == "__main__":
    unittest.main()
