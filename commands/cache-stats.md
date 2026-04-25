---
name: cache-stats
description: Per-turn cache_creation analysis for current session
argument-hint: "[transcript_path]"
allowed-tools: Bash(python3:*), Bash(python:*)
---

# Cache Stats

Run the cache stats analyzer and show the output verbatim.

The analyzer is at `scripts/cache_stats.py` in this plugin. It takes an optional transcript path; without one it auto-finds the newest `*.jsonl` in `~/.claude/projects/<cwd-slug>/`.

## Step 1: Resolve the script path

The script lives alongside `scripts/statusline.py`. Determine this plugin's install path using the same resolution order as `setup.md`:

1. `~/.claude/plugins/cache/claude-statusline-marketplace/claude-statusline/`
2. `~/.claude/plugins/cache/claude-statusline/claude-statusline/`
3. The repo working directory (local dev)

## Step 2: Run the analyzer

If the user passed an argument, use it as the transcript path. Otherwise run with no argument (auto-find).

```bash
python3 <resolved-path>/scripts/cache_stats.py [optional-path]
```

## Step 3: Present output

Print the script's stdout verbatim — it's a formatted ASCII table with summary and top spikes. Do not reformat or interpret unless the user asks.

If stderr reports "No transcript path provided and no recent JSONL found", tell the user to pass a path explicitly or run from a directory that has a Claude Code session log under `~/.claude/projects/`.
