# claude-statusline

Claude Code statusline plugin: a Python script Claude Code invokes each turn to render context usage, token counts, session/weekly limits, and a cache-creation heuristic. Ships with a `/cache-stats` slash command for per-turn `cache_creation_input_tokens` analysis.

## Architectural decisions

- [ADR-0001](./docs/adr/0001-no-claude-code-paths-in-scripts.md) — Claude Code path conventions stay out of analysis scripts
