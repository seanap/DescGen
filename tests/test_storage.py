import sqlite3
import tempfile
import unittest
from pathlib import Path

import chronicle.storage as storage
from chronicle.storage import (
    acquire_runtime_lock,
    get_runtime_value,
    is_activity_processed,
    is_worker_healthy,
    mark_activity_processed,
    read_json,
    release_runtime_lock,
    set_runtime_value,
    set_worker_heartbeat,
    write_json,
)


class TestStorage(unittest.TestCase):
    def test_processed_activity_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "processed.log"
            self.assertFalse(is_activity_processed(path, 123))
            mark_activity_processed(path, 123)
            self.assertTrue(is_activity_processed(path, 123))
            mark_activity_processed(path, 123)
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines, ["123"])

    def test_json_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "latest.json"
            payload = {"activity_id": 123, "description": "hello"}
            write_json(path, payload)
            self.assertEqual(read_json(path), payload)

    def test_runtime_kv_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "processed.log"
            set_runtime_value(path, "worker.state", "sleeping")
            self.assertEqual(get_runtime_value(path, "worker.state"), "sleeping")

    def test_runtime_lock_acquire_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "processed.log"
            self.assertTrue(acquire_runtime_lock(path, "run_once", "owner-a", ttl_seconds=60))
            self.assertFalse(acquire_runtime_lock(path, "run_once", "owner-b", ttl_seconds=60))
            release_runtime_lock(path, "run_once", "owner-a")
            self.assertTrue(acquire_runtime_lock(path, "run_once", "owner-b", ttl_seconds=60))

    def test_worker_heartbeat_health(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "processed.log"
            self.assertFalse(is_worker_healthy(path, max_age_seconds=300))
            set_worker_heartbeat(path)
            self.assertTrue(is_worker_healthy(path, max_age_seconds=300))

    def test_runtime_lock_fails_closed_when_db_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "processed.log"
            original_connect = storage._connect_runtime_db

            def _raise_sqlite_error(_path: Path):
                raise sqlite3.Error("db unavailable")

            storage._connect_runtime_db = _raise_sqlite_error
            try:
                self.assertFalse(acquire_runtime_lock(path, "run_once", "owner-a", ttl_seconds=60))
            finally:
                storage._connect_runtime_db = original_connect


if __name__ == "__main__":
    unittest.main()
