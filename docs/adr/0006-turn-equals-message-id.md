# One Turn per `message.id`; collapse transcript records

A [[Turn]] is one assistant API call, identified by `message.id`. Claude Code writes one JSONL [[Transcript record]] per content block (thinking, tool_use, text), all sharing the same `message.id` and repeating the same `usage`. The walker in `scripts/transcript.py` collapses these records — buffers the latest record of each msg.id run, emits one `ClassifiedTurn` when the run ends (next msg.id, non-assistant event, or EOF).

## Why

Counting each record as its own Turn double-counted `cache_creation`/`cache_read`. A two-block message (thinking + tool_use) yielded two `ClassifiedTurn`s with identical usage; record #2 saw record #1's `cache_read` as `prev_cr`, so `cc/prev_cr` approached `cc/cc ≈ 1.0` and crossed the 0.8 [[TTL Refresh]] ratio. Observed live: session `9e3809b9` line 10 (`cc=21733`, `cr=22639`, ratio 0.96) → false TTL! on the first user prompt of a fresh session, where no cache could possibly have expired.

The bug masqueraded as a session-boundary or first-turn issue. It was neither — the heuristic was sound; the walker had a stale model of "Turn".

## Decision

`transcript.turns()` keeps a `pending` record (latest seen). On each new assistant line, if `message.id` matches `pending`, replace `pending` (keep latest content so `tool_name` reflects the final block — typically `tool_use`). Otherwise flush `pending` as a `ClassifiedTurn`, then start a new run. Any non-assistant line flushes `pending` first.

`prev_cr` advances exactly once per emitted Turn.

## Considered options

- **Skip consecutive same `msg.id`, emit first record** — rejected. `_first_tool_name` runs against the thinking block (first), so `cache_stats` notes lose the tool name.
- **Track all seen `msg.id`s in a set** — rejected. O(n) memory for no benefit; empirically dups are always consecutive (Anthropic streams a single message's blocks atomically).
- **Consolidate content blocks into one merged record** — rejected. Larger refactor of `turns()` for no behavioural win; usage is identical across blocks, so taking the last record is sufficient.
- **Leave the walker, change thresholds** — rejected. The ratio isn't the problem; the unit is.

## Consequences

- `cache_stats` "Turns: N" now counts API calls, not records — typically ~halves for sessions with many tool-use messages.
- `tool_name` becomes more useful (no longer `None` whenever a Turn started with `thinking`).
- ADR-0002 and ADR-0004 remain unchanged in spirit; the [[Turn]] they refer to is now the precise notion.
- Older transcripts without `message.id` still walk correctly: dedup is guarded on `mid is not None`, so each record emits its own Turn (fallback to pre-fix behaviour).
