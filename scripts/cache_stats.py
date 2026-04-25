#!/usr/bin/env python3
"""Per-turn cache_creation analysis for Claude Code session JSONL."""

import json
import os
import sys
from statusline import TTL_RATIO, TTL_MIN_PREV


RED   = "\033[31m"
DIM   = "\033[2m"
RESET = "\033[0m"


def analyze(transcript_path):
    """Return {turns: [...], total_cc: int}.

    Each turn: {index, cc, cache_read, tool_name, timestamp}.
    """
    result = {"turns": [], "total_cc": 0}
    if not transcript_path or not os.path.isfile(transcript_path):
        return result

    idx = 0
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    obj = json.loads(ln)
                except (json.JSONDecodeError, ValueError):
                    continue
                if obj.get("type") != "assistant":
                    continue
                msg = obj.get("message") or {}
                usage = msg.get("usage") or {}
                cc = usage.get("cache_creation_input_tokens", 0) or 0
                cr = usage.get("cache_read_input_tokens", 0) or 0
                tool_name = _first_tool_name(msg.get("content"))
                ts = obj.get("timestamp")
                result["turns"].append({
                    "index": idx,
                    "cc": cc,
                    "cache_read": cr,
                    "tool_name": tool_name,
                    "timestamp": ts,
                })
                result["total_cc"] += cc
                idx += 1
    except Exception:
        return result
    return result


def _first_tool_name(content):
    if not isinstance(content, list):
        return None
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            return block.get("name")
    return None


def _classify_turn(turn, prev_cache_read):
    """Return 'init' | 'ttl' | 'data_load' | 'normal'."""
    cc = turn["cc"]
    if turn["index"] == 0:
        return "init"
    if prev_cache_read > TTL_MIN_PREV and cc / prev_cache_read > TTL_RATIO:
        return "ttl"
    if cc >= 10000:
        return "data_load"
    return "normal"


def summarize(analysis):
    turns = analysis["turns"]
    out = {
        "init_total": 0,
        "data_loads_total": 0,
        "ttl_total": 0,
        "normal_total": 0,
        "ttl_count": 0,
        "top_spikes": [],
    }
    prev_cr = 0
    for t in turns:
        kind = _classify_turn(t, prev_cr)
        t["kind"] = kind
        if kind == "init":
            out["init_total"] += t["cc"]
        elif kind == "ttl":
            out["ttl_total"] += t["cc"]
            out["ttl_count"] += 1
        elif kind == "data_load":
            out["data_loads_total"] += t["cc"]
        else:
            out["normal_total"] += t["cc"]
        prev_cr = t["cache_read"]

    out["top_spikes"] = sorted(turns, key=lambda t: t["cc"], reverse=True)[:3]
    return out


# keep in sync with statusline.fmt_k
def _fmt_k(n):
    if n < 1000:
        return str(n)
    if n < 10000:
        return f"{n/1000:.1f}k"
    return f"{round(n/1000)}k"


def _note_for(turn):
    kind = turn.get("kind")
    if kind == "init":
        return "init"
    if kind == "ttl":
        return f"{RED}TTL!{RESET}"
    if turn.get("tool_name"):
        return turn["tool_name"]
    return ""


def render(analysis, summary):
    lines = []
    lines.append(f"Turns: {len(analysis['turns'])}  Total cc: {analysis['total_cc']:,}")
    lines.append("")
    lines.append(f"{'Turn':>4}  {'cc':>9}  {'cache_read':>10}  Note")
    lines.append("-" * 50)

    for t in analysis["turns"]:
        cc_str = _fmt_k(t["cc"])
        cr_str = _fmt_k(t["cache_read"])
        note = _note_for(t)
        lines.append(f"{t['index']+1:>4}  {cc_str:>9}  {cr_str:>10}  {note}")

    lines.append("")
    lines.append("Summary")
    lines.append("-------")
    total = analysis["total_cc"] or 1
    lines.append(f"  init:        {summary['init_total']:>10,}  ({summary['init_total']*100/total:5.1f}%)")
    lines.append(f"  data loads:  {summary['data_loads_total']:>10,}  ({summary['data_loads_total']*100/total:5.1f}%)")
    lines.append(f"  TTL refresh: {summary['ttl_total']:>10,}  ({summary['ttl_total']*100/total:5.1f}%)  {summary['ttl_count']} events")
    lines.append(f"  normal:      {summary['normal_total']:>10,}  ({summary['normal_total']*100/total:5.1f}%)")
    lines.append("")
    lines.append("Top spikes:")
    for sp in summary["top_spikes"]:
        note = _note_for(sp)
        lines.append(f"  Turn {sp['index']+1}: {_fmt_k(sp['cc']):>7}  {note}")
    return "\n".join(lines)


def _cwd_slug():
    """Convert current cwd to ~/.claude/projects slug format.

    Windows 'H:\\Projects\\foo' -> 'H--Projects-foo'.
    POSIX '/home/u/proj' -> '-home-u-proj'.
    """
    cwd = os.getcwd()
    s = cwd.replace("\\", "/").replace("/", "-").replace(":", "-")
    return s.lstrip("-") or s


def _find_latest_transcript():
    """Newest *.jsonl in ~/.claude/projects/<cwd-slug>/, or None."""
    home = os.environ.get("USERPROFILE") or os.environ.get("HOME")
    if not home:
        return None
    proj_dir = os.path.join(home, ".claude", "projects", _cwd_slug())
    if not os.path.isdir(proj_dir):
        return None
    candidates = [
        os.path.join(proj_dir, f)
        for f in os.listdir(proj_dir)
        if f.endswith(".jsonl")
    ]
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else _find_latest_transcript()
    if not path:
        print("No transcript path provided and no recent JSONL found.", file=sys.stderr)
        sys.exit(1)
    a = analyze(path)
    s = summarize(a)
    print(render(a, s))
