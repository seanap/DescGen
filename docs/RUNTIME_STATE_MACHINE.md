# Runtime State Machine

Chronicle now persists activity processing state in `runtime_state.db` with explicit job/run transitions.

## Tables

### `activities`
Tracks discovered Strava activities.

- `activity_id` (PK)
- `first_seen_at_utc`
- `last_seen_at_utc`
- `sport_type`
- `start_date_utc`
- `updated_at_utc`

### `jobs`
One processing request for an activity.

- `job_id` (PK)
- `activity_id` (FK -> `activities.activity_id`)
- `request_kind` (`auto_poll`, `manual_latest`, `manual_activity`)
- `requested_by` (`worker`, `manual`, etc.)
- `force_update` (0/1)
- `priority`
- `status` (`queued`, `claimed`, `running`, `retry_wait`, `succeeded`, `failed_permanent`, `cancelled`)
- `attempt_count`
- `max_attempts`
- `requested_at_utc`
- `available_at_utc`
- `lease_owner`
- `lease_expires_at_utc`
- `started_at_utc`
- `finished_at_utc`
- `run_id`
- `last_error`
- `last_result_json`
- `updated_at_utc`

### `runs`
An execution attempt for a job.

- `run_id` (PK)
- `job_id` (FK -> `jobs.job_id`)
- `activity_id` (FK -> `activities.activity_id`)
- `attempt_number`
- `worker_owner`
- `status` (same state vocabulary as jobs)
- `started_at_utc`
- `finished_at_utc`
- `error`
- `result_json`
- `updated_at_utc`

### `activity_state`
Latest aggregate state for each activity.

- `activity_id` (PK)
- `state`
- `last_job_id`
- `last_run_id`
- `last_profile_id`
- `last_title`
- `last_description_hash`
- `last_result_status`
- `last_error`
- `updated_at_utc`

### `config_snapshots`
Audit snapshots of runtime control settings.

- `snapshot_id` (PK)
- `source`
- `payload_json`
- `created_at_utc`

## State Transitions

Primary job transition path:

1. `queued` -> `claimed` via `claim_activity_job(...)`
2. `claimed` -> `running` via `start_activity_job_run(...)`
3. `running` -> terminal or retry via `complete_activity_job_run(...)`

Terminal outcomes:

- `running` -> `succeeded`
- `running` -> `failed_permanent`
- `running` -> `retry_wait` (if retryable and attempts remain)
- `retry_wait` -> `failed_permanent` (when attempts exhausted)

Lease recovery:

- `claimed`/`running` -> `queued` when lease expires via `requeue_expired_jobs(...)`

## Runtime Integration

- Worker loop calls `requeue_expired_jobs(...)` each cycle.
- `run_once(...)` now:
  1. snapshots runtime config,
  2. records discovered activities,
  3. enqueues a job,
  4. claims and starts a run,
  5. processes activity,
  6. completes the run as `succeeded`/`retry_wait`/`failed_permanent`.
- `record_activity_output(...)` updates `activity_state` with profile/title/description hash and latest outcome.

## Compatibility

Existing behavior is preserved:

- `processed_activities` + `processed_activities.log` remain the idempotency gate.
- Manual rerun endpoints still force update.
- There is no description-diff overwrite loop.
