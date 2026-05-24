# TTL Refresh detection heuristic

A [[Turn]] is classified as a **TTL Refresh** when `cc > 80% * prev_cache_read` AND `prev_cache_read >= 5k`. The Anthropic API doesn't report cache expiry directly, so we infer it from token-usage shape: a turn that re-creates most of what was just being read implies the 5-minute prompt-cache TTL expired between turns.

## Why these thresholds

The 80% ratio and 5k floor are author-set defaults, not empirical. The ratio is high enough that ordinary Data Loads (new tool results appended on top of an existing cached prefix) don't trigger it; the floor avoids classifying tiny early-session turns as TTL events when there's barely any cache to expire. They can be tuned without architectural impact — they live as constants in `scripts/statusline.py` (`TTL_RATIO`, `TTL_MIN_PREV`), shared with `cache_stats.py`.

## Considered options

- **Timestamp delta** (compare turn timestamps against the 5-minute window) — not implemented. Would be more direct, but the token-ratio heuristic was simpler and good enough.
