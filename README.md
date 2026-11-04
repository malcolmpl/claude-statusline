# claude-statusline

A Claude Code plugin providing a custom statusline with context usage monitoring and rate limit tracking.

## Features

- **Context Usage Bar** — Color-coded progress bar (green < 60%, yellow, orange, red+blink at 80%+) with percentage and token count
- **Git Branch** — Current branch or detached HEAD hash
- **Model Info** — Active model display name + effort level
- **Session Duration** — Time since session start
- **Rate Limit Monitoring** — Session (5h) and weekly (7d) usage percentages with reset countdown timers, sourced natively from Claude Code's stdin payload
- **Cache Creation Tracking** — `cc:` segment shows cache_creation_input_tokens of the last turn, with cache-miss cause labels (TTL / rebuild / server) and color-coded thresholds
- **Viewed agent** — Foreground a subagent (`f` in `/tasks`, or Enter in the agent panel) and model, effort, ctx and cc switch to it, prefixed with a dimmed `↳<agentType>`. Session time and the 5h/7d gauges stay global
- **/cache-stats command** — Per-turn cache_creation breakdown for the current session with summary and top spikes

## Requirements

- Claude Code 1.0.80+
- Python 3.8+ in PATH

## Installation

### From marketplace (recommended)

Add the marketplace and install the plugin:

```shell
/plugin marketplace add malcolmpl/claude-statusline
/plugin install claude-statusline@claude-statusline-marketplace
```

Then run the setup command to configure everything:

```shell
/claude-statusline:setup
```

### From local directory (development)

Clone the repo and load it directly:

```bash
git clone https://github.com/malcolmpl/claude-statusline.git
claude --plugin-dir ./claude-statusline
```

After installing, run `/claude-statusline:setup` to configure the statusline and install dependencies.

## Usage

### Setup

Run `/claude-statusline:setup` to:
1. Configure `settings.json` statusline command
2. Enable the viewed-agent mod and set `statusLine.refreshInterval: 1`
3. Optionally enable git hooks for development

Restart Claude Code after setup to see the statusline.

### What it shows

```
/home/user/project | (master)
Opus 5.5 high | ctx: ▰▰▰▰▱▱▱▱▱▱ 40% 80,000 / 200,000 | 12m30s | cc:1.2k | 5h: ▰▰▰▱▱▱▱▱▱▱ 25% ↻3h42m | 7d: ▰▰▰▰▰▰▱▱▱▱ 58% ↻4d12h
```

Two lines, segments separated by `|`.

Line 1 — location:
- Working directory
- Git branch (if in a repo)

Line 2 — usage:
- Model name + effort (`low`…`max`, from the transcript, else stdin `effort.level`; omitted when unknown)
- `ctx:` context usage bar + percentage + token count (`used / window size`; `used` only for 1M+ windows). `used` = input + cache read + cache creation
- Session duration
- `cc:` cache_creation tokens of the last turn (omitted on cold start)
- `5h:` 5-hour rate limit with time until reset (`↻`)
- `7d:` 7-day rate limit with time until reset (`↻`)

### Viewed agent (subagents)

```
↳Explore Sonnet 5.5 medium | ctx: ▱▱▱▱▱▱▱▱▱▱ 2% 24,310 | 46m07s | cc:1.2k | 5h: … | 7d: …
```

Claude Code's statusline stdin always describes the main session and is not re-run on a view switch. The plugin ships a small mod (`hooks/viewed-agent.ts`) whose `AbovePrompt` hook renders nothing and, on each view switch, writes `~/.claude/claude-statusline/viewed-agent-<session_id>.json` (subagent transcript path, `agentType`, and model/effort from `agent-<id>.meta.json`). With `refreshInterval: 1` the statusline reads that file and takes, from the subagent's transcript:

- model — `message.model`, `claude-<family>-<maj>-<min>` → `Family maj.min`, raw id otherwise
- effort — the record's `effort`, else `meta.json`; omitted when unknown (never the session's)
- ctx — last turn's input + cache read + cache creation. The window is sized by the subagent's own model ([docs](https://code.claude.com/docs/en/sub-agents)): the main session's stdin window when the model is the same (covers `[1m]` and 1M-off), else the model's default — 1M for Fable, Sonnet 5+, Haiku 5.5, Opus 4.7+; 200K for older models ([docs](https://code.claude.com/docs/en/model-config)), capped at 200K when `CLAUDE_CODE_DISABLE_1M_CONTEXT` is set or the main session runs a native-1M model at 200K; stepped up to 1M if usage exceeds 200K. Unknown model → token count only, no bar or %
- cc — last turn with cc > 0, labelled by the TTL ratio heuristic (`prompt_cache` covers the main session only)

A finished subagent keeps its last numbers. If the state file is missing, unreadable, names main, or its transcript is gone, the line shows the main session with no marker. Teammates fall back to main. The mod deletes state files older than 7 days at session start. Without the mod, behaviour is unchanged. See [ADR-0008](docs/adr/0008-mod-sensor-for-viewed-agent.md).

Rate limit data comes from the `rate_limits` field in Claude Code's statusline stdin payload — no external dependencies, no caching layer.

### Color coding

Context usage bar:

| Usage    | Color         |
|----------|---------------|
| < 60%    | Green         |
| 60-69%   | Yellow        |
| 70-79%   | Orange        |
| 80%+     | Red + blink   |

`cc:` segment:

| Condition           | Render                       |
|---------------------|------------------------------|
| Cache miss: TTL     | `cc:Nk (TTL!)` red bold      |
| Cache miss: tools / system prompt changed | `cc:Nk (rebuild!)` red bold |
| Cache miss: server side | `cc:Nk (srv?)` red bold  |
| First turn          | gray (init noise)            |
| < 2k                | gray                         |
| 2k–10k              | yellow                       |
| 10k–30k             | `cc:Nk ⚠` red bold           |
| ≥ 30k               | `cc:Nk ‼` red inverse        |

Cache-miss labels come from Claude Code's stdin `prompt_cache.last_miss_cause` (CC ≥ 2.1.260) and show only on the turn whose time matches `prompt_cache.last_miss_at` (the cause persists until the next miss). Without `prompt_cache`, the size palette applies with no label. See [ADR-0009](docs/adr/0009-cache-miss-cause-from-stdin.md).

The ratio heuristic — `cc > 80%` of previous `cache_read_input_tokens` (previous ≥ 5k) — is kept only for `/cache-stats` (and subagent turns).

### /claude-statusline:cache-stats

Run `/claude-statusline:cache-stats` (or `python scripts/cache_stats.py [transcript.jsonl]`) to print a per-turn table of `cache_creation_input_tokens` for the current session, plus a summary categorizing tokens into init / data loads / TTL refresh / normal, and the top 3 spikes. Auto-finds the newest transcript under `~/.claude/projects/<cwd-slug>/` when called with no argument.

## Compatibility

- Windows, macOS, Linux
- Python subprocess uses `STARTUPINFO` on Windows to hide console flashes
- Git hook uses portable sed (GNU + BSD detection)
- All paths use `os.path` for cross-platform compatibility

## Architecture

- `scripts/statusline.py` — Main statusline script, reads JSON from stdin (Claude Code statusline protocol), outputs ANSI-formatted text
- `scripts/viewed_agent.py` — Reads the mod's viewed-agent state file; model id → name and context-window table
- `hooks/viewed-agent.ts` — Mod (function hooks) sensing the Viewed agent; tests in `hooks/viewed-agent.test.tsx` (`claude plugin test .`)
- `scripts/cache_stats.py` — Per-turn `cache_creation_input_tokens` analyzer for a session transcript
- `commands/setup.md` — `/claude-statusline:setup` slash command for automated installation
- `commands/cache-stats.md` — `/claude-statusline:cache-stats` slash command wrapping `cache_stats.py`
- Rate limit data sourced from Claude Code's native `rate_limits` stdin field (no subprocess, no cache file)

## Development

After cloning, enable git hooks for auto version bumping:

```bash
git config core.hooksPath githooks
```

The `post-commit` hook automatically:
- Bumps version in `plugin.json` and `marketplace.json` based on conventional commits (`feat:` → minor, `fix:`/`chore:` → patch, `BREAKING CHANGE` → major)
- Only triggers when plugin files change (not docs/README)
- Tags releases for `feat:` and `BREAKING CHANGE` commits
- `[release]` in commit message forces a tag on any bump type
- `[skip-bump]` skips version bumping entirely

## License

MIT — see [LICENSE](LICENSE)
