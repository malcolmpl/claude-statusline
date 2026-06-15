# claude-statusline

Claude Code statusline plugin: a Python script Claude Code invokes each turn to render context usage, token counts, session/weekly limits, and a cache-creation heuristic. Ships with a `/cache-stats` slash command for per-turn `cache_creation_input_tokens` analysis.

## Glossary

- **Turn** — a single assistant API call, identified by `message.id`. Cache usage (`cache_creation_input_tokens`, `cache_read_input_tokens`) is reported per Turn. One user prompt may produce many Turns (tool-use cycles).
- **Transcript record** — a single JSONL line with `type:"assistant"`. Claude Code splits one Turn across multiple records — one per content block (thinking, tool_use, text) — all sharing the same `message.id` and repeating the same `usage`. Heuristics walk Turns, not records: a single Turn must be counted once regardless of record count.
- **Real prompt** — a `type:"user"` message whose `content` is a plain string and does NOT start with `<local-command-caveat>`, `<command-name>`, or `<system-reminder>`. Tool results (`content:list` with `tool_result`) and harness chatter are NOT real prompts.
- **Session window** — the stretch of transcript between two cache-resetting events. A new window starts at file beginning and after any `<command-name>/clear` or `<command-name>/compact`.
- **First turn** — every assistant turn belonging to the **first real prompt** of the current [[Session window]]. Cache creation here is dominated by system-prompt + CLAUDE.md load ("init noise"), not user-driven cost.
- **Init noise** — the large `cache_creation_input_tokens` value observed during a [[First turn]] because the cacheable prefix (system prompt, CLAUDE.md, tools schema) is being built. Not a signal of user behaviour; statusline dims it.
- **TTL Refresh** — a turn classified by the heuristic in [ADR-0002](./docs/adr/0002-ttl-refresh-heuristic.md): `cc > 80% * prev_cache_read` AND `prev_cache_read > 5k`. Independent signal from [[Init noise]] — fires even inside [[First turn]].
- **Data load** — a Turn where `cc ≥ 10_000` outside [[First turn]] / [[TTL Refresh]], typically driven by a large tool result (file Read, Grep dump) inflating the cache prefix. Diagnostic-only signal — statusline uses its size-based palette regardless of this classification; cache_stats tallies it separately.
- **Gauge** — a rendered progress segment: bar (`▰▱`) + percentage, colored by a shared palette (green/yellow/orange/red), with blink applied when `pct ≥ BLINK_THRESHOLD` (80). Three adapters today: context-window gauge, session-limit gauge, weekly-limit gauge. The render rule (palette + bar + blink) lives in one place so the three adapters cannot drift.

## Architectural decisions

- [ADR-0001](./docs/adr/0001-no-claude-code-paths-in-scripts.md) — Claude Code path conventions stay out of analysis scripts
- [ADR-0002](./docs/adr/0002-ttl-refresh-heuristic.md) — TTL Refresh detection heuristic
- [ADR-0003](./docs/adr/0003-stdin-only-no-external-deps.md) — Statusline reads only from Claude Code stdin payload
- [ADR-0004](./docs/adr/0004-first-turn-dim.md) — First-turn dim to suppress init noise
- [ADR-0005](./docs/adr/0005-no-kind-style-table.md) — No Kind→style table in cc segment
- [ADR-0006](./docs/adr/0006-turn-equals-message-id.md) — One Turn per `message.id`; collapse transcript records
- [ADR-0007](./docs/adr/0007-update-stable-install-path.md) — Install paths use the non-versioned marketplace clone, not the versioned cache
