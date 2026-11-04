# A mod senses the Viewed agent; the Python statusline still renders

Status: proposed

Claude Code's statusLine stdin always describes the main session and is not re-run when the user switches the main view to a subagent or teammate (upstream anthropics/claude-code#83512, open). Only a mod can see the view: an `AbovePrompt` `ui.render` hook reads `e.props.view.agentId` and re-runs on every view switch. So the plugin ships a small mod that renders nothing and writes a per-session state file (`viewed-agent-<session_id>.json`) holding the [[Viewed agent]]'s transcript path, `agentType`, model and effort (from `agent-<id>.meta.json`). The Python statusline runs on `refreshInterval: 1`, reads that file by `session_id` from stdin and, when a subagent is in view, takes model, effort, ctx and cc from that transcript. Session time and the 5h/7d-limit Gauges stay global.

## Considered Options

- **Main session only** — rejected: the user watches subagents and wants their numbers.
- **Active agent (newest transcript mtime)** — rejected: shows an agent other than the one on screen and flickers with parallel subagents.
- **Mod renders its own usage band** — rejected: rendering logic duplicated in JS and Python (cf. ADR-0005, one render rule).
- **Whole statusline as a mod** — rejected: full rewrite for no gain.

## Consequences

- The mod, not `scripts/`, resolves Claude Code's subagent path layout, so ADR-0001 holds: Python receives a path.
- ADR-0003 (stdin + transcript only) gains one input: the mod's state file.
- The mod is optional. Without it, or on a Claude Code without `e.props.view`, the statusline shows the main session and `refreshInterval` is not set.
- View switches show up after up to ~1 s. The cost is one Python start per second.
- The mod deletes state files older than 7 days at startup.
- If upstream adds a viewed-agent field to stdin, drop the mod.

## Prototype findings (2026-11-04, CC 2.1.318)

- Foregrounding a subagent (`f` in `/tasks`, or Enter in the agent panel) re-ran the `AbovePrompt` hook with `e.props.view.agentId`. That id is the suffix of `subagents/agent-<id>.jsonl`. Returning to main re-ran it with no `agentId`. The `/tasks` details dialog alone is not a view switch.
- The hook re-runs only on view switches and prompt-area changes (7 runs in the whole test), so it is cheap.
- `$.agent.list()` gives `{ id, description, type, status }`, with no model or effort, so those come from `meta.json` and the transcript.
- `$.fs.write` to an absolute path outside the workspace works.
- `$.session.id()` matches the stdin `session_id`. The `classic.UserPromptSubmit` hook carries the main `transcript_path`.
- `CLAUDE_PLUGIN_DATA` is not set for the mod, so the state file goes under `~/.claude/claude-statusline/`.
- The statusline script takes about 105 ms per run (median of 10).
- Teammates (experimental, off by default) have no documented transcript path. They fall back to the main session.
- `prompt_cache.last_miss_cause` persists until the next miss. ADR-0009 matches it to a Turn via `last_miss_at`.
