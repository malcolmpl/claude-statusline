---
name: cache-stats
description: Per-turn cache_creation analysis for current session
argument-hint: "[transcript_path]"
allowed-tools: Bash(python3:*), Bash(python:*)
---

# Cache Stats

Run the cache stats analyzer and show the output verbatim.

The analyzer is at `scripts/cache_stats.py` in this plugin. It now requires a transcript path; this slash command resolves the current session's transcript before invoking it. See [ADR-0001](../docs/adr/0001-no-claude-code-paths-in-scripts.md) for why path resolution lives here, not in the script.

## Step 1: Resolve the script path

The script lives alongside `scripts/statusline.py`. Determine this plugin's install path using the same resolution order as `setup.md`:

1. `~/.claude/plugins/cache/claude-statusline-marketplace/claude-statusline/`
2. `~/.claude/plugins/cache/claude-statusline/claude-statusline/`
3. The repo working directory (local dev)

## Step 2: Resolve the transcript path

If the user passed an argument, use it verbatim as the transcript path and skip to Step 3.

Otherwise, resolve via the current session ID. Run this one-liner to print the matching JSONL path (or empty if not found):

```bash
python3 -c "import pathlib,sys; sid='${CLAUDE_SESSION_ID}'; m=list(pathlib.Path.home().glob(f'.claude/projects/*/{sid}.jsonl')); print(m[0] if m else '')"
```

If the output is empty, surface this message to the user and stop:

```
No transcript found for session ${CLAUDE_SESSION_ID} under ~/.claude/projects/*/. Pass a path explicitly: /cache-stats <path>
```

## Step 3: Run the analyzer

```bash
python3 <resolved-script-path>/scripts/cache_stats.py <resolved-transcript-path>
```

## Step 4: Present output

Print the script's stdout verbatim — it's a formatted ASCII table with summary and top spikes. Do not reformat or interpret unless the user asks.
