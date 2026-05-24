# Statusline reads only from Claude Code stdin payload

The statusline derives every signal it renders ([[Context Usage]], [[Rate Limit Usage]], model, [[Session]] duration, [[Cache Creation]]) from the JSON payload Claude Code pipes to it on stdin, plus the [[Session]]'s transcript JSONL for per-turn history. No external CLI is invoked, no shared cache file is written, no background process is required.

## Why

Earlier versions depended on `claude-dashboard` for rate-limit data. That was removed in v1.0.3 because (a) the extra install step frustrated users, (b) the on-disk cache file created consistency issues, and (c) Claude Code began exposing `rate_limits` directly in the statusline stdin payload, making the dependency redundant.

## Consequences

- The statusline is fully functional with only Python in PATH — no provisioning, no daemon.
- We are coupled to the shape of Claude Code's statusline stdin contract. If the `rate_limits` field is renamed or removed upstream, the corresponding segments break.
- Anything not in the stdin payload or the transcript JSONL is out of scope for this plugin. Adding a new signal means first asking "is this already in stdin?" — if not, we don't add it.
