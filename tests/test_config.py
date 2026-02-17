import os
import unittest
from unittest.mock import patch

from config import Settings


class TestConfigEnvAliases(unittest.TestCase):
    def test_reads_canonical_strava_env_names(self) -> None:
        with patch.dict(
            os.environ,
            {
                "STRAVA_CLIENT_ID": "new-id",
                "STRAVA_CLIENT_SECRET": "new-secret",
                "STRAVA_REFRESH_TOKEN": "new-refresh",
                "STRAVA_ACCESS_TOKEN": "new-access",
            },
            clear=True,
        ):
            settings = Settings.from_env()
            self.assertEqual(settings.strava_client_id, "new-id")
            self.assertEqual(settings.strava_client_secret, "new-secret")
            self.assertEqual(settings.strava_refresh_token, "new-refresh")
            self.assertEqual(settings.strava_access_token, "new-access")

    def test_legacy_strava_aliases_still_work(self) -> None:
        with patch.dict(
            os.environ,
            {
                "CLIENT_ID": "legacy-id",
                "CLIENT_SECRET": "legacy-secret",
                "REFRESH_TOKEN": "legacy-refresh",
                "ACCESS_TOKEN": "legacy-access",
            },
            clear=True,
        ):
            settings = Settings.from_env()
            self.assertEqual(settings.strava_client_id, "legacy-id")
            self.assertEqual(settings.strava_client_secret, "legacy-secret")
            self.assertEqual(settings.strava_refresh_token, "legacy-refresh")
            self.assertEqual(settings.strava_access_token, "legacy-access")

    def test_canonical_env_takes_precedence_over_legacy(self) -> None:
        with patch.dict(
            os.environ,
            {
                "STRAVA_CLIENT_ID": "new-id",
                "CLIENT_ID": "legacy-id",
                "STRAVA_CLIENT_SECRET": "new-secret",
                "CLIENT_SECRET": "legacy-secret",
                "STRAVA_REFRESH_TOKEN": "new-refresh",
                "REFRESH_TOKEN": "legacy-refresh",
                "STRAVA_ACCESS_TOKEN": "new-access",
                "ACCESS_TOKEN": "legacy-access",
                "INTERVALS_USER_ID": "new-user",
                "USER_ID": "legacy-user",
            },
            clear=True,
        ):
            settings = Settings.from_env()
            self.assertEqual(settings.strava_client_id, "new-id")
            self.assertEqual(settings.strava_client_secret, "new-secret")
            self.assertEqual(settings.strava_refresh_token, "new-refresh")
            self.assertEqual(settings.strava_access_token, "new-access")
            self.assertEqual(settings.intervals_user_id, "new-user")

    def test_timezone_and_intervals_user_aliases(self) -> None:
        with patch.dict(
            os.environ,
            {
                "CLIENT_ID": "legacy-id",
                "CLIENT_SECRET": "legacy-secret",
                "REFRESH_TOKEN": "legacy-refresh",
                "USER_ID": "legacy-user",
                "TZ": "America/Chicago",
            },
            clear=True,
        ):
            settings = Settings.from_env()
            self.assertEqual(settings.intervals_user_id, "legacy-user")
            self.assertEqual(settings.timezone, "America/Chicago")

        with patch.dict(
            os.environ,
            {
                "CLIENT_ID": "legacy-id",
                "CLIENT_SECRET": "legacy-secret",
                "REFRESH_TOKEN": "legacy-refresh",
                "INTERVALS_USER_ID": "canonical-user",
                "TIMEZONE": "America/Denver",
                "TZ": "America/Chicago",
            },
            clear=True,
        ):
            settings = Settings.from_env()
            self.assertEqual(settings.intervals_user_id, "canonical-user")
            self.assertEqual(settings.timezone, "America/Denver")


if __name__ == "__main__":
    unittest.main()
