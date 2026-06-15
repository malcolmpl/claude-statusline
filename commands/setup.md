---
name: setup
description: Install and configure the custom statusline
argument-hint: ""
allowed-tools: Read, Write, Edit, Bash(python3:*), Bash(python:*), Bash(cat:*), Bash(mkdir:*), Bash(ls:*), AskUserQuestion
---

# Setup Statusline Plugin

Follow these steps exactly in order.

## Step 1: Configure statusline command

The statusline script is at `scripts/statusline.py` relative to the plugin root. Pick an **update-stable** path — do NOT point at the versioned cache dir (`~/.claude/plugins/cache/.../<VERSION>/...`): that version subdir is deleted on every plugin update, which silently breaks the statusline.

Resolve the plugin root by **discovering** it (don't hardcode the dir name — it may derive from the marketplace git slug, not the `name` field):

1. **Marketplace install (preferred, non-versioned, survives updates):** glob `~/.claude/plugins/marketplaces/*/` and pick the dir whose `.claude-plugin/marketplace.json` `name` is `claude-statusline-marketplace`, or that contains `scripts/statusline.py`. This is the marketplace git clone, kept current in place by Claude Code — its path never changes across updates.
2. **Local development:** the repo working directory, if running from a local checkout.

Resolve the chosen root to an **absolute** path (expand `~`/`$HOME`) and build `<root>/scripts/statusline.py` with forward slashes.

Update `~/.claude/settings.json` `statusLine` to:
```json
{
  "type": "command",
  "command": "python3 <resolved-absolute-root>/scripts/statusline.py"
}
```

Then verify: pipe `{}` into the resolved command and confirm it prints a statusline and exits 0.

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
