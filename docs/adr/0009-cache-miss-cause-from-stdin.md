# Main-session cache misses use Claude Code's reported cause

Status: proposed. Supersedes ADR-0002 for the main session.

ADR-0002 labelled `TTL!` from a token ratio, assuming a 5-minute TTL. Main-session writes on a subscription now default to a 1-hour TTL, while subagents keep 5 minutes. So a full prefix rebuild in the main session is now more often an invalidation (tools or system prompt changed, server side) than an expiry. Claude Code now reports this directly on stdin: `prompt_cache.last_miss_cause` (`ttl_expired_5m`, `tools_changed`, `system_prompt_changed`, `likely_server_side`, …), plus `misses`, `warm`, `ttl` and `expires_at`.

For the main session, the cc label is therefore taken from that cause: `TTL!` for an expiry, `rebuild!` for a tools or system-prompt change, `srv?` for the server side. `prompt_cache` excludes subagent requests, so a subagent in view ([[Viewed agent]], ADR-0008) keeps the ADR-0002 ratio heuristic.

`last_miss_cause` persists until the next miss. So the label applies only to the Turn whose timestamp matches `prompt_cache.last_miss_at`. Claude Code also uses a lower miss threshold (more than 5% and at least 2,000 tokens) than the ADR-0002 ratio (80%), so the two will disagree on borderline Turns.

## Considered Options

- **Keep the ratio only** — rejected: it reports invalidations as `TTL!`.
- **Ratio plus timestamp gap against the TTL bucket** — rejected for the main session, because Claude Code already knows the cause. It remains possible later for subagents.
