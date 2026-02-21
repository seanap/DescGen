import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import chronicle.storage as storage
from chronicle.storage import (
    acquire_runtime_lock,
    claim_activity_job,
    complete_activity_job_run,
    enqueue_activity_job,
    get_activity_job,
    get_activity_state,
    get_runtime_value,
    is_activity_processed,
    is_worker_healthy,
    mark_activity_processed,
    requeue_expired_jobs,
    start_activity_job_run,
    read_json,
    release_runtime_lock,
    register_activity_discovery,
    set_runtime_value,
    set_worker_heartbeat,
    write_json,
    write_config_snapshot,
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

    def test_activity_job_state_transitions_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "processed.log"
            register_activity_discovery(path, 123, sport_type="Run")
            job_id = enqueue_activity_job(
                path,
                123,
                request_kind="auto_poll",
                requested_by="worker",
                force_update=False,
                max_attempts=3,
            )
            self.assertIsNotNone(job_id)
            self.assertTrue(claim_activity_job(path, str(job_id), owner="owner-a", lease_seconds=300))
            started = start_activity_job_run(path, str(job_id), owner="owner-a")
            self.assertIsNotNone(started)
            run_id = str(started["run_id"])
            outcome = complete_activity_job_run(
                path,
                str(job_id),
                run_id,
                owner="owner-a",
                outcome="succeeded",
                result={"status": "updated", "activity_id": 123},
            )
            self.assertEqual(outcome, "succeeded")

            job = get_activity_job(path, str(job_id))
            self.assertIsNotNone(job)
            assert job is not None
            self.assertEqual(job["status"], "succeeded")
            self.assertEqual(job["attempt_count"], 1)
            self.assertIsNotNone(job["finished_at_utc"])

            state = get_activity_state(path, 123)
            self.assertIsNotNone(state)
            assert state is not None
            self.assertEqual(state["state"], "succeeded")
            self.assertEqual(state["last_result_status"], "succeeded")

    def test_activity_job_retry_wait_promotes_to_failed_when_attempts_exhausted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "processed.log"
            job_id = enqueue_activity_job(
                path,
                321,
                request_kind="manual_activity",
                requested_by="manual",
                force_update=True,
                max_attempts=1,
            )
            self.assertIsNotNone(job_id)
            self.assertTrue(claim_activity_job(path, str(job_id), owner="owner-a", lease_seconds=300))
            started = start_activity_job_run(path, str(job_id), owner="owner-a")
            self.assertIsNotNone(started)

            outcome = complete_activity_job_run(
                path,
                str(job_id),
                str(started["run_id"]),
                owner="owner-a",
                outcome="retry_wait",
                error="transient error",
                retry_delay_seconds=60,
            )
            self.assertEqual(outcome, "failed_permanent")
            job = get_activity_job(path, str(job_id))
            self.assertIsNotNone(job)
            assert job is not None
            self.assertEqual(job["status"], "failed_permanent")

    def test_requeue_expired_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "processed.log"
            now = datetime.now(timezone.utc) + timedelta(minutes=2)
            job_id = enqueue_activity_job(
                path,
                555,
                request_kind="auto_poll",
                requested_by="worker",
                force_update=False,
            )
            self.assertIsNotNone(job_id)
            claimed = claim_activity_job(
                path,
                str(job_id),
                owner="owner-a",
                lease_seconds=30,
                now_utc=now,
            )
            self.assertTrue(claimed)

            requeued = requeue_expired_jobs(path, now_utc=now + timedelta(seconds=31))
            self.assertEqual(requeued, 1)
            job = get_activity_job(path, str(job_id))
            self.assertIsNotNone(job)
            assert job is not None
            self.assertEqual(job["status"], "queued")

    def test_write_config_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "processed.log"
            snapshot_id = write_config_snapshot(path, "test", {"timezone": "UTC"})
            self.assertIsNotNone(snapshot_id)
            self.assertTrue(str(snapshot_id))


if __name__ == "__main__":
    unittest.main()
