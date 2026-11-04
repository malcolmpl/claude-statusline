"""Parse a Claude Code transcript JSONL into classified assistant turns.

Single source of truth for the session-window walk and the cc-spike
classification (see CONTEXT.md and ADR-0002/0004). Consumed by both
statusline.py and cache_stats.py.
"""

import json
import math
import os
from dataclasses import dataclass
from datetime import datetime
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
    # Timestamp of the record just before the Turn (prompt / tool_result):
    # roughly when the request was sent. Lower bound for miss matching.
    request_timestamp: Optional[str] = None
    effort: Optional[str] = None


@dataclass
class Latest:
    cc_turn: Optional[ClassifiedTurn]  # last Turn with cc>0
    effort: Optional[str]              # top-level `effort` of the last assistant record


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
    pending = None  # (cc, cr, content, msg_id, pos, ts, request_ts, effort)
    last_ts = None  # timestamp of the last record read

    def build(rec):
        cc, cr, content, _mid, pos, ts, req_ts, effort = rec
        return ClassifiedTurn(
            cc=cc,
            cache_read=cr,
            window_prompt_pos=pos,
            tool_name=_first_tool_name(content),
            timestamp=ts,
            kind=_classify(cc, prev_cr, pos),
            request_timestamp=req_ts,
            effort=effort,
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
                ts_before, last_ts = last_ts, obj.get("timestamp") or last_ts

                if obj.get("type") == "assistant":
                    msg = obj.get("message") or {}
                    mid = msg.get("id")
                    usage = msg.get("usage") or {}
                    cc = usage.get("cache_creation_input_tokens", 0) or 0
                    cr = usage.get("cache_read_input_tokens", 0) or 0
                    effort = obj.get("effort")
                    effort = str(effort) if effort not in (None, "") else None
                    same = pending is not None and mid is not None and pending[3] == mid
                    req_ts = pending[6] if same else ts_before
                    rec = (cc, cr, msg.get("content"), mid, window_prompt_pos,
                           obj.get("timestamp"), req_ts, effort)
                    if not same and pending is not None:
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


def latest(path) -> Latest:
    """One pass: last Turn with cc>0 and the last assistant record's effort."""
    last_cc = None
    effort = None
    for t in turns(path):
        effort = t.effort
        if t.cc > 0:
            last_cc = t
    return Latest(cc_turn=last_cc, effort=effort)


def last_cc_turn(path) -> Optional[ClassifiedTurn]:
    """Return the last assistant Turn with cc>0, or None."""
    return latest(path).cc_turn


# ADR-0009: main-session cache-miss label from Claude Code's stdin `prompt_cache`.
MISS_SLACK_S = 2
_REBUILD_CAUSES = ("tools_changed", "system_prompt_changed")


def _epoch(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _turn_matches(turn, miss_at):
    """True if `miss_at` (epoch s) falls inside the Turn's request..response span.

    Lower bound is the record before the Turn (request sent), so a cause that
    persisted from an earlier Turn never matches a later one.
    """
    end = _epoch(turn.timestamp)
    if end is None:
        return False
    start = _epoch(turn.request_timestamp)
    if start is None:
        start = math.floor(end) - MISS_SLACK_S
    return start <= miss_at <= math.ceil(end) + MISS_SLACK_S


def miss_label(prompt_cache, turn) -> Optional[str]:
    """'TTL!' / 'rebuild!' / 'srv?' when the shown Turn is the reported miss, else None."""
    if not isinstance(prompt_cache, dict) or turn is None:
        return None
    miss_at = prompt_cache.get("last_miss_at")
    cause = prompt_cache.get("last_miss_cause")
    if not isinstance(miss_at, (int, float)) or not isinstance(cause, dict):
        return None
    causes = [c for c in (cause.get("causes") or []) if isinstance(c, str)]
    if not causes or not _turn_matches(turn, float(miss_at)):
        return None
    if any(c.startswith("ttl_expired") for c in causes):
        return "TTL!"
    if any(c in _REBUILD_CAUSES for c in causes):
        return "rebuild!"
    if "likely_server_side" in causes:
        return "srv?"
    return None


def main_session_kind(turn) -> Kind:
    """Turn kind without the ADR-0002 ratio heuristic (main session, ADR-0009)."""
    if turn.kind != Kind.TTL_REFRESH:
        return turn.kind
    if turn.window_prompt_pos == 1:
        return Kind.FIRST_TURN
    return Kind.DATA_LOAD if turn.cc >= 10000 else Kind.NORMAL


def fmt_k(n):
    """Compact: '500', '1.2k', '74k'."""
    if n < 1000:
        return str(n)
    if n < 10000:
        return f"{n/1000:.1f}k"
    return f"{round(n/1000)}k"
