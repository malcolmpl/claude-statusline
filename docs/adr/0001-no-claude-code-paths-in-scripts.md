# Claude Code path conventions stay out of analysis scripts

Scripts in `scripts/` analyze JSONL transcripts; they accept a path and return analysis. They do **not** know about `~/.claude/projects/`, the cwd→slug mapping, or any other Claude Code layout convention. Path resolution lives in slash command markdown (`commands/*.md`), where Claude Code-specific glue belongs.

## Why

The previous `cache_stats.py` reimplemented Claude Code's cwd→slug rules and walked `~/.claude/projects/<slug>/` to auto-discover the newest transcript. The slug rules were OS-conditional and silently broke on macOS/Linux (`lstrip("-")` stripped the leading dash that POSIX paths require), so `/cache-stats` never found a transcript on those platforms. Every Claude Code convention baked into the script is a future bug when that convention drifts.

## How we resolve the transcript now

`commands/cache-stats.md` resolves the path once, using `${CLAUDE_SESSION_ID}` (a documented slash-command substitution) and globbing `~/.claude/projects/*/<session-id>.jsonl` via `pathlib.Path.home()`. The session ID is unique, so the project directory becomes a wildcard — the slug format is no longer our concern. The resolved path is passed to `cache_stats.py` as a positional argument.

## Consequences

- `cache_stats.py` requires an explicit path argument and exits non-zero without one. No fallback.
- Tests no longer touch `HOME`/`USERPROFILE` or `~/.claude/`.
- If Claude Code ever changes its project-directory convention, only the one-line glob in `commands/cache-stats.md` needs updating.
