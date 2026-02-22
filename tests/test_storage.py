import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import chronicle.storage as storage
from chronicle.storage import (
    acquire_runtime_lock,
    claim_activity_job,
    cleanup_runtime_state,
    complete_activity_job_run,
    enqueue_activity_job,
    get_activity_job,
    get_activity_state,
    get_plan_day,
    list_plan_days,
    list_plan_sessions,
    get_runtime_value,
    get_runtime_values,
    is_activity_processed,
    is_worker_healthy,
    mark_activity_processed,
    requeue_expired_jobs,
    start_activity_job_run,
    read_json,
    release_runtime_lock,
    replace_plan_sessions_for_day,
    register_activity_discovery,
    set_runtime_value,
    set_runtime_values,
    set_worker_heartbeat,
    upsert_plan_day,
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

    def test_runtime_kv_batch_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "processed.log"
            set_runtime_values(
                path,
                {
                    "worker.state": "sleeping",
                    "worker.next_wake_utc": "2026-02-22T00:00:00+00:00",
                },
            )
            self.assertEqual(get_runtime_value(path, "worker.state"), "sleeping")
            self.assertEqual(
                get_runtime_value(path, "worker.next_wake_utc"),
                "2026-02-22T00:00:00+00:00",
            )

    def test_runtime_multi_get_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "processed.log"
            set_runtime_values(
                path,
                {
                    "worker.state": "running",
                    "worker.next_wake_utc": "2026-02-22T00:00:00+00:00",
                },
            )
            values = get_runtime_values(
                path,
                [
                    "worker.state",
                    "worker.next_wake_utc",
                    "worker.missing",
                ],
            )
            self.assertEqual(values.get("worker.state"), "running")
            self.assertEqual(
                values.get("worker.next_wake_utc"),
                "2026-02-22T00:00:00+00:00",
            )
            self.assertNotIn("worker.missing", values)

    def test_plan_day_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "processed.log"
            saved = upsert_plan_day(
                path,
                date_local="2026-02-22",
                timezone_name="America/New_York",
                run_type="Easy",
                planned_total_miles=6.2,
                is_complete=False,
                notes="Plan day",
            )
            self.assertTrue(saved)
            rows = list_plan_days(
                path,
                start_date="2026-02-01",
                end_date="2026-02-28",
            )
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["date_local"], "2026-02-22")
            self.assertEqual(row["run_type"], "Easy")
            self.assertAlmostEqual(float(row["planned_total_miles"]), 6.2, places=3)
            self.assertEqual(row["is_complete"], False)

    def test_plan_sessions_replace_and_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "processed.log"
            self.assertTrue(
                replace_plan_sessions_for_day(
                    path,
                    date_local="2026-02-22",
                    sessions=[
                        {"ordinal": 1, "planned_miles": 6.0},
                        {"ordinal": 2, "planned_miles": 4.0},
                    ],
                )
            )
            sessions = list_plan_sessions(
                path,
                start_date="2026-02-01",
                end_date="2026-02-28",
            )
            self.assertIn("2026-02-22", sessions)
            day_sessions = sessions["2026-02-22"]
            self.assertEqual(len(day_sessions), 2)
            self.assertEqual(day_sessions[0]["ordinal"], 1)
            self.assertAlmostEqual(float(day_sessions[0]["planned_miles"]), 6.0, places=3)
            self.assertEqual(day_sessions[1]["ordinal"], 2)
            self.assertAlmostEqual(float(day_sessions[1]["planned_miles"]), 4.0, places=3)

            day = get_plan_day(path, date_local="2026-02-22")
            self.assertIsNotNone(day)

    def test_runtime_schema_initializes_once_per_db_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "processed.log"
            with mock.patch(
                "chronicle.storage._initialize_runtime_schema",
                wraps=storage._initialize_runtime_schema,
            ) as init_schema:
                set_runtime_value(path, "worker.state", "running")
                self.assertEqual(get_runtime_value(path, "worker.state"), "running")
                set_runtime_value(path, "worker.state", "sleeping")
            self.assertEqual(init_schema.call_count, 1)

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

    def test_cleanup_runtime_state_prunes_stale_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "processed.log"
            now = datetime(2026, 2, 22, 12, 0, tzinfo=timezone.utc)
            stale_iso = (now - timedelta(days=10)).isoformat()
            recent_iso = (now - timedelta(minutes=30)).isoformat()

            set_runtime_values(
                path,
                {
                    "service.test.cache.old": {"value": 1},
                    "service.test.cache.new": {"value": 2},
                    "worker.state": "sleeping",
                    "setup.strava.oauth": {"state": "stale"},
                    "cycle.period_stats.activities_cache": {"activities": []},
                },
            )

            old_snapshot = write_config_snapshot(path, "test", {"n": 1})
            mid_snapshot = write_config_snapshot(path, "test", {"n": 2})
            fresh_snapshot = write_config_snapshot(path, "test", {"n": 3})
            self.assertIsNotNone(old_snapshot)
            self.assertIsNotNone(mid_snapshot)
            self.assertIsNotNone(fresh_snapshot)
            assert isinstance(old_snapshot, str)
            assert isinstance(mid_snapshot, str)
            assert isinstance(fresh_snapshot, str)

            old_job = enqueue_activity_job(
                path,
                999,
                request_kind="auto_poll",
                requested_by="worker",
                force_update=False,
                available_at_utc=now - timedelta(days=41),
            )
            self.assertIsNotNone(old_job)
            assert isinstance(old_job, str)
            self.assertTrue(
                claim_activity_job(
                    path,
                    old_job,
                    owner="owner-a",
                    lease_seconds=300,
                    now_utc=now - timedelta(days=40),
                )
            )
            old_started = start_activity_job_run(
                path,
                old_job,
                owner="owner-a",
                now_utc=now - timedelta(days=40) + timedelta(minutes=1),
            )
            self.assertIsNotNone(old_started)
            assert isinstance(old_started, dict)
            self.assertEqual(
                complete_activity_job_run(
                    path,
                    old_job,
                    str(old_started["run_id"]),
                    owner="owner-a",
                    outcome="succeeded",
                    now_utc=now - timedelta(days=40) + timedelta(minutes=2),
                ),
                "succeeded",
            )

            fresh_job = enqueue_activity_job(
                path,
                999,
                request_kind="auto_poll",
                requested_by="worker",
                force_update=False,
                available_at_utc=now - timedelta(minutes=5),
            )
            self.assertIsNotNone(fresh_job)
            assert isinstance(fresh_job, str)
            self.assertTrue(
                claim_activity_job(
                    path,
                    fresh_job,
                    owner="owner-a",
                    lease_seconds=300,
                    now_utc=now - timedelta(minutes=2),
                )
            )
            fresh_started = start_activity_job_run(
                path,
                fresh_job,
                owner="owner-a",
                now_utc=now - timedelta(minutes=1),
            )
            self.assertIsNotNone(fresh_started)
            assert isinstance(fresh_started, dict)
            self.assertEqual(
                complete_activity_job_run(
                    path,
                    fresh_job,
                    str(fresh_started["run_id"]),
                    owner="owner-a",
                    outcome="succeeded",
                    now_utc=now,
                ),
                "succeeded",
            )

            self.assertTrue(
                acquire_runtime_lock(
                    path,
                    "stale-lock",
                    "owner-a",
                    ttl_seconds=30,
                    now_utc=now - timedelta(days=5),
                )
            )

            with storage._connect_runtime_db(path) as conn:
                conn.execute(
                    """
                    UPDATE runtime_kv
                    SET updated_at_utc = ?
                    WHERE key IN (
                        'service.test.cache.old',
                        'setup.strava.oauth',
                        'cycle.period_stats.activities_cache'
                    )
                    """,
                    (stale_iso,),
                )
                conn.execute(
                    """
                    UPDATE runtime_kv
                    SET updated_at_utc = ?
                    WHERE key = 'service.test.cache.new'
                    """,
                    (recent_iso,),
                )
                conn.execute(
                    "UPDATE config_snapshots SET created_at_utc = ? WHERE snapshot_id = ?",
                    ((now - timedelta(days=20)).isoformat(), old_snapshot),
                )
                conn.execute(
                    "UPDATE config_snapshots SET created_at_utc = ? WHERE snapshot_id = ?",
                    ((now - timedelta(days=10)).isoformat(), mid_snapshot),
                )
                conn.execute(
                    "UPDATE config_snapshots SET created_at_utc = ? WHERE snapshot_id = ?",
                    (recent_iso, fresh_snapshot),
                )

            stats = cleanup_runtime_state(
                path,
                now_utc=now,
                service_cache_retention_seconds=3600,
                transient_runtime_retention_seconds=3600,
                config_snapshot_retention_count=2,
                terminal_job_retention_days=30,
                expired_lock_retention_seconds=3600,
            )

            self.assertEqual(get_runtime_value(path, "service.test.cache.old"), None)
            self.assertEqual(get_runtime_value(path, "setup.strava.oauth"), None)
            self.assertEqual(get_runtime_value(path, "cycle.period_stats.activities_cache"), None)
            self.assertEqual(get_runtime_value(path, "service.test.cache.new"), {"value": 2})
            self.assertEqual(get_runtime_value(path, "worker.state"), "sleeping")
            self.assertIsNone(get_activity_job(path, old_job))
            self.assertIsNotNone(get_activity_job(path, fresh_job))

            with storage._connect_runtime_db(path) as conn:
                snapshot_count = conn.execute("SELECT COUNT(1) FROM config_snapshots").fetchone()[0]
                stale_lock_rows = conn.execute(
                    "SELECT COUNT(1) FROM runtime_locks WHERE lock_name = ?",
                    ("stale-lock",),
                ).fetchone()[0]
            self.assertEqual(int(snapshot_count), 2)
            self.assertEqual(int(stale_lock_rows), 0)
            self.assertGreaterEqual(int(stats.get("runtime_kv_service_cache_deleted", 0)), 1)
            self.assertGreaterEqual(int(stats.get("runtime_kv_transient_deleted", 0)), 2)
            self.assertGreaterEqual(int(stats.get("config_snapshots_deleted", 0)), 1)
            self.assertGreaterEqual(int(stats.get("runs_deleted", 0)), 1)
            self.assertGreaterEqual(int(stats.get("jobs_deleted", 0)), 1)
            self.assertGreaterEqual(int(stats.get("expired_locks_deleted", 0)), 1)


if __name__ == "__main__":
    unittest.main()
