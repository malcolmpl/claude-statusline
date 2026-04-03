---
name: setup
description: Install and configure the custom statusline
argument-hint: ""
allowed-tools: Read, Write, Edit, Bash(python3:*), Bash(python:*), Bash(cat:*), Bash(mkdir:*), Bash(ls:*), AskUserQuestion
---

# Setup Statusline Plugin

Follow these steps exactly in order.

## Step 1: Configure statusline command

Determine this plugin's install path. The statusline script is at `scripts/statusline.py` relative to the plugin root.

Check these locations in order:
1. `~/.claude/plugins/cache/claude-statusline-marketplace/claude-statusline/` (marketplace install — use latest version subdir)
2. `~/.claude/plugins/cache/claude-statusline/claude-statusline/` (alt marketplace name)
3. The repo working directory if running during local development

Build the full path to `scripts/statusline.py` using forward slashes.

Update `~/.claude/settings.json` `statusLine` to:
```json
{
  "type": "command",
  "command": "python3 <resolved-path>/scripts/statusline.py"
}
```

## Step 2: Enable git hooks (optional, local dev only)

Only if the plugin was resolved from the repo working directory (option 3 in Step 1), ask the user if they want to enable auto-version-bump git hooks for development.
If yes, run: `git config core.hooksPath githooks` in the plugin repo directory.
If the plugin was installed from marketplace (options 1 or 2), skip this step entirely.

## Step 3: Confirm

Tell the user setup is complete. The statusline shows:
- Working directory, git branch, model name
- Context usage bar (color-coded: green/yellow/orange/red+blink)
- Token count, session duration
- Claude usage limits: session (5h) + weekly (7d) with reset timers

Restart Claude Code to see the new statusline.
