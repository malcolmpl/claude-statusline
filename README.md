# claude-statusline

A Claude Code plugin providing a custom statusline with context usage monitoring and rate limit tracking.

## Features

- **Context Usage Bar** — Color-coded progress bar (green < 60%, yellow, orange, red+blink at 80%+) with percentage and token count
- **Git Branch** — Current branch or detached HEAD hash
- **Model Info** — Active model display name
- **Session Duration** — Time since session start
- **Rate Limit Monitoring** — Session (5h) and weekly (7d) usage percentages with reset countdown timers, sourced natively from Claude Code's stdin payload
- **Cache Creation Tracking** — `cc:` segment shows cache_creation_input_tokens of the last turn, with TTL-refresh detection and color-coded thresholds
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
2. Optionally enable git hooks for development

Restart Claude Code after setup to see the statusline.

### What it shows

```
/home/user/project | (master) | Claude Opus 4.7 | ▰▰▰▰▱▱▱▱▱▱ 40% | 80,000 / 200,000 | 12m30s | cc:1.2k | session: ▰▰▰▱▱▱▱▱▱▱ 25% resets 3h42m | weekly: ▰▰▰▰▰▰▱▱▱▱ 58% resets 4d12h
```

Segments separated by `|`:
- Working directory
- Git branch (if in a repo)
- Model name
- Context usage bar + percentage
- Token count (current / window size)
- Session duration
- `cc:` cache_creation tokens of the last turn (omitted on cold start)
- Session rate limit (5h window) with reset timer
- Weekly rate limit (7d window) with reset timer

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
| First turn          | `cc:Nk (init)` yellow        |
| TTL refresh         | `cc:Nk (TTL!)` red bold      |
| < 2k                | gray                         |
| 2k–10k              | yellow                       |
| 10k–30k             | `cc:Nk ⚠` red bold           |
| ≥ 30k               | `cc:Nk ‼` red inverse        |

TTL refresh = current `cc > 80%` of previous `cache_read_input_tokens` (with previous ≥ 5k), indicating the 5-minute prompt cache TTL expired and the prefix was re-cached.

### /claude-statusline:cache-stats

Run `/claude-statusline:cache-stats` (or `python scripts/cache_stats.py [transcript.jsonl]`) to print a per-turn table of `cache_creation_input_tokens` for the current session, plus a summary categorizing tokens into init / data loads / TTL refresh / normal, and the top 3 spikes. Auto-finds the newest transcript under `~/.claude/projects/<cwd-slug>/` when called with no argument.

## Compatibility

- Windows, macOS, Linux
- Python subprocess uses `STARTUPINFO` on Windows to hide console flashes
- Git hook uses portable sed (GNU + BSD detection)
- All paths use `os.path` for cross-platform compatibility

## Architecture

- `scripts/statusline.py` — Main statusline script, reads JSON from stdin (Claude Code statusline protocol), outputs ANSI-formatted text
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
