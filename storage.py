from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


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
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
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
    return conn


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
    try:
        with _connect_runtime_db(path) as conn:
            conn.execute(
                """
                INSERT INTO runtime_kv (key, value_json, updated_at_utc)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at_utc = excluded.updated_at_utc
                """,
                (key, _to_json_string(value), _utc_now_iso()),
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
