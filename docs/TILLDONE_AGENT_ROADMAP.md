# Chronicle Agent TillDone

This checklist tracks the `codex exec` companion architecture from the agreed phased rollout through the first complete implementation pass.

## Phase 1: Remote Codex Provider

- [x] Keep `codex exec` as the execution model.
- [x] Support `local_codex_exec` and `remote_codex_exec` providers in Chronicle.
- [x] Add remote companion protocol versioning and handshake endpoint.
- [x] Add remote companion auth via `X-Chronicle-Agent-Key`.
- [x] Keep the existing editor assistant working through the provider abstraction.

## Phase 2: Chronicle Control API

- [x] Add versioned, resource-oriented control endpoints.
- [x] Expose templates, profiles, workouts, and plan-week reads.
- [x] Add durable `drafts`, `jobs`, and `audit` resources.
- [x] Enforce `draft -> validate -> apply` instead of unrestricted writes.
- [x] Separate read access from write/apply access.

## Phase 3: Plan Drafting Workflow

- [x] Add `POST /agent/tasks/plan-next-week`.
- [x] Build a focused next-week planning context in Chronicle.
- [x] Persist returned plan proposals as `plan_week` drafts.
- [x] Validate the generated week before marking the job `awaiting_approval`.
- [x] Record audit events for task and draft creation.

## Phase 4: Apply and Rollback-Safe Workflows

- [x] Add dry-run support on draft apply.
- [x] Enforce expected-version checks on apply.
- [x] Persist apply results and failures on drafts/jobs.
- [x] Require write credentials for remote apply operations.
- [x] Keep live resource writes routed through existing Chronicle save paths.

## Phase 5: Multi-Resource Agent Tasks

- [x] Add `POST /agent/tasks/bundle-create`.
- [x] Support bundled profile/template/workout draft generation.
- [x] Allow template drafts to target a not-yet-applied profile without publishing prematurely.
- [x] Return durable draft ids so the UI or user can review/apply in sequence.
- [x] Document the remote companion + control API operating model.

## Remaining hardening work

- [ ] Add optimistic locking to more first-class editor/plan routes, not only agent apply.
- [ ] Add a first-party UI for reviewing jobs, drafts, diffs, and audit history.
- [ ] Add rollback endpoints for profiles/workouts/plan weeks where practical.
- [ ] Add capability-scoped tokens beyond the current read/write split.
- [ ] Add richer planning validators for load progression, locked days, and taper rules.
