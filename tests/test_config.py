import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from chronicle.config import Settings
from chronicle.storage import write_json


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

    def test_setup_overrides_are_applied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            state_dir = Path(tmp_dir)
            write_json(
                state_dir / "setup_overrides.json",
                {
                    "version": 1,
                    "updated_at_utc": "2999-01-01T00:00:00+00:00",
                    "values": {
                        "STRAVA_CLIENT_ID": "override-client-id",
                        "STRAVA_CLIENT_SECRET": "override-client-secret",
                        "STRAVA_REFRESH_TOKEN": "override-refresh-token",
                        "TIMEZONE": "America/Phoenix",
                        "ENABLE_WEATHER": False,
                        "ENABLE_CRONO_API": True,
                    },
                },
            )
            with patch.dict(
                os.environ,
                {
                    "STATE_DIR": str(state_dir),
                    "STRAVA_CLIENT_ID": "env-client-id",
                    "STRAVA_CLIENT_SECRET": "env-client-secret",
                    "STRAVA_REFRESH_TOKEN": "env-refresh-token",
                    "TIMEZONE": "UTC",
                    "ENABLE_WEATHER": "true",
                    "ENABLE_CRONO_API": "false",
                },
                clear=True,
            ):
                settings = Settings.from_env()
                self.assertEqual(settings.strava_client_id, "override-client-id")
                self.assertEqual(settings.strava_client_secret, "override-client-secret")
                self.assertEqual(settings.strava_refresh_token, "override-refresh-token")
                self.assertEqual(settings.timezone, "America/Phoenix")
                self.assertFalse(settings.enable_weather)
                self.assertTrue(settings.enable_crono_api)

    def test_stale_setup_overrides_do_not_override_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            state_dir = Path(tmp_dir)
            write_json(
                state_dir / "setup_overrides.json",
                {
                    "version": 1,
                    "updated_at_utc": "2000-01-01T00:00:00+00:00",
                    "values": {
                        "TIMEZONE": "America/Phoenix",
                        "ENABLE_WEATHER": False,
                    },
                },
            )
            with patch.dict(
                os.environ,
                {
                    "STATE_DIR": str(state_dir),
                    "STRAVA_CLIENT_ID": "env-client-id",
                    "STRAVA_CLIENT_SECRET": "env-client-secret",
                    "STRAVA_REFRESH_TOKEN": "env-refresh-token",
                    "TIMEZONE": "UTC",
                    "ENABLE_WEATHER": "true",
                },
                clear=True,
            ):
                settings = Settings.from_env()
                self.assertEqual(settings.timezone, "UTC")
                self.assertTrue(settings.enable_weather)


if __name__ == "__main__":
    unittest.main()
