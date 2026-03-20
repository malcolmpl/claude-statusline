---
name: setup
description: Install and configure the custom statusline (auto-installs claude-dashboard dependency)
argument-hint: ""
allowed-tools: Read, Write, Edit, Bash(jq:*), Bash(cat:*), Bash(mkdir:*), Bash(node:*), Bash(ls:*), AskUserQuestion
---

# Setup Statusline Plugin

Follow these steps exactly in order.

## Step 1: Ensure claude-dashboard dependency

Read `~/.claude/settings.json`.

Check if BOTH conditions are met:
1. `extraKnownMarketplaces` has `"claude-dashboard"` with source `"uppinote20/claude-dashboard"`
2. `enabledPlugins` has `"claude-dashboard@claude-dashboard": true`

If either is missing, add them to `settings.json` using the Edit tool.

Then check if `~/.claude/plugins/cache/claude-dashboard/claude-dashboard/` exists and has version subdirectories:
```
ls ~/.claude/plugins/cache/claude-dashboard/claude-dashboard/
```

If the directory doesn't exist or is empty, tell the user:
> claude-dashboard configured but not yet downloaded. Restart Claude Code, then run `/claude-statusline:setup` again.

Then STOP — do not continue to further steps.

## Step 2: Configure statusline command

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

## Step 3: Enable git hooks (optional)

Ask the user if they want to enable auto-version-bump git hooks for development.
If yes, run: `git config core.hooksPath githooks` in the plugin repo directory.

## Step 4: Confirm

Tell the user setup is complete. The statusline shows:
- Working directory, git branch, model name
- Context usage bar (color-coded: green/yellow/orange/red+blink)
- Token count, session duration
- Claude usage limits: session (5h) + weekly (7d) with reset timers

Restart Claude Code to see the new statusline.
