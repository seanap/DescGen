# Repository Guidelines

## Project Structure & Module Organization
- `chronicle/`: core Python application (API server, worker, template pipeline, storage, config).
- `chronicle/stat_modules/`: provider-specific integrations (Garmin, Intervals, Smashrun, Crono API, etc.).
- `templates/` and `static/`: Flask-rendered UI pages and frontend assets.
- `tests/`: `unittest` suite, including API/UI contract tests.
- `docs/`: API, metrics, setup, and design notes.
- `state/`: local runtime/template artifacts used by the app; treat as generated state unless intentionally updating defaults.
- `data/`: Docker-mounted runtime state directory (ignored via `.gitignore`).

## Build, Test, and Development Commands
- `cp .env.example .env`: create local configuration before running services.
- `docker compose up -d`: start `chronicle-api` and `chronicle-worker`.
- `docker compose logs -f chronicle-api`: tail API logs while developing.
- `python -m unittest discover -s tests -p "test_*.py" -v`: run full test suite (matches CI).
- `python -m unittest tests.test_api_server -v`: run a focused test module.
- `python -m chronicle.worker`: run worker loop in foreground for debugging.

## Coding Style & Naming Conventions
- Python: 4-space indentation, PEP 8 conventions, `snake_case` for functions/modules, `PascalCase` for classes.
- Prefer explicit type hints where existing code uses them.
- Frontend (`static/*.js`): `camelCase` variables/functions, `UPPER_SNAKE_CASE` constants.
- Keep route names, template IDs, and response keys stable; contract tests depend on them.
- No dedicated formatter config is checked in; follow surrounding style and keep diffs tight.

## Testing Guidelines
- Use `unittest` with files named `tests/test_<feature>.py`.
- Name test classes `Test<Feature>` and test methods `test_<behavior>`.
- Add/adjust tests for behavior, API payload shape, and template/HTML contract changes.
- Run the full suite before opening a PR; include any targeted test command used during development.
- Use the .env in the root project folder to run any custom scripts or commands to test live api data to validate external sources api calls and endpoints and provided data.
- `gh`, and access to my github and docker hub are configured and authenticated for you to use when needed.

## Commit & Pull Request Guidelines
- Follow existing history style: short, imperative commit subjects (for example, `Fix ...`, `Add ...`, `Update ...`).
- Keep each commit scoped to one logical change.
- PRs should include: purpose, key file/module changes, test evidence, and linked issue(s) when applicable.
- For UI changes, include screenshots for affected pages (`/dashboard`, `/editor`, `/setup`, `/control`).
- If config/env behavior changes, update `.env.example` and relevant docs in `docs/`.

## Security & Configuration Tips
- Never commit real credentials from `.env`, `state/`, or `data/`.
- Always ensure `AGENTS.md` and the `local/` folder are in gitignore
- Redact tokens/keys in logs and screenshots.
- Treat `.env.example` as the only safe template for shared configuration.

## GitHub-as-Memory Workflows (Agentic)

This repo uses GitHub Issues + PRs as durable "project memory" so work can resume after context compaction without rehydrating the entire history.

### Principles (Token-Aware)
- Do NOT paste long logs, stack traces, or CI output into chat context unless directly needed.
- Store bulk artifacts in GitHub instead:
  - Issue body = canonical problem statement + acceptance criteria + current status
  - PR description = canonical solution narrative + test plan + verification
  - CI logs stay in Actions; summarize the failure in one paragraph and link via PR/Actions
- When resuming, use the Recall Protocol to pull only the minimum relevant state.

---

## Labels & Conventions
Use labels consistently so recall/search is fast.

**Type**
- `type/bug`, `type/feat`, `type/docs`, `type/refactor`, `type/chore`

**Priority**
- `prio/high`, `prio/med`, `prio/low`

**State**
- `state/blocked`, `state/needs-info`, `state/in-progress`

**Agent**
- `agent/ready`, `agent/wip`, `agent/do-not-touch`

**Branch naming**
- With an issue: `type/<ISSUE>-short-kebab`
  - `fix/123-dashboard-leak`
  - `feat/221-add-auth`
- Without an issue (tiny changes only): `type/short-kebab`

**PR title / squash commit title**
- Conventional commit style: `type(scope): description`
- Example: `fix(api): handle null profile response`

---

## Recall Protocol (Use BEFORE starting work or after compaction)
When the user says "resume", "continue", "pick up", or references a bug/feature without details:

1. Identify the active work item:
   - If an issue number is known: use it.
   - Else search GitHub by keywords.

2. Minimal GitHub recall (prefer CLI):
   - Find candidates:
     - `gh issue list --state open --limit 20`
     - `gh issue list --search "<keywords>" --state open --limit 20`
     - `gh pr list --state open --limit 20`
   - Open the best match:
     - `gh issue view <N> --comments`
     - `gh pr view <N> --comments`
     - `gh pr checks <N>`

3. Extract ONLY these into working context (5–10 bullets max):
   - Problem statement (Observed vs Expected)
   - Acceptance criteria (checkboxes)
   - Current status (what’s done / what’s blocked)
   - Repro steps (or how to validate)
   - Most recent CI failure summary (if any)
   - Next 1–3 actions

4. If anything is missing (repro steps, expected behavior, env), label `state/needs-info` and ask ONLY for that missing detail.

---

## Workflow A: "New Issue" (GitHub Memory First)
When the user says: "new issue", "track this", "file this", or a bug feels non-trivial (>30 min, unclear, likely to recur):

### A1) Decide: Issue vs No Issue
Create an issue if ANY are true:
- Bug requires reproduction steps or logs to preserve
- Multi-step fix, refactor, or risk of regression
- Likely to be revisited later
- Requires discussion/decision

Skip issue only for tiny one-commit changes (typo, trivial docs).

### A2) Create Issue (CLI preferred)
1. Create issue with structured body:
   - `gh issue create`
2. Add labels:
   - `type/*`, `prio/*`, optional `state/needs-info` if unclear
3. Issue body MUST include:
   - **Observed**
   - **Expected**
   - **Repro steps**
   - **Scope / constraints**
   - **Acceptance criteria** (checkbox list)
   - **Current status** (short; update as you progress)

### A3) Add a Plan Comment (keeps memory durable)
Add a brief comment with:
- Proposed approach (3–7 steps)
- Risks/unknowns
- Test plan (what will prove it works)

### A4) Create Branch from Issue
1. `git checkout main`
2. `git pull --ff-only`
3. `git checkout -b <type>/<ISSUE>-short-kebab`

### A5) Work Loop (keep commits meaningful)
- Keep commits small and descriptive.
- Reference issue in PR (not necessarily every commit).
- If you discover new info (root cause, constraints), UPDATE the issue body under **Current status**.

### A6) Open PR Early (Draft by default)
1. Push branch:
   - `git push -u origin HEAD`
2. Create PR (draft preferred while iterating):
   - `gh pr create --draft --fill`
3. In PR description, include:
   - Summary (what/why)
   - Test plan (what you ran locally)
   - Verification steps (how to validate manually)
   - Risks / rollback notes (if relevant)
   - Link issue: include `Fixes #<ISSUE>` ONLY when confident it should auto-close on merge

### A7) CI loop
- Watch checks:
  - `gh pr checks --watch`
- If CI fails:
  - Summarize failure in PR comment (1 short paragraph + next action)
  - Fix and push until green

---

## Workflow B: "Commit / Push / CI" (your existing habit, formalized)
When the user says "commit/push/ci" (or you’re ready to checkpoint work):

1. Ensure branch is correct and named per convention.
2. Run local quality gate (single command if possible, e.g. `make check`):
   - lint/format, unit tests, typecheck, build (as applicable)
3. Commit with conventional commit format:
   - `type(scope): description`
   - Body for non-trivial changes: context + tradeoffs
4. Push:
   - `git push`
5. Ensure a PR exists (create/update as needed):
   - `gh pr create --draft --fill` (if none exists)
6. Watch CI:
   - `gh pr checks --watch`
7. Update issue **Current status** (only if there is an issue):
   - What changed
   - CI status
   - Next action

---

## Workflow C: "Merge to Main" (Clean Main, CI-Enforced)
When the user says "merge to main":

### C1) Preconditions
- A PR exists targeting `main`
- CI is green (required checks)
- Issue linkage is correct (`Fixes #N` if applicable)
- No unresolved review/notes (even if solo: read your own PR once)

### C2) Sync & Conflict Check (branch stays current)
1. `git fetch origin`
2. Ensure PR branch is up-to-date with `origin/main` (repo standard):
   - Preferred: rebase
     - `git rebase origin/main`
   - If conflicts:
     - resolve, rerun checks, push

### C3) Final verification (minimal but real)
- Confirm local checks passed OR rely on CI + a smoke check script.
- PR description includes verification steps.
- If your app is Docker-based, ensure:
  - image build is successful in CI
  - version/tag semantics are correct (if you tag)

### C4) Merge method
Default: **Squash merge** (keeps main readable; PR becomes the story).
- Squash title MUST remain conventional-commit formatted.
- If PR contains multiple logical changes, prefer multiple PRs rather than merge commits.

CLI merge:
- `gh pr merge <PR#> --squash --delete-branch`

### C5) Post-merge hygiene
1. Update local main:
   - `git checkout main`
   - `git pull --ff-only`
2. Confirm issue auto-closed (if `Fixes #N` used).
3. Update the issue (if still open) with:
   - What shipped
   - How to validate
   - Any follow-ups (new issues if needed)

## What to store where (memory map)
- **Issue**: problem, repro, acceptance criteria, current status, key decisions
- **PR**: solution narrative, test plan, verification, risk/rollback
- **docs/adr/** (optional): architectural decisions that outlive the issue
- **Actions logs**: keep there; summarize outcomes in PR comments

## GitHub API Connectivity Troubleshooting (Sandbox)
If commands fail with errors like:
- `error connecting to api.github.com`
- `curl: (6) Could not resolve host: api.github.com`

use this workflow:
1. Assume sandbox network/DNS restrictions first (not immediate GitHub outage).
2. Re-run GitHub API commands outside sandbox using escalation (`sandbox_permissions: require_escalated`).
3. Save a reusable prefix approval for recurring commands (for example `gh workflow run`, `gh pr`, `gh run list/view/watch`).
4. Verify with:
   - `curl -sS -I https://api.github.com`
   - `gh run list -R <owner/repo> --limit 5`

Notes:
- `gh issue ...` may still work if that prefix was already approved, even when `curl` fails in sandbox.
- `gh auth status` can report misleading auth problems when network to GitHub API is blocked; confirm connectivity first.
