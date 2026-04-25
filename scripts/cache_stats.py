#!/usr/bin/env python3
"""Per-turn cache_creation analysis for Claude Code session JSONL."""

import json
import os
import sys


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


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    r = analyze(path)
    print(f"turns={len(r['turns'])} total_cc={r['total_cc']}")
