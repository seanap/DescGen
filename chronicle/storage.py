from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

JOB_STATUS_QUEUED = "queued"
JOB_STATUS_CLAIMED = "claimed"
JOB_STATUS_RUNNING = "running"
JOB_STATUS_RETRY_WAIT = "retry_wait"
JOB_STATUS_SUCCEEDED = "succeeded"
JOB_STATUS_FAILED_PERMANENT = "failed_permanent"
JOB_STATUS_CANCELLED = "cancelled"

JOB_STATUS_NON_TERMINAL = {
    JOB_STATUS_QUEUED,
    JOB_STATUS_CLAIMED,
    JOB_STATUS_RUNNING,
    JOB_STATUS_RETRY_WAIT,
}
JOB_STATUS_TERMINAL = {
    JOB_STATUS_SUCCEEDED,
    JOB_STATUS_FAILED_PERMANENT,
    JOB_STATUS_CANCELLED,
}
JOB_STATUS_ALL = JOB_STATUS_NON_TERMINAL | JOB_STATUS_TERMINAL

_RUNTIME_SCHEMA_READY: set[str] = set()
_RUNTIME_SCHEMA_LOCK = threading.Lock()

_TRANSIENT_RUNTIME_KEYS_TO_PRUNE = (
    "setup.strava.oauth",
    "cycle.period_stats.activities_cache",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _runtime_db_path(path: Path) -> Path:
    configured = os.getenv("RUNTIME_DB_FILE", "runtime_state.db").strip() or "runtime_state.db"
    runtime_path = Path(configured)
    if runtime_path.is_absolute():
        return runtime_path
    return path.parent / runtime_path


def _parse_utc(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _connect_runtime_db(path: Path) -> sqlite3.Connection:
    db_path = _runtime_db_path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    _ensure_runtime_schema(db_path, conn)
    return conn


def _schema_cache_key(db_path: Path) -> str:
    return str(db_path.resolve())


def _ensure_runtime_schema(db_path: Path, conn: sqlite3.Connection) -> None:
    key = _schema_cache_key(db_path)
    if key in _RUNTIME_SCHEMA_READY:
        return
    with _RUNTIME_SCHEMA_LOCK:
        if key in _RUNTIME_SCHEMA_READY:
            return
        _initialize_runtime_schema(conn)
        _RUNTIME_SCHEMA_READY.add(key)


def _initialize_runtime_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS processed_activities (
            activity_id TEXT PRIMARY KEY,
            processed_at_utc TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runtime_kv (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runtime_locks (
            lock_name TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            acquired_at_utc TEXT NOT NULL,
            expires_at_utc TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS activities (
            activity_id TEXT PRIMARY KEY,
            first_seen_at_utc TEXT NOT NULL,
            last_seen_at_utc TEXT NOT NULL,
            sport_type TEXT,
            start_date_utc TEXT,
            updated_at_utc TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            activity_id TEXT NOT NULL,
            request_kind TEXT NOT NULL,
            requested_by TEXT NOT NULL,
            force_update INTEGER NOT NULL DEFAULT 0,
            priority INTEGER NOT NULL DEFAULT 100,
            status TEXT NOT NULL,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3,
            requested_at_utc TEXT NOT NULL,
            available_at_utc TEXT NOT NULL,
            lease_owner TEXT,
            lease_expires_at_utc TEXT,
            started_at_utc TEXT,
            finished_at_utc TEXT,
            run_id TEXT,
            last_error TEXT,
            last_result_json TEXT,
            updated_at_utc TEXT NOT NULL,
            FOREIGN KEY(activity_id) REFERENCES activities(activity_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            activity_id TEXT NOT NULL,
            attempt_number INTEGER NOT NULL,
            worker_owner TEXT,
            status TEXT NOT NULL,
            started_at_utc TEXT NOT NULL,
            finished_at_utc TEXT,
            error TEXT,
            result_json TEXT,
            updated_at_utc TEXT NOT NULL,
            FOREIGN KEY(job_id) REFERENCES jobs(job_id),
            FOREIGN KEY(activity_id) REFERENCES activities(activity_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS activity_state (
            activity_id TEXT PRIMARY KEY,
            state TEXT NOT NULL,
            last_job_id TEXT,
            last_run_id TEXT,
            last_profile_id TEXT,
            last_title TEXT,
            last_description_hash TEXT,
            last_result_status TEXT,
            last_error TEXT,
            updated_at_utc TEXT NOT NULL,
            FOREIGN KEY(activity_id) REFERENCES activities(activity_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS config_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at_utc TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS plan_days (
            date_local TEXT PRIMARY KEY,
            timezone TEXT,
            run_type TEXT,
            planned_total_miles REAL,
            actual_total_miles REAL,
            is_complete INTEGER,
            notes TEXT,
            updated_at_utc TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS plan_sessions (
            session_id TEXT PRIMARY KEY,
            date_local TEXT NOT NULL,
            ordinal INTEGER NOT NULL,
            planned_miles REAL,
            actual_miles REAL,
            run_type TEXT,
            workout_code TEXT,
            source_activity_id TEXT,
            updated_at_utc TEXT NOT NULL,
            FOREIGN KEY(date_local) REFERENCES plan_days(date_local) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS plan_settings (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_jobs_status_available
        ON jobs (status, available_at_utc, priority, requested_at_utc)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_jobs_activity
        ON jobs (activity_id, requested_at_utc DESC)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_runs_job_started
        ON runs (job_id, started_at_utc DESC)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_plan_sessions_date_ordinal
        ON plan_sessions (date_local, ordinal)
        """
    )


def _load_processed_ids_from_file(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def is_activity_processed(path: Path, activity_id: int | str) -> bool:
    activity_id_str = str(activity_id).strip()
    if not activity_id_str:
        return False

    try:
        with _connect_runtime_db(path) as conn:
            row = conn.execute(
                "SELECT 1 FROM processed_activities WHERE activity_id = ? LIMIT 1",
                (activity_id_str,),
            ).fetchone()
        if row is not None:
            return True
    except sqlite3.Error:
        pass

    return activity_id_str in _load_processed_ids_from_file(path)


def _append_processed_log(path: Path, activity_id_str: str) -> None:
    file_ids = _load_processed_ids_from_file(path)
    if activity_id_str in file_ids:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{activity_id_str}\n")


def mark_activity_processed(path: Path, activity_id: int | str) -> None:
    activity_id_str = str(activity_id).strip()
    if not activity_id_str:
        return

    try:
        with _connect_runtime_db(path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO processed_activities (activity_id, processed_at_utc)
                VALUES (?, ?)
                """,
                (activity_id_str, _utc_now_iso()),
            )
    except sqlite3.Error:
        pass

    _append_processed_log(path, activity_id_str)


def _to_json_string(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _from_json_string(value_json: str) -> Any:
    return json.loads(value_json)


def set_runtime_value(path: Path, key: str, value: Any) -> None:
    set_runtime_values(path, {key: value})


def set_runtime_values(path: Path, values: dict[str, Any]) -> None:
    if not values:
        return
    rows: list[tuple[str, str, str]] = []
    updated_at_utc = _utc_now_iso()
    for key, value in values.items():
        key_text = str(key).strip()
        if not key_text:
            continue
        rows.append((key_text, _to_json_string(value), updated_at_utc))
    if not rows:
        return
    try:
        with _connect_runtime_db(path) as conn:
            conn.executemany(
                """
                INSERT INTO runtime_kv (key, value_json, updated_at_utc)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at_utc = excluded.updated_at_utc
                """,
                rows,
            )
    except sqlite3.Error:
        return


def get_runtime_value(path: Path, key: str, default: Any = None) -> Any:
    try:
        with _connect_runtime_db(path) as conn:
            row = conn.execute(
                "SELECT value_json FROM runtime_kv WHERE key = ? LIMIT 1",
                (key,),
            ).fetchone()
    except sqlite3.Error:
        return default

    if row is None:
        return default
    try:
        return _from_json_string(str(row[0]))
    except (json.JSONDecodeError, TypeError, ValueError):
        return default


def get_runtime_values(path: Path, keys: list[str]) -> dict[str, Any]:
    normalized_keys: list[str] = []
    seen: set[str] = set()
    for key in keys:
        key_text = str(key).strip()
        if not key_text or key_text in seen:
            continue
        seen.add(key_text)
        normalized_keys.append(key_text)
    if not normalized_keys:
        return {}

    placeholders = ",".join(["?"] * len(normalized_keys))
    query = f"SELECT key, value_json FROM runtime_kv WHERE key IN ({placeholders})"
    try:
        with _connect_runtime_db(path) as conn:
            rows = conn.execute(query, normalized_keys).fetchall()
    except sqlite3.Error:
        return {}

    values: dict[str, Any] = {}
    for row in rows:
        key_text = str(row[0]).strip()
        if not key_text:
            continue
        try:
            values[key_text] = _from_json_string(str(row[1]))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return values


def delete_runtime_value(path: Path, key: str) -> None:
    try:
        with _connect_runtime_db(path) as conn:
            conn.execute("DELETE FROM runtime_kv WHERE key = ?", (key,))
    except sqlite3.Error:
        return


def set_worker_heartbeat(path: Path, heartbeat_utc: datetime | None = None) -> None:
    now = heartbeat_utc.astimezone(timezone.utc) if heartbeat_utc else _utc_now()
    set_runtime_value(path, "worker.last_heartbeat_utc", now.isoformat())


def get_worker_heartbeat(path: Path) -> datetime | None:
    raw = get_runtime_value(path, "worker.last_heartbeat_utc")
    return _parse_utc(raw)


def is_worker_healthy(
    path: Path,
    max_age_seconds: int,
    now_utc: datetime | None = None,
) -> bool:
    heartbeat = get_worker_heartbeat(path)
    if heartbeat is None:
        return False
    now = now_utc.astimezone(timezone.utc) if now_utc else _utc_now()
    age = (now - heartbeat).total_seconds()
    return age <= max(30, int(max_age_seconds))


def acquire_runtime_lock(
    path: Path,
    lock_name: str,
    owner: str,
    ttl_seconds: int,
    now_utc: datetime | None = None,
) -> bool:
    now = now_utc.astimezone(timezone.utc) if now_utc else _utc_now()
    expires = now + timedelta(seconds=max(30, int(ttl_seconds)))
    now_iso = now.isoformat()
    expires_iso = expires.isoformat()

    try:
        with _connect_runtime_db(path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT owner, expires_at_utc
                FROM runtime_locks
                WHERE lock_name = ?
                LIMIT 1
                """,
                (lock_name,),
            ).fetchone()

            if row:
                current_owner = str(row[0])
                expires_at = _parse_utc(row[1])
                if expires_at and expires_at > now and current_owner != owner:
                    return False

            conn.execute(
                """
                INSERT INTO runtime_locks (lock_name, owner, acquired_at_utc, expires_at_utc)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(lock_name) DO UPDATE SET
                    owner = excluded.owner,
                    acquired_at_utc = excluded.acquired_at_utc,
                    expires_at_utc = excluded.expires_at_utc
                """,
                (lock_name, owner, now_iso, expires_iso),
            )
        return True
    except sqlite3.Error:
        return False


def release_runtime_lock(path: Path, lock_name: str, owner: str) -> None:
    try:
        with _connect_runtime_db(path) as conn:
            conn.execute(
                "DELETE FROM runtime_locks WHERE lock_name = ? AND owner = ?",
                (lock_name, owner),
            )
    except sqlite3.Error:
        return


def _status_value(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalize_job_status(status: str, *, default: str = JOB_STATUS_QUEUED) -> str:
    normalized = _status_value(status)
    if normalized in JOB_STATUS_ALL:
        return normalized
    return default


def _description_hash(description: str | None) -> str | None:
    if not isinstance(description, str):
        return None
    text = description.strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _to_job_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "job_id": str(row["job_id"]),
        "activity_id": str(row["activity_id"]),
        "request_kind": str(row["request_kind"]),
        "requested_by": str(row["requested_by"]),
        "force_update": bool(int(row["force_update"])),
        "priority": int(row["priority"]),
        "status": _status_value(row["status"]),
        "attempt_count": int(row["attempt_count"]),
        "max_attempts": int(row["max_attempts"]),
        "requested_at_utc": str(row["requested_at_utc"]),
        "available_at_utc": str(row["available_at_utc"]),
        "lease_owner": str(row["lease_owner"]) if row["lease_owner"] is not None else None,
        "lease_expires_at_utc": (
            str(row["lease_expires_at_utc"]) if row["lease_expires_at_utc"] is not None else None
        ),
        "started_at_utc": str(row["started_at_utc"]) if row["started_at_utc"] is not None else None,
        "finished_at_utc": str(row["finished_at_utc"]) if row["finished_at_utc"] is not None else None,
        "run_id": str(row["run_id"]) if row["run_id"] is not None else None,
        "last_error": str(row["last_error"]) if row["last_error"] is not None else None,
        "last_result_json": str(row["last_result_json"]) if row["last_result_json"] is not None else None,
        "updated_at_utc": str(row["updated_at_utc"]),
    }


def _upsert_activity_state(
    conn: sqlite3.Connection,
    *,
    activity_id: str,
    state: str,
    updated_at_utc: str,
    last_job_id: str | None = None,
    last_run_id: str | None = None,
    last_profile_id: str | None = None,
    last_title: str | None = None,
    last_description_hash: str | None = None,
    last_result_status: str | None = None,
    last_error: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO activity_state (
            activity_id,
            state,
            last_job_id,
            last_run_id,
            last_profile_id,
            last_title,
            last_description_hash,
            last_result_status,
            last_error,
            updated_at_utc
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(activity_id) DO UPDATE SET
            state = excluded.state,
            last_job_id = COALESCE(excluded.last_job_id, activity_state.last_job_id),
            last_run_id = COALESCE(excluded.last_run_id, activity_state.last_run_id),
            last_profile_id = COALESCE(excluded.last_profile_id, activity_state.last_profile_id),
            last_title = COALESCE(excluded.last_title, activity_state.last_title),
            last_description_hash = COALESCE(excluded.last_description_hash, activity_state.last_description_hash),
            last_result_status = COALESCE(excluded.last_result_status, activity_state.last_result_status),
            last_error = excluded.last_error,
            updated_at_utc = excluded.updated_at_utc
        """,
        (
            activity_id,
            _normalize_job_status(state, default=JOB_STATUS_QUEUED),
            last_job_id,
            last_run_id,
            last_profile_id,
            last_title,
            last_description_hash,
            last_result_status,
            last_error,
            updated_at_utc,
        ),
    )


def register_activity_discovery(
    path: Path,
    activity_id: int | str,
    *,
    sport_type: str | None = None,
    start_date_utc: str | None = None,
    discovered_at_utc: datetime | None = None,
) -> None:
    activity_id_str = str(activity_id).strip()
    if not activity_id_str:
        return

    now_iso = (discovered_at_utc.astimezone(timezone.utc) if discovered_at_utc else _utc_now()).isoformat()

    try:
        with _connect_runtime_db(path) as conn:
            conn.execute(
                """
                INSERT INTO activities (
                    activity_id,
                    first_seen_at_utc,
                    last_seen_at_utc,
                    sport_type,
                    start_date_utc,
                    updated_at_utc
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(activity_id) DO UPDATE SET
                    last_seen_at_utc = excluded.last_seen_at_utc,
                    sport_type = COALESCE(excluded.sport_type, activities.sport_type),
                    start_date_utc = COALESCE(excluded.start_date_utc, activities.start_date_utc),
                    updated_at_utc = excluded.updated_at_utc
                """,
                (
                    activity_id_str,
                    now_iso,
                    now_iso,
                    sport_type.strip() if isinstance(sport_type, str) and sport_type.strip() else None,
                    start_date_utc.strip() if isinstance(start_date_utc, str) and start_date_utc.strip() else None,
                    now_iso,
                ),
            )
    except sqlite3.Error:
        return


def enqueue_activity_job(
    path: Path,
    activity_id: int | str,
    *,
    request_kind: str,
    requested_by: str,
    force_update: bool,
    priority: int = 100,
    available_at_utc: datetime | None = None,
    max_attempts: int = 3,
) -> str | None:
    activity_id_str = str(activity_id).strip()
    if not activity_id_str:
        return None

    job_id = uuid.uuid4().hex
    now = _utc_now()
    now_iso = now.isoformat()
    available_iso = (available_at_utc.astimezone(timezone.utc) if available_at_utc else now).isoformat()
    max_attempts_value = max(1, int(max_attempts))

    try:
        with _connect_runtime_db(path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO activities (
                    activity_id,
                    first_seen_at_utc,
                    last_seen_at_utc,
                    sport_type,
                    start_date_utc,
                    updated_at_utc
                )
                VALUES (?, ?, ?, NULL, NULL, ?)
                ON CONFLICT(activity_id) DO UPDATE SET
                    last_seen_at_utc = excluded.last_seen_at_utc,
                    updated_at_utc = excluded.updated_at_utc
                """,
                (activity_id_str, now_iso, now_iso, now_iso),
            )
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id,
                    activity_id,
                    request_kind,
                    requested_by,
                    force_update,
                    priority,
                    status,
                    attempt_count,
                    max_attempts,
                    requested_at_utc,
                    available_at_utc,
                    updated_at_utc
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    activity_id_str,
                    str(request_kind or "auto_poll").strip() or "auto_poll",
                    str(requested_by or "system").strip() or "system",
                    1 if force_update else 0,
                    int(priority),
                    JOB_STATUS_QUEUED,
                    max_attempts_value,
                    now_iso,
                    available_iso,
                    now_iso,
                ),
            )
            _upsert_activity_state(
                conn,
                activity_id=activity_id_str,
                state=JOB_STATUS_QUEUED,
                updated_at_utc=now_iso,
                last_job_id=job_id,
                last_result_status="queued",
                last_error=None,
            )
        return job_id
    except sqlite3.Error:
        return None


def claim_activity_job(
    path: Path,
    job_id: str,
    *,
    owner: str,
    lease_seconds: int,
    now_utc: datetime | None = None,
) -> bool:
    job_id_value = str(job_id).strip()
    owner_value = str(owner).strip()
    if not job_id_value or not owner_value:
        return False

    now = now_utc.astimezone(timezone.utc) if now_utc else _utc_now()
    now_iso = now.isoformat()
    lease_expires_iso = (now + timedelta(seconds=max(30, int(lease_seconds)))).isoformat()

    try:
        with _connect_runtime_db(path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT activity_id, status, available_at_utc
                FROM jobs
                WHERE job_id = ?
                LIMIT 1
                """,
                (job_id_value,),
            ).fetchone()
            if row is None:
                return False

            status = _status_value(row["status"])
            if status not in {JOB_STATUS_QUEUED, JOB_STATUS_RETRY_WAIT}:
                return False

            available_at = _parse_utc(row["available_at_utc"])
            if available_at is not None and available_at > now:
                return False

            conn.execute(
                """
                UPDATE jobs
                SET
                    status = ?,
                    lease_owner = ?,
                    lease_expires_at_utc = ?,
                    updated_at_utc = ?
                WHERE job_id = ?
                """,
                (
                    JOB_STATUS_CLAIMED,
                    owner_value,
                    lease_expires_iso,
                    now_iso,
                    job_id_value,
                ),
            )
            _upsert_activity_state(
                conn,
                activity_id=str(row["activity_id"]),
                state=JOB_STATUS_CLAIMED,
                updated_at_utc=now_iso,
                last_job_id=job_id_value,
                last_result_status="claimed",
                last_error=None,
            )
        return True
    except sqlite3.Error:
        return False


def start_activity_job_run(
    path: Path,
    job_id: str,
    *,
    owner: str,
    now_utc: datetime | None = None,
) -> dict[str, Any] | None:
    job_id_value = str(job_id).strip()
    owner_value = str(owner).strip()
    if not job_id_value or not owner_value:
        return None

    now = now_utc.astimezone(timezone.utc) if now_utc else _utc_now()
    now_iso = now.isoformat()
    run_id = uuid.uuid4().hex

    try:
        with _connect_runtime_db(path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT activity_id, status, attempt_count, max_attempts, force_update, lease_owner, lease_expires_at_utc
                FROM jobs
                WHERE job_id = ?
                LIMIT 1
                """,
                (job_id_value,),
            ).fetchone()
            if row is None:
                return None
            if _status_value(row["status"]) != JOB_STATUS_CLAIMED:
                return None
            if str(row["lease_owner"] or "").strip() != owner_value:
                return None
            lease_expires = _parse_utc(row["lease_expires_at_utc"])
            if lease_expires is not None and lease_expires <= now:
                return None

            attempt_number = int(row["attempt_count"]) + 1
            conn.execute(
                """
                UPDATE jobs
                SET
                    status = ?,
                    attempt_count = ?,
                    started_at_utc = COALESCE(started_at_utc, ?),
                    run_id = ?,
                    updated_at_utc = ?
                WHERE job_id = ?
                """,
                (
                    JOB_STATUS_RUNNING,
                    attempt_number,
                    now_iso,
                    run_id,
                    now_iso,
                    job_id_value,
                ),
            )
            conn.execute(
                """
                INSERT INTO runs (
                    run_id,
                    job_id,
                    activity_id,
                    attempt_number,
                    worker_owner,
                    status,
                    started_at_utc,
                    updated_at_utc
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    job_id_value,
                    str(row["activity_id"]),
                    attempt_number,
                    owner_value,
                    JOB_STATUS_RUNNING,
                    now_iso,
                    now_iso,
                ),
            )
            _upsert_activity_state(
                conn,
                activity_id=str(row["activity_id"]),
                state=JOB_STATUS_RUNNING,
                updated_at_utc=now_iso,
                last_job_id=job_id_value,
                last_run_id=run_id,
                last_result_status="running",
                last_error=None,
            )
            return {
                "job_id": job_id_value,
                "run_id": run_id,
                "activity_id": str(row["activity_id"]),
                "attempt_number": attempt_number,
                "max_attempts": int(row["max_attempts"]),
                "force_update": bool(int(row["force_update"])),
            }
    except sqlite3.Error:
        return None


def complete_activity_job_run(
    path: Path,
    job_id: str,
    run_id: str,
    *,
    owner: str,
    outcome: str,
    error: str | None = None,
    result: Any = None,
    retry_delay_seconds: int = 300,
    now_utc: datetime | None = None,
) -> str | None:
    job_id_value = str(job_id).strip()
    run_id_value = str(run_id).strip()
    owner_value = str(owner).strip()
    if not job_id_value or not run_id_value or not owner_value:
        return None

    normalized_outcome = _normalize_job_status(outcome, default=JOB_STATUS_FAILED_PERMANENT)
    if normalized_outcome not in {JOB_STATUS_SUCCEEDED, JOB_STATUS_FAILED_PERMANENT, JOB_STATUS_RETRY_WAIT, JOB_STATUS_CANCELLED}:
        normalized_outcome = JOB_STATUS_FAILED_PERMANENT

    now = now_utc.astimezone(timezone.utc) if now_utc else _utc_now()
    now_iso = now.isoformat()
    retry_at_iso = (now + timedelta(seconds=max(30, int(retry_delay_seconds)))).isoformat()

    result_json: str | None = None
    if result is not None:
        try:
            result_json = _to_json_string(result)
        except (TypeError, ValueError):
            result_json = _to_json_string({"value": str(result)})

    try:
        with _connect_runtime_db(path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT activity_id, status, attempt_count, max_attempts, lease_owner
                FROM jobs
                WHERE job_id = ?
                LIMIT 1
                """,
                (job_id_value,),
            ).fetchone()
            if row is None:
                return None

            current_owner = str(row["lease_owner"] or "").strip()
            if current_owner and current_owner != owner_value:
                return None

            attempts = int(row["attempt_count"])
            max_attempts = max(1, int(row["max_attempts"]))
            final_outcome = normalized_outcome
            if final_outcome == JOB_STATUS_RETRY_WAIT and attempts >= max_attempts:
                final_outcome = JOB_STATUS_FAILED_PERMANENT

            finished_at_value = now_iso if final_outcome in JOB_STATUS_TERMINAL else None
            available_at_value = retry_at_iso if final_outcome == JOB_STATUS_RETRY_WAIT else now_iso

            conn.execute(
                """
                UPDATE jobs
                SET
                    status = ?,
                    lease_owner = NULL,
                    lease_expires_at_utc = NULL,
                    finished_at_utc = COALESCE(?, finished_at_utc),
                    available_at_utc = ?,
                    last_error = ?,
                    last_result_json = COALESCE(?, last_result_json),
                    updated_at_utc = ?
                WHERE job_id = ?
                """,
                (
                    final_outcome,
                    finished_at_value,
                    available_at_value,
                    error,
                    result_json,
                    now_iso,
                    job_id_value,
                ),
            )
            conn.execute(
                """
                UPDATE runs
                SET
                    status = ?,
                    finished_at_utc = ?,
                    error = ?,
                    result_json = COALESCE(?, result_json),
                    updated_at_utc = ?
                WHERE run_id = ? AND job_id = ?
                """,
                (
                    final_outcome,
                    now_iso,
                    error,
                    result_json,
                    now_iso,
                    run_id_value,
                    job_id_value,
                ),
            )
            _upsert_activity_state(
                conn,
                activity_id=str(row["activity_id"]),
                state=final_outcome,
                updated_at_utc=now_iso,
                last_job_id=job_id_value,
                last_run_id=run_id_value,
                last_result_status=final_outcome,
                last_error=error,
            )
            return final_outcome
    except sqlite3.Error:
        return None


def requeue_expired_jobs(path: Path, *, now_utc: datetime | None = None) -> int:
    now = now_utc.astimezone(timezone.utc) if now_utc else _utc_now()
    now_iso = now.isoformat()
    try:
        with _connect_runtime_db(path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            expired_rows = conn.execute(
                """
                SELECT activity_id, job_id
                FROM jobs
                WHERE status IN (?, ?)
                  AND lease_expires_at_utc IS NOT NULL
                  AND lease_expires_at_utc <= ?
                """,
                (JOB_STATUS_CLAIMED, JOB_STATUS_RUNNING, now_iso),
            ).fetchall()
            if not expired_rows:
                return 0

            conn.execute(
                """
                UPDATE jobs
                SET
                    status = ?,
                    lease_owner = NULL,
                    lease_expires_at_utc = NULL,
                    available_at_utc = ?,
                    updated_at_utc = ?
                WHERE status IN (?, ?)
                  AND lease_expires_at_utc IS NOT NULL
                  AND lease_expires_at_utc <= ?
                """,
                (
                    JOB_STATUS_QUEUED,
                    now_iso,
                    now_iso,
                    JOB_STATUS_CLAIMED,
                    JOB_STATUS_RUNNING,
                    now_iso,
                ),
            )
            for row in expired_rows:
                _upsert_activity_state(
                    conn,
                    activity_id=str(row["activity_id"]),
                    state=JOB_STATUS_QUEUED,
                    updated_at_utc=now_iso,
                    last_job_id=str(row["job_id"]),
                    last_result_status="requeued_expired_lease",
                    last_error=None,
                )
            return len(expired_rows)
    except sqlite3.Error:
        return 0


def record_activity_output(
    path: Path,
    activity_id: int | str,
    *,
    state: str,
    result_status: str,
    profile_id: str | None = None,
    title: str | None = None,
    description: str | None = None,
    job_id: str | None = None,
    run_id: str | None = None,
    error: str | None = None,
) -> None:
    activity_id_str = str(activity_id).strip()
    if not activity_id_str:
        return
    now_iso = _utc_now_iso()
    try:
        with _connect_runtime_db(path) as conn:
            _upsert_activity_state(
                conn,
                activity_id=activity_id_str,
                state=state,
                updated_at_utc=now_iso,
                last_job_id=str(job_id).strip() if isinstance(job_id, str) and job_id.strip() else None,
                last_run_id=str(run_id).strip() if isinstance(run_id, str) and run_id.strip() else None,
                last_profile_id=profile_id.strip() if isinstance(profile_id, str) and profile_id.strip() else None,
                last_title=title.strip() if isinstance(title, str) and title.strip() else None,
                last_description_hash=_description_hash(description),
                last_result_status=result_status.strip() if isinstance(result_status, str) and result_status.strip() else None,
                last_error=error,
            )
    except sqlite3.Error:
        return


def write_config_snapshot(path: Path, source: str, payload: Any) -> str | None:
    source_value = str(source).strip() or "unknown"
    now_iso = _utc_now_iso()
    snapshot_id = uuid.uuid4().hex
    try:
        payload_json = _to_json_string(payload)
    except (TypeError, ValueError):
        payload_json = _to_json_string({"value": str(payload)})

    try:
        with _connect_runtime_db(path) as conn:
            conn.execute(
                """
                INSERT INTO config_snapshots (snapshot_id, source, payload_json, created_at_utc)
                VALUES (?, ?, ?, ?)
                """,
                (snapshot_id, source_value, payload_json, now_iso),
            )
        return snapshot_id
    except sqlite3.Error:
        return None


def cleanup_runtime_state(
    path: Path,
    *,
    now_utc: datetime | None = None,
    service_cache_retention_seconds: int = 259200,
    transient_runtime_retention_seconds: int = 604800,
    config_snapshot_retention_count: int = 50,
    terminal_job_retention_days: int = 30,
    expired_lock_retention_seconds: int = 86400,
) -> dict[str, int]:
    now = now_utc.astimezone(timezone.utc) if now_utc else _utc_now()
    service_cutoff_iso = (
        now - timedelta(seconds=max(0, int(service_cache_retention_seconds)))
    ).isoformat()
    transient_cutoff_iso = (
        now - timedelta(seconds=max(0, int(transient_runtime_retention_seconds)))
    ).isoformat()
    terminal_job_cutoff_iso = (
        now - timedelta(days=max(1, int(terminal_job_retention_days)))
    ).isoformat()
    lock_cutoff_iso = (
        now - timedelta(seconds=max(0, int(expired_lock_retention_seconds)))
    ).isoformat()
    keep_snapshot_count = max(1, int(config_snapshot_retention_count))

    stats: dict[str, int] = {
        "runtime_kv_service_cache_deleted": 0,
        "runtime_kv_transient_deleted": 0,
        "config_snapshots_deleted": 0,
        "runs_deleted": 0,
        "jobs_deleted": 0,
        "expired_locks_deleted": 0,
        "deleted_total": 0,
        "errors": 0,
    }

    try:
        with _connect_runtime_db(path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            deleted = conn.execute(
                """
                DELETE FROM runtime_kv
                WHERE key LIKE 'service.%.cache.%'
                  AND updated_at_utc < ?
                """,
                (service_cutoff_iso,),
            )
            stats["runtime_kv_service_cache_deleted"] = int(max(0, deleted.rowcount))

            placeholders = ", ".join("?" for _ in _TRANSIENT_RUNTIME_KEYS_TO_PRUNE)
            deleted = conn.execute(
                f"""
                DELETE FROM runtime_kv
                WHERE key IN ({placeholders})
                  AND updated_at_utc < ?
                """,
                (*_TRANSIENT_RUNTIME_KEYS_TO_PRUNE, transient_cutoff_iso),
            )
            stats["runtime_kv_transient_deleted"] = int(max(0, deleted.rowcount))

            deleted = conn.execute(
                """
                DELETE FROM config_snapshots
                WHERE snapshot_id IN (
                    SELECT snapshot_id
                    FROM config_snapshots
                    ORDER BY created_at_utc DESC
                    LIMIT -1 OFFSET ?
                )
                """,
                (keep_snapshot_count,),
            )
            stats["config_snapshots_deleted"] = int(max(0, deleted.rowcount))

            status_placeholders = ", ".join("?" for _ in JOB_STATUS_TERMINAL)
            terminal_statuses = tuple(sorted(JOB_STATUS_TERMINAL))
            rows = conn.execute(
                f"""
                SELECT job_id
                FROM jobs
                WHERE status IN ({status_placeholders})
                  AND finished_at_utc IS NOT NULL
                  AND finished_at_utc < ?
                  AND job_id NOT IN (
                    SELECT last_job_id
                    FROM activity_state
                    WHERE last_job_id IS NOT NULL
                  )
                """,
                (*terminal_statuses, terminal_job_cutoff_iso),
            ).fetchall()
            candidate_job_ids = [str(row["job_id"]) for row in rows if str(row["job_id"]).strip()]
            if candidate_job_ids:
                candidate_placeholders = ", ".join("?" for _ in candidate_job_ids)
                deleted = conn.execute(
                    f"""
                    DELETE FROM runs
                    WHERE job_id IN ({candidate_placeholders})
                      AND run_id NOT IN (
                        SELECT last_run_id
                        FROM activity_state
                        WHERE last_run_id IS NOT NULL
                      )
                    """,
                    tuple(candidate_job_ids),
                )
                stats["runs_deleted"] = int(max(0, deleted.rowcount))

                deleted = conn.execute(
                    f"""
                    DELETE FROM jobs
                    WHERE job_id IN ({candidate_placeholders})
                      AND NOT EXISTS (
                        SELECT 1
                        FROM runs
                        WHERE runs.job_id = jobs.job_id
                      )
                    """,
                    tuple(candidate_job_ids),
                )
                stats["jobs_deleted"] = int(max(0, deleted.rowcount))

            deleted = conn.execute(
                """
                DELETE FROM runtime_locks
                WHERE expires_at_utc < ?
                """,
                (lock_cutoff_iso,),
            )
            stats["expired_locks_deleted"] = int(max(0, deleted.rowcount))
    except sqlite3.Error:
        stats["errors"] = 1

    stats["deleted_total"] = (
        int(stats["runtime_kv_service_cache_deleted"])
        + int(stats["runtime_kv_transient_deleted"])
        + int(stats["config_snapshots_deleted"])
        + int(stats["runs_deleted"])
        + int(stats["jobs_deleted"])
        + int(stats["expired_locks_deleted"])
    )
    return stats


def get_activity_job(path: Path, job_id: str) -> dict[str, Any] | None:
    job_id_value = str(job_id).strip()
    if not job_id_value:
        return None
    try:
        with _connect_runtime_db(path) as conn:
            row = conn.execute(
                """
                SELECT
                    job_id,
                    activity_id,
                    request_kind,
                    requested_by,
                    force_update,
                    priority,
                    status,
                    attempt_count,
                    max_attempts,
                    requested_at_utc,
                    available_at_utc,
                    lease_owner,
                    lease_expires_at_utc,
                    started_at_utc,
                    finished_at_utc,
                    run_id,
                    last_error,
                    last_result_json,
                    updated_at_utc
                FROM jobs
                WHERE job_id = ?
                LIMIT 1
                """,
                (job_id_value,),
            ).fetchone()
    except sqlite3.Error:
        return None
    return _to_job_dict(row)


def get_activity_state(path: Path, activity_id: int | str) -> dict[str, Any] | None:
    activity_id_str = str(activity_id).strip()
    if not activity_id_str:
        return None
    try:
        with _connect_runtime_db(path) as conn:
            row = conn.execute(
                """
                SELECT
                    activity_id,
                    state,
                    last_job_id,
                    last_run_id,
                    last_profile_id,
                    last_title,
                    last_description_hash,
                    last_result_status,
                    last_error,
                    updated_at_utc
                FROM activity_state
                WHERE activity_id = ?
                LIMIT 1
                """,
                (activity_id_str,),
            ).fetchone()
    except sqlite3.Error:
        return None
    if row is None:
        return None
    return {
        "activity_id": str(row["activity_id"]),
        "state": _status_value(row["state"]),
        "last_job_id": str(row["last_job_id"]) if row["last_job_id"] is not None else None,
        "last_run_id": str(row["last_run_id"]) if row["last_run_id"] is not None else None,
        "last_profile_id": str(row["last_profile_id"]) if row["last_profile_id"] is not None else None,
        "last_title": str(row["last_title"]) if row["last_title"] is not None else None,
        "last_description_hash": (
            str(row["last_description_hash"]) if row["last_description_hash"] is not None else None
        ),
        "last_result_status": (
            str(row["last_result_status"]) if row["last_result_status"] is not None else None
        ),
        "last_error": str(row["last_error"]) if row["last_error"] is not None else None,
        "updated_at_utc": str(row["updated_at_utc"]),
    }


def get_runtime_lock_owner(path: Path, lock_name: str) -> str | None:
    try:
        with _connect_runtime_db(path) as conn:
            row = conn.execute(
                """
                SELECT owner, expires_at_utc
                FROM runtime_locks
                WHERE lock_name = ?
                LIMIT 1
                """,
                (lock_name,),
            ).fetchone()
    except sqlite3.Error:
        return None
    if not row:
        return None
    expires_at = _parse_utc(row[1])
    if expires_at is not None and expires_at <= _utc_now():
        return None
    owner = str(row[0]).strip()
    return owner or None


def _parse_plan_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def upsert_plan_day(
    path: Path,
    *,
    date_local: str,
    timezone_name: str | None = None,
    run_type: str | None = None,
    planned_total_miles: float | int | str | None = None,
    actual_total_miles: float | int | str | None = None,
    is_complete: bool | None = None,
    notes: str | None = None,
) -> bool:
    parsed_date = _parse_plan_date(date_local)
    if parsed_date is None:
        return False

    now_iso = _utc_now_iso()
    date_key = parsed_date.isoformat()
    timezone_text = str(timezone_name or "").strip() or None
    run_type_text = str(run_type or "").strip() or None
    notes_text = str(notes or "").strip() or None
    planned = _optional_float(planned_total_miles)
    actual = _optional_float(actual_total_miles)
    complete_value = None if is_complete is None else (1 if bool(is_complete) else 0)

    try:
        with _connect_runtime_db(path) as conn:
            conn.execute(
                """
                INSERT INTO plan_days (
                    date_local,
                    timezone,
                    run_type,
                    planned_total_miles,
                    actual_total_miles,
                    is_complete,
                    notes,
                    updated_at_utc
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date_local) DO UPDATE SET
                    timezone = excluded.timezone,
                    run_type = excluded.run_type,
                    planned_total_miles = excluded.planned_total_miles,
                    actual_total_miles = excluded.actual_total_miles,
                    is_complete = excluded.is_complete,
                    notes = excluded.notes,
                    updated_at_utc = excluded.updated_at_utc
                """,
                (
                    date_key,
                    timezone_text,
                    run_type_text,
                    planned,
                    actual,
                    complete_value,
                    notes_text,
                    now_iso,
                ),
            )
        return True
    except sqlite3.Error:
        return False


def list_plan_days(path: Path, *, start_date: str, end_date: str) -> list[dict[str, Any]]:
    start = _parse_plan_date(start_date)
    end = _parse_plan_date(end_date)
    if start is None or end is None:
        return []
    if start > end:
        start, end = end, start

    try:
        with _connect_runtime_db(path) as conn:
            rows = conn.execute(
                """
                SELECT
                    date_local,
                    timezone,
                    run_type,
                    planned_total_miles,
                    actual_total_miles,
                    is_complete,
                    notes,
                    updated_at_utc
                FROM plan_days
                WHERE date_local >= ? AND date_local <= ?
                ORDER BY date_local ASC
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchall()
    except sqlite3.Error:
        return []

    payload: list[dict[str, Any]] = []
    for row in rows:
        is_complete_raw = row["is_complete"]
        complete = None if is_complete_raw is None else bool(int(is_complete_raw))
        payload.append(
            {
                "date_local": str(row["date_local"]),
                "timezone": str(row["timezone"]) if row["timezone"] is not None else None,
                "run_type": str(row["run_type"]) if row["run_type"] is not None else None,
                "planned_total_miles": (
                    float(row["planned_total_miles"])
                    if row["planned_total_miles"] is not None
                    else None
                ),
                "actual_total_miles": (
                    float(row["actual_total_miles"])
                    if row["actual_total_miles"] is not None
                    else None
                ),
                "is_complete": complete,
                "notes": str(row["notes"]) if row["notes"] is not None else None,
                "updated_at_utc": str(row["updated_at_utc"]),
            }
        )
    return payload


def get_plan_day(path: Path, *, date_local: str) -> dict[str, Any] | None:
    parsed = _parse_plan_date(date_local)
    if parsed is None:
        return None
    date_key = parsed.isoformat()
    try:
        with _connect_runtime_db(path) as conn:
            row = conn.execute(
                """
                SELECT
                    date_local,
                    timezone,
                    run_type,
                    planned_total_miles,
                    actual_total_miles,
                    is_complete,
                    notes,
                    updated_at_utc
                FROM plan_days
                WHERE date_local = ?
                LIMIT 1
                """,
                (date_key,),
            ).fetchone()
    except sqlite3.Error:
        return None
    if row is None:
        return None
    is_complete_raw = row["is_complete"]
    complete = None if is_complete_raw is None else bool(int(is_complete_raw))
    return {
        "date_local": str(row["date_local"]),
        "timezone": str(row["timezone"]) if row["timezone"] is not None else None,
        "run_type": str(row["run_type"]) if row["run_type"] is not None else None,
        "planned_total_miles": (
            float(row["planned_total_miles"]) if row["planned_total_miles"] is not None else None
        ),
        "actual_total_miles": (
            float(row["actual_total_miles"]) if row["actual_total_miles"] is not None else None
        ),
        "is_complete": complete,
        "notes": str(row["notes"]) if row["notes"] is not None else None,
        "updated_at_utc": str(row["updated_at_utc"]),
    }


def replace_plan_sessions_for_day(
    path: Path,
    *,
    date_local: str,
    sessions: list[dict[str, Any]],
) -> bool:
    parsed = _parse_plan_date(date_local)
    if parsed is None:
        return False
    date_key = parsed.isoformat()
    now_iso = _utc_now_iso()
    rows: list[tuple[str, str, int, float | None, float | None, str | None, str | None, str | None, str]] = []
    for idx, session in enumerate(sessions):
        if not isinstance(session, dict):
            continue
        planned = _optional_float(session.get("planned_miles"))
        actual = _optional_float(session.get("actual_miles"))
        run_type = str(session.get("run_type") or "").strip() or None
        workout_code = str(session.get("workout_code") or "").strip() or None
        source_activity_id = str(session.get("source_activity_id") or "").strip() or None
        rows.append(
            (
                uuid.uuid4().hex,
                date_key,
                int(session.get("ordinal")) if isinstance(session.get("ordinal"), int) else (idx + 1),
                planned,
                actual,
                run_type,
                workout_code,
                source_activity_id,
                now_iso,
            )
        )

    try:
        with _connect_runtime_db(path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO plan_days (
                    date_local,
                    updated_at_utc
                )
                VALUES (?, ?)
                ON CONFLICT(date_local) DO UPDATE SET
                    updated_at_utc = excluded.updated_at_utc
                """,
                (date_key, now_iso),
            )
            conn.execute(
                "DELETE FROM plan_sessions WHERE date_local = ?",
                (date_key,),
            )
            if rows:
                conn.executemany(
                    """
                    INSERT INTO plan_sessions (
                        session_id,
                        date_local,
                        ordinal,
                        planned_miles,
                        actual_miles,
                        run_type,
                        workout_code,
                        source_activity_id,
                        updated_at_utc
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
        return True
    except sqlite3.Error:
        return False


def list_plan_sessions(path: Path, *, start_date: str, end_date: str) -> dict[str, list[dict[str, Any]]]:
    start = _parse_plan_date(start_date)
    end = _parse_plan_date(end_date)
    if start is None or end is None:
        return {}
    if start > end:
        start, end = end, start

    try:
        with _connect_runtime_db(path) as conn:
            rows = conn.execute(
                """
                SELECT
                    session_id,
                    date_local,
                    ordinal,
                    planned_miles,
                    actual_miles,
                    run_type,
                    workout_code,
                    source_activity_id,
                    updated_at_utc
                FROM plan_sessions
                WHERE date_local >= ? AND date_local <= ?
                ORDER BY date_local ASC, ordinal ASC, session_id ASC
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchall()
    except sqlite3.Error:
        return {}

    payload: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        date_key = str(row["date_local"])
        bucket = payload.setdefault(date_key, [])
        bucket.append(
            {
                "session_id": str(row["session_id"]),
                "date_local": date_key,
                "ordinal": int(row["ordinal"]),
                "planned_miles": float(row["planned_miles"]) if row["planned_miles"] is not None else None,
                "actual_miles": float(row["actual_miles"]) if row["actual_miles"] is not None else None,
                "run_type": str(row["run_type"]) if row["run_type"] is not None else None,
                "workout_code": str(row["workout_code"]) if row["workout_code"] is not None else None,
                "source_activity_id": (
                    str(row["source_activity_id"]) if row["source_activity_id"] is not None else None
                ),
                "updated_at_utc": str(row["updated_at_utc"]),
            }
        )
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(path)


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
