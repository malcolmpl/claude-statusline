# First-turn dim to suppress init noise

The statusline dims the `cc:Nk` segment (no colour, no icon, no label) for every assistant [[Turn]] inside the [[First turn]] of the current [[Session window]]. [[TTL Refresh]] highlights still fire normally — they are an independent signal.

## Why

Claude Code loads CLAUDE.md, the system prompt, and tool schemas on the first turn of a session window. That load shows up as a large `cache_creation_input_tokens` value, which under the size-based colouring rules in `render_cc_segment` would render red+icon (`⚠` / `‼`). This is [[Init noise]], not user-driven cost — flagging it every session start was noise.

## Decision

In `read_last_cc` (`scripts/statusline.py`) walk the whole transcript and track a `current_window_prompt_count` that:

- starts at 0,
- resets to 0 on any `type:"user"` message whose string content starts with `<command-name>/clear` or `<command-name>/compact`,
- increments on each [[Real prompt]].

For the last assistant turn with `cc>0`, snapshot the count at the moment of that turn. `is_first_turn` is true iff that snapshot == 1.

`render_cc_segment` then short-circuits: when `is_first_turn` and not TTL → render `{DIM}cc:Nk{RESET}` with no label, no icon, regardless of size. TTL detection runs unchanged.

`scripts/cache_stats.py` keeps the raw number visible and adds an `init` annotation for turns in [[First turn]] (post `/clear`/`/compact` too). Diagnostic tool keeps all signal; statusline trades signal for less noise.

## Considered options

- **Hide the cc segment entirely on first turn** — rejected. Loses the diagnostic data for users who *do* want to see init magnitude.
- **Plain (uncoloured) `cc:Nk` instead of dim** — rejected. Dim is the existing low-priority visual idiom; plain reads as "normal value".
- **Keep an `(init)` label** — rejected. User wants minimal visual footprint; the dim itself conveys "ignore me".
- **Detect session resume (`claude --resume`) and reset first-turn** — rejected. Resume is rare; the [[TTL Refresh]] heuristic will likely fire on the resumed turn and provide a (different but semantically correct) highlight.

## Consequences

- A genuinely high `cc` that happens during the first turn (e.g. user opens session with a prompt that triggers a huge tool result) will be dimmed. TTL detection is the safety net — if cache truly refreshed mid-turn, the TTL highlight still fires.
- Slash commands other than `/clear` and `/compact` (e.g. `/cache-stats`, `/setup`) do NOT reset the window. They are not cache-resetting events.
- Requires walking the full transcript (already done for `total_assistant`). No additional I/O.
