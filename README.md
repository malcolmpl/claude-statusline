# claude-statusline

A Claude Code plugin providing a custom statusline with context usage monitoring and rate limit tracking.

## Features

- **Context Usage Bar** — Color-coded progress bar (green < 60%, yellow, orange, red+blink at 80%+) with percentage and token count
- **Git Branch** — Current branch or detached HEAD hash
- **Model Info** — Active model display name
- **Session Duration** — Time since session start
- **Rate Limit Monitoring** — Session (5h) and weekly (7d) usage percentages with reset countdown timers, powered by [claude-dashboard](https://github.com/uppinote20/claude-dashboard)

## Requirements

- Claude Code 1.0.80+
- Python 3.8+ in PATH
- Node.js in PATH (for rate limit data via claude-dashboard)

## Dependencies

This plugin requires [claude-dashboard](https://github.com/uppinote20/claude-dashboard) for rate limit monitoring. The `/claude-statusline:setup` command auto-installs it if missing.

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
1. Auto-install `claude-dashboard` dependency if missing
2. Configure `settings.json` statusline command
3. Optionally enable git hooks for development

Restart Claude Code after setup to see the statusline.

### What it shows

```
/home/user/project | (main) | Claude Opus 4.6 | ▰▰▰▰▱▱▱▱▱▱ 40% | 80,000 / 200,000 | 12m30s | session: ▰▰▰▱▱▱▱▱▱▱ 25% resets 3h42m | weekly: ▰▰▰▰▰▰▱▱▱▱ 58% resets 4d12h
```

Segments separated by `|`:
- Working directory
- Git branch (if in a repo)
- Model name
- Context usage bar + percentage
- Token count (current / window size)
- Session duration
- Session rate limit (5h window) with reset timer
- Weekly rate limit (7d window) with reset timer

Rate limit data is cached for 120 seconds to avoid excessive API calls.

### Color coding

| Usage    | Color         |
|----------|---------------|
| < 60%    | Green         |
| 60-69%   | Yellow        |
| 70-79%   | Orange        |
| 80%+     | Red + blink   |

## Compatibility

- Windows, macOS, Linux
- Python subprocess uses `STARTUPINFO` on Windows to hide console flashes
- Git hook uses portable sed (GNU + BSD detection)
- All paths use `os.path` for cross-platform compatibility

## Architecture

- `scripts/statusline.py` — Main statusline script, reads JSON from stdin (Claude Code statusline protocol), outputs ANSI-formatted text
- `commands/setup.md` — `/claude-statusline:setup` slash command for automated installation
- Rate limit data sourced from `claude-dashboard`'s `check-usage.js` via subprocess, cached to `~/.claude/usage_cache.json`

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
