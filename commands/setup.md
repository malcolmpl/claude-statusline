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

Resolve the **real interpreter**, not a launcher: run `python3 -c "import sys; print(sys.executable)"` (if `python3` is missing, use `python`). Use the printed path with forward slashes; wrap it in double quotes if it contains a space. Do not write a bare `python3`/`python`: on Windows that is often a shim (scoop, pyenv-win) which starts the real `python.exe` suspended and resumes it later. When Claude Code cancels a run inside that gap, the interpreter stays suspended forever (#5). If the printed path holds a version dir (e.g. `scoop/apps/python/3.13.1/`) and a sibling `current/` holds the same `python.exe`, use the `current/` path so an interpreter update does not break the statusline.

Update `~/.claude/settings.json` `statusLine` to:
```json
{
  "type": "command",
  "command": "<resolved-interpreter> <resolved-absolute-root>/scripts/statusline.py"
}
```

If `statusLine` already exists (e.g. `python3 .../statusline.py` from an earlier setup), Edit only the `command` value; keep `refreshInterval` and every other key.

Then verify: pipe `{}` into the resolved command and confirm it prints a statusline and exits 0.

## Step 1b: Enable the viewed-agent mod and the 1 s refresh

The plugin ships a mod (`hooks/hooks.json` → `hooks/viewed-agent.ts`) that tells the statusline which agent is in the main view, so model, effort, ctx and cc follow a foregrounded subagent (ADR-0008). It loads with the plugin; there is nothing to copy.

1. Make sure the plugin is enabled: in `~/.claude/settings.json`, `enabledPlugins` must hold `"claude-statusline@claude-statusline-marketplace": true` (add it if missing; leave other entries alone). For a local `--plugin-dir` checkout, skip this item.
2. Only if the plugin is enabled (item 1) or loaded via `--plugin-dir`, add `"refreshInterval": 1` to the `statusLine` object from Step 1, keeping `type` and `command`:
   ```json
   { "type": "command", "command": "<resolved-interpreter> <resolved-absolute-root>/scripts/statusline.py", "refreshInterval": 1 }
   ```
   Claude Code does not re-run the statusline on a view switch, so the 1 s refresh is what picks the switch up (one Python run per second, ~0.15-0.45 s each on Windows). Without the mod, do not set `refreshInterval`: the statusline then shows the main session only, unchanged.

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
- When a subagent is foregrounded (`f` in `/tasks`, or Enter in the agent panel): `↳<agentType>` and that subagent's model, effort, ctx and cc, within ~1 s

Restart Claude Code to see the new statusline.
