# Install paths reference the marketplace clone, never the versioned cache

The `statusLine.command` in `settings.json`, and any slash command resolving `scripts/*.py`, point at the **non-versioned marketplace git clone** (`~/.claude/plugins/marketplaces/<marketplace>/scripts/...`), discovered at resolve time. They never point at the versioned cache dir (`~/.claude/plugins/cache/.../<VERSION>/...`).

## Why

`setup.md` previously wrote the active versioned cache path (`.../claude-statusline/1.0.6/scripts/statusline.py`) into the user's `settings.json`. On the next plugin update Claude Code deletes the old version subdir, so the pinned path 404s and `python3` exits non-zero — the statusline silently vanishes. This reproduced on Linux while a Windows machine (still pinned to a version that happened to exist) kept working: a phantom "OS-specific" bug that was really a stale path. Same failure class as [ADR-0001](./0001-no-claude-code-paths-in-scripts.md) — a Claude Code layout convention (here, the version-numbered cache dir) baked into config becomes a bug when that convention drifts.

The marketplace clone is the canonical source Claude Code keeps current in place via `git pull`; its path is derived from the marketplace, not the release version, so it survives updates. It is identical across OSes (`~/.claude/plugins/marketplaces/`), unlike a `SessionStart` mirror hook whose POSIX `cp`/`mkdir` command would re-introduce the very Windows-vs-Linux split this fixes.

## How install paths resolve now

`setup.md` and `cache-stats.md` **discover** the root: glob `~/.claude/plugins/marketplaces/*/`, pick the dir whose `.claude-plugin/marketplace.json` `name` is `claude-statusline-marketplace` (or that contains `scripts/statusline.py`). The dir name is never hardcoded — if Claude Code derives it from the git slug rather than the `name` field, discovery still finds it. Local-checkout fallback is kept for dev installs.

## Consequences

- The statusline survives plugin updates; no version pinning, no mirror hook, no `plugin.json` change.
- The clone tracks the marketplace's default-branch HEAD, which can be ≥ the activated cache version. The statusline is defensively coded against the stable stdin contract ([ADR-0003](./0003-stdin-only-no-external-deps.md)), so that divergence is benign — but it is the *current marketplace checkout*, not necessarily the *activated version*.
- Plugins cannot declare a main `statusLine` natively (only `subagentStatusLine`), and `${CLAUDE_PLUGIN_ROOT}` is not expanded in `statusLine.command` — so a discovered absolute path in the user's `settings.json` remains the only mechanism.
