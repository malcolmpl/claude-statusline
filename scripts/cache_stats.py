#!/usr/bin/env python3
"""Per-turn cache_creation analysis for Claude Code session JSONL."""

import sys

from transcript import Kind, turns, fmt_k
from render import RED, DIM, RESET


def analyze(transcript_path):
    """Return {turns: [ClassifiedTurn...], total_cc: int}."""
    ts = list(turns(transcript_path))
    return {"turns": ts, "total_cc": sum(t.cc for t in ts)}


def summarize(analysis):
    out = {
        "init_total": 0,
        "data_loads_total": 0,
        "ttl_total": 0,
        "normal_total": 0,
        "ttl_count": 0,
        "top_spikes": [],
    }
    for t in analysis["turns"]:
        if t.kind == Kind.FIRST_TURN:
            out["init_total"] += t.cc
        elif t.kind == Kind.TTL_REFRESH:
            out["ttl_total"] += t.cc
            out["ttl_count"] += 1
        elif t.kind == Kind.DATA_LOAD:
            out["data_loads_total"] += t.cc
        else:
            out["normal_total"] += t.cc
    out["top_spikes"] = sorted(
        enumerate(analysis["turns"]), key=lambda it: it[1].cc, reverse=True
    )[:3]
    return out


def _note_for(turn):
    if turn.kind == Kind.FIRST_TURN:
        return "init"
    if turn.kind == Kind.TTL_REFRESH:
        return f"{RED}TTL!{RESET}"
    if turn.tool_name:
        return turn.tool_name
    return ""


def render(analysis, summary):
    lines = []
    lines.append(f"Turns: {len(analysis['turns'])}  Total cc: {analysis['total_cc']:,}")
    lines.append("")
    lines.append(f"{'Turn':>4}  {'cc':>9}  {'cache_read':>10}  Note")
    lines.append("-" * 50)

    for i, t in enumerate(analysis["turns"]):
        lines.append(f"{i+1:>4}  {fmt_k(t.cc):>9}  {fmt_k(t.cache_read):>10}  {_note_for(t)}")

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
    for idx, sp in summary["top_spikes"]:
        lines.append(f"  Turn {idx+1}: {fmt_k(sp.cc):>7}  {_note_for(sp)}")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: cache_stats.py <transcript.jsonl>", file=sys.stderr)
        sys.exit(2)
    path = sys.argv[1]
    a = analyze(path)
    s = summarize(a)
    print(render(a, s))
