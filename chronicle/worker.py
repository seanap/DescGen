from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import Settings
from .activity_pipeline import run_once
from .dashboard_data import ensure_dashboard_cache_warm, get_dashboard_payload
from .storage import cleanup_runtime_state, get_runtime_value, requeue_expired_jobs, set_runtime_values, set_worker_heartbeat


logger = logging.getLogger(__name__)
RUNTIME_CLEANUP_LAST_AT_KEY = "worker.runtime_cleanup.last_at_utc"


def _in_quiet_hours(hour: int, start_hour: int, end_hour: int) -> bool:
    if start_hour == end_hour:
        return False
    if start_hour < end_hour:
        return start_hour <= hour < end_hour
    return hour >= start_hour or hour < end_hour


def _seconds_until_quiet_end(
    now_local: datetime, start_hour: int, end_hour: int
) -> int:
    if not _in_quiet_hours(now_local.hour, start_hour, end_hour):
        return 0

    quiet_end = now_local.replace(
        hour=end_hour,
        minute=0,
        second=0,
        microsecond=0,
    )

    if start_hour < end_hour:
        if now_local >= quiet_end:
            quiet_end += timedelta(days=1)
    else:
        if now_local.hour >= start_hour:
            quiet_end += timedelta(days=1)

    delta = int((quiet_end - now_local).total_seconds())
    return max(60, delta)


def _should_refresh_dashboard(result: object) -> bool:
    if not isinstance(result, dict):
        return False
    return str(result.get("status") or "").strip().lower() == "updated"


def _parse_utc(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _maybe_cleanup_runtime_state(settings: Settings, *, now_utc: datetime) -> None:
    interval_seconds = max(0, int(settings.runtime_cleanup_interval_seconds))
    if interval_seconds <= 0:
        return
    last_run_raw = get_runtime_value(settings.processed_log_file, RUNTIME_CLEANUP_LAST_AT_KEY)
    last_run = _parse_utc(last_run_raw)
    if last_run is not None:
        age_seconds = (now_utc - last_run).total_seconds()
        if age_seconds < interval_seconds:
            return

    cleanup_stats = cleanup_runtime_state(
        settings.processed_log_file,
        now_utc=now_utc,
        service_cache_retention_seconds=settings.runtime_retention_service_cache_seconds,
        transient_runtime_retention_seconds=settings.runtime_retention_transient_runtime_seconds,
        config_snapshot_retention_count=settings.runtime_retention_config_snapshots,
        terminal_job_retention_days=settings.runtime_retention_terminal_job_days,
        expired_lock_retention_seconds=settings.runtime_retention_expired_lock_seconds,
    )
    deleted_total = int(cleanup_stats.get("deleted_total", 0) or 0)
    set_runtime_values(
        settings.processed_log_file,
        {
            RUNTIME_CLEANUP_LAST_AT_KEY: now_utc.isoformat(),
            "worker.runtime_cleanup.last_stats": cleanup_stats,
            "worker.runtime_cleanup.last_deleted_total": deleted_total,
        },
    )
    if int(cleanup_stats.get("errors", 0) or 0) > 0:
        logger.warning("Runtime cleanup reported errors: %s", cleanup_stats)
    elif deleted_total > 0:
        logger.info("Runtime cleanup deleted %s record(s): %s", deleted_total, cleanup_stats)


def main() -> None:
    settings = Settings.from_env()
    settings.ensure_state_paths()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    interval = settings.poll_interval_seconds
    try:
        local_tz = ZoneInfo(settings.timezone)
    except ZoneInfoNotFoundError:
        logger.warning("Unknown timezone '%s'. Falling back to UTC.", settings.timezone)
        local_tz = ZoneInfo("UTC")

    logger.info("Worker started with poll interval: %ss", interval)
    set_runtime_values(
        settings.processed_log_file,
        {
            "worker.started_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    )
    try:
        warm_payload = ensure_dashboard_cache_warm(settings)
        warm_count = len(warm_payload.get("activities", [])) if isinstance(warm_payload, dict) else 0
        set_runtime_values(
            settings.processed_log_file,
            {
                "worker.dashboard_warm_status": "ok",
                "worker.dashboard_warm_activity_count": warm_count,
                "worker.dashboard_warm_at_utc": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception as exc:
        set_runtime_values(
            settings.processed_log_file,
            {
                "worker.dashboard_warm_status": f"error:{exc}",
            },
        )
        logger.warning("Dashboard warmup failed: %s", exc)
    if settings.enable_quiet_hours:
        logger.info(
            "Quiet hours enabled: %02d:00-%02d:00 (%s)",
            settings.quiet_hours_start_hour,
            settings.quiet_hours_end_hour,
            local_tz,
        )

    while True:
        now_utc = datetime.now(timezone.utc)
        set_worker_heartbeat(settings.processed_log_file, now_utc)
        requeued_expired = requeue_expired_jobs(settings.processed_log_file, now_utc=now_utc)
        if requeued_expired > 0:
            logger.warning("Requeued %s expired job(s).", requeued_expired)
            set_runtime_values(
                settings.processed_log_file,
                {
                    "worker.last_requeued_jobs": requeued_expired,
                    "worker.last_requeued_at_utc": now_utc.isoformat(),
                },
            )
        _maybe_cleanup_runtime_state(settings, now_utc=now_utc)
        now_local = datetime.now(local_tz)
        if settings.enable_quiet_hours and _in_quiet_hours(
            now_local.hour,
            settings.quiet_hours_start_hour,
            settings.quiet_hours_end_hour,
        ):
            sleep_seconds = _seconds_until_quiet_end(
                now_local,
                settings.quiet_hours_start_hour,
                settings.quiet_hours_end_hour,
            )
            logger.info(
                "In quiet hours at %s, sleeping for %ss",
                now_local.isoformat(timespec="seconds"),
                sleep_seconds,
            )
            set_runtime_values(
                settings.processed_log_file,
                {
                    "worker.state": "quiet_hours",
                    "worker.next_wake_utc": (now_utc + timedelta(seconds=sleep_seconds)).isoformat(),
                },
            )
            time.sleep(sleep_seconds)
            continue

        try:
            set_runtime_values(settings.processed_log_file, {"worker.state": "running_cycle"})
            result = run_once(force_update=False)
            set_runtime_values(settings.processed_log_file, {"worker.last_cycle_result": result})
            if _should_refresh_dashboard(result):
                try:
                    get_dashboard_payload(settings, force_refresh=True)
                except Exception as exc:
                    logger.warning("Dashboard cache refresh failed: %s", exc)
            set_runtime_values(
                settings.processed_log_file,
                {"worker.last_success_at_utc": datetime.now(timezone.utc).isoformat()},
            )
            logger.info("Cycle result: %s", result)
        except Exception as exc:
            set_runtime_values(
                settings.processed_log_file,
                {
                    "worker.last_error": str(exc),
                    "worker.last_error_at_utc": datetime.now(timezone.utc).isoformat(),
                },
            )
            logger.exception("Worker cycle failed.")
        finally:
            set_runtime_values(
                settings.processed_log_file,
                {
                    "worker.state": "sleeping",
                    "worker.next_wake_utc": (datetime.now(timezone.utc) + timedelta(seconds=interval)).isoformat(),
                },
            )
        time.sleep(interval)


if __name__ == "__main__":
    main()
