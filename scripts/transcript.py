"""Parse a Claude Code transcript JSONL into classified assistant turns.

Single source of truth for the session-window walk and the cc-spike
classification (see CONTEXT.md and ADR-0002/0004). Consumed by both
statusline.py and cache_stats.py.
"""

import json
import os
from dataclasses import dataclass
from enum import Enum
from typing import Iterator, Optional


TTL_RATIO = 0.8
TTL_MIN_PREV = 5000


class Kind(Enum):
    FIRST_TURN = "first_turn"
    TTL_REFRESH = "ttl_refresh"
    DATA_LOAD = "data_load"
    NORMAL = "normal"


@dataclass
class ClassifiedTurn:
    cc: int
    cache_read: int
    window_prompt_pos: int
    tool_name: Optional[str]
    timestamp: Optional[str]
    kind: Kind


_NON_PROMPT_PREFIXES = ("<local-command-caveat>", "<command-name>", "<system-reminder>")


def _is_real_prompt(obj):
    if obj.get("type") != "user":
        return False
    content = (obj.get("message") or {}).get("content")
    if not isinstance(content, str):
        return False
    return not content.startswith(_NON_PROMPT_PREFIXES)


def _is_window_reset(obj):
    if obj.get("type") != "user":
        return False
    content = (obj.get("message") or {}).get("content")
    if not isinstance(content, str):
        return False
    if not content.startswith("<command-name>"):
        return False
    return "/clear" in content or "/compact" in content


def _first_tool_name(content):
    if not isinstance(content, list):
        return None
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            return block.get("name")
    return None


def _classify(cc, prev_cache_read, window_prompt_pos):
    # ADR-0004: TTL fires independently inside the first turn.
    if prev_cache_read > TTL_MIN_PREV and cc / prev_cache_read > TTL_RATIO:
        return Kind.TTL_REFRESH
    if window_prompt_pos == 1:
        return Kind.FIRST_TURN
    if cc >= 10000:
        return Kind.DATA_LOAD
    return Kind.NORMAL


def turns(path) -> Iterator[ClassifiedTurn]:
    """Yield every assistant Turn (including cc=0), already classified.

    One Turn = one API call (one `message.id`). Claude Code splits a Turn
    across multiple JSONL records (one per content block, all repeating the
    same usage); we collapse them, keeping the last record so tool_name
    reflects the final block (typically `tool_use`).
    """
    if not path or not os.path.isfile(path):
        return
    window_prompt_pos = 0
    prev_cr = 0
    pending = None  # (cc, cr, content, msg_id, pos, ts)

    def build(rec):
        cc, cr, content, _mid, pos, ts = rec
        return ClassifiedTurn(
            cc=cc,
            cache_read=cr,
            window_prompt_pos=pos,
            tool_name=_first_tool_name(content),
            timestamp=ts,
            kind=_classify(cc, prev_cr, pos),
        )

    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    obj = json.loads(ln)
                except (json.JSONDecodeError, ValueError):
                    continue

                if obj.get("type") == "assistant":
                    msg = obj.get("message") or {}
                    mid = msg.get("id")
                    usage = msg.get("usage") or {}
                    cc = usage.get("cache_creation_input_tokens", 0) or 0
                    cr = usage.get("cache_read_input_tokens", 0) or 0
                    rec = (cc, cr, msg.get("content"), mid, window_prompt_pos, obj.get("timestamp"))
                    if pending is not None and mid is not None and pending[3] == mid:
                        pending = rec
                    else:
                        if pending is not None:
                            yield build(pending)
                            prev_cr = pending[1]
                        pending = rec
                    continue

                if pending is not None:
                    yield build(pending)
                    prev_cr = pending[1]
                    pending = None

                if _is_window_reset(obj):
                    window_prompt_pos = 0
                elif _is_real_prompt(obj):
                    window_prompt_pos += 1

            if pending is not None:
                yield build(pending)
    except OSError:
        return


def last_cc_turn(path) -> Optional[ClassifiedTurn]:
    """Return the last assistant Turn with cc>0, or None."""
    last = None
    for t in turns(path):
        if t.cc > 0:
            last = t
    return last


def fmt_k(n):
    """Compact: '500', '1.2k', '74k'."""
    if n < 1000:
        return str(n)
    if n < 10000:
        return f"{n/1000:.1f}k"
    return f"{round(n/1000)}k"
