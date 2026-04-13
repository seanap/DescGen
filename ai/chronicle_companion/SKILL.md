# Chronicle Codex Companion

This companion runs on a machine that already has Codex installed and logged in.

Its role:
- accept structured task requests from Chronicle
- use `codex exec` with Chronicle-owned prompts and output schemas
- return structured JSON responses
- optionally call Chronicle's agent control API for read-only context gathering

Safety model:
- prefer drafts over direct apply
- return structured warnings when context is incomplete
- do not mutate Chronicle state directly unless the request explicitly asks for an apply step and Chronicle has already validated the draft
