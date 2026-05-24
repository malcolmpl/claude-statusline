# claude-statusline

Claude Code statusline plugin: a Python script Claude Code invokes each turn to render context usage, token counts, session/weekly limits, and a cache-creation heuristic. Ships with a `/cache-stats` slash command for per-turn `cache_creation_input_tokens` analysis.

## Glossary

- **Turn** — a single assistant message in the transcript JSONL (`type:"assistant"`). One user prompt may produce many turns (tool-use cycles).
- **Real prompt** — a `type:"user"` message whose `content` is a plain string and does NOT start with `<local-command-caveat>`, `<command-name>`, or `<system-reminder>`. Tool results (`content:list` with `tool_result`) and harness chatter are NOT real prompts.
- **Session window** — the stretch of transcript between two cache-resetting events. A new window starts at file beginning and after any `<command-name>/clear` or `<command-name>/compact`.
- **First turn** — every assistant turn belonging to the **first real prompt** of the current [[Session window]]. Cache creation here is dominated by system-prompt + CLAUDE.md load ("init noise"), not user-driven cost.
- **Init noise** — the large `cache_creation_input_tokens` value observed during a [[First turn]] because the cacheable prefix (system prompt, CLAUDE.md, tools schema) is being built. Not a signal of user behaviour; statusline dims it.
- **TTL Refresh** — a turn classified by the heuristic in [ADR-0002](./docs/adr/0002-ttl-refresh-heuristic.md): `cc > 80% * prev_cache_read` AND `prev_cache_read > 5k`. Independent signal from [[Init noise]] — fires even inside [[First turn]].

## Architectural decisions

- [ADR-0001](./docs/adr/0001-no-claude-code-paths-in-scripts.md) — Claude Code path conventions stay out of analysis scripts
- [ADR-0002](./docs/adr/0002-ttl-refresh-heuristic.md) — TTL Refresh detection heuristic
- [ADR-0003](./docs/adr/0003-stdin-only-no-external-deps.md) — Statusline reads only from Claude Code stdin payload
- [ADR-0004](./docs/adr/0004-first-turn-dim.md) — First-turn dim to suppress init noise
