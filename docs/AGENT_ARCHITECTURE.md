# Chronicle Agent Architecture

## Goal

Chronicle should be able to use Codex from a separate machine without installing Codex on the Docker host. The agent must operate through stable Chronicle APIs, not browser automation or shell access to the Chronicle host.

## Components

### 1. Chronicle

Chronicle remains the system of record.

Responsibilities:

- store templates, profiles, workouts, and plan state
- expose agent-safe control APIs
- validate proposed changes
- apply approved changes through existing save paths
- persist drafts, jobs, and audit events

### 2. Chronicle Codex Companion

The companion runs on the machine where the user already has Codex installed and authenticated.

Responsibilities:

- receive Chronicle task requests
- run `codex exec`
- load repo-shipped skill/prompt assets
- return structured results

The companion does not:

- edit Chronicle files over SSH
- drive Chronicle’s UI
- own Chronicle state

### 3. Provider Abstraction

Chronicle supports:

- `local_codex_exec`
- `remote_codex_exec`

The editor assistant and higher-level agent tasks both route through the same provider interface.

## Resource Model

The control surface is resource-oriented, not page-oriented.

Primary resources:

- `templates`
- `profiles`
- `workouts`
- `plans`
- `drafts`
- `jobs`
- `audit`

This avoids coupling the agent to page layouts or frontend interactions.

## Task Lifecycle

Every non-trivial agent action should follow:

1. create job
2. gather Chronicle context
3. generate draft with Codex
4. validate draft
5. return warnings/diff identifiers
6. apply only after explicit approval or a scoped policy
7. audit the outcome

## Safety Model

Chronicle uses `draft -> validate -> apply`.

Important properties:

- agent proposals do not directly mutate live state
- validation occurs inside Chronicle
- remote apply requires a write credential
- dry-run is available on apply endpoints
- version checks reduce stale-write risk

## Remote Operating Model

Recommended deployment:

- Chronicle on the Docker server
- Codex Companion on the dev VM or other Codex-capable machine

Chronicle calls the companion over HTTP. The companion may call Chronicle’s control API for additional context if needed.

## Versioning

Both sides expose a protocol version handshake.

Current protocol:

- `COMPANION_PROTOCOL_VERSION=1`

This should be bumped when request/response contracts change incompatibly.

## Current Gaps

- no dedicated draft review UI yet
- no rollback endpoints for every resource type yet
- read/write auth is coarse-grained compared with future capability scopes
- plan validators are still structural, not yet full coaching-policy validators
