#!/usr/bin/env python3
"""Claude Code statusline: cwd, git branch, model name, context usage, token count, session time."""

import json
import sys
import os
import subprocess
from collections import deque

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Hide console window for subprocesses on Windows
_SUBPROCESS_KWARGS = {}
if sys.platform == "win32":
    _si = subprocess.STARTUPINFO()
    _si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    _si.wShowWindow = 0  # SW_HIDE
    _SUBPROCESS_KWARGS["startupinfo"] = _si


RESET  = "\033[0m"
DIM    = "\033[2m"
BLINK  = "\033[5m"


def color_for_pct(pct):
    if pct >= 80:
        return "\033[31m"        # Red (blinking applied separately)
    elif pct >= 70:
        return "\033[38;5;208m"  # Orange
    elif pct >= 60:
        return "\033[33m"        # Yellow
    else:
        return "\033[32m"        # Green


def make_bar(pct, width=10):
    filled = int(pct / 100 * width)
    filled = max(0, min(width, filled))
    return "\u25b0" * filled + "\u25b1" * (width - filled)


def get_git_branch(cwd):
    if not cwd:
        return None
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "--no-optional-locks", "symbolic-ref", "--short", "HEAD"],
            capture_output=True, text=True, timeout=2, **_SUBPROCESS_KWARGS,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        result2 = subprocess.run(
            ["git", "-C", cwd, "--no-optional-locks", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=2, **_SUBPROCESS_KWARGS,
        )
        if result2.returncode == 0:
            return result2.stdout.strip()
    except Exception:
        pass
    return None



def fmt_resets_in(value):
    """Return 'Xd Xh' or 'Xh Xm' or 'Xm' until a reset time.

    Accepts ISO timestamp string or Unix epoch seconds (int/float).
    """
    try:
        from datetime import datetime, timezone
        if isinstance(value, (int, float)):
            target = datetime.fromtimestamp(value, tz=timezone.utc)
        else:
            target = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        secs = int((target - now).total_seconds())
        if secs <= 0:
            return "now"
        d = secs // 86400
        h = (secs % 86400) // 3600
        m = (secs % 3600) // 60
        if d:
            return f"{d}d{h}h"
        elif h:
            return f"{h}h{m:02d}m"
        else:
            return f"{m}m"
    except Exception:
        return "?"


def fmt_tokens(n):
    """Format token count with commas."""
    return f"{n:,}"


def fmt_k(n):
    """Compact: '500', '1.2k', '74k'."""
    if n < 1000:
        return str(n)
    if n < 10000:
        return f"{n/1000:.1f}k"
    return f"{round(n/1000)}k"


def read_last_cc(transcript_path):
    """Return {'cc','is_first_turn','found'} from last assistant msg with cc>0.

    is_first_turn: the matching message is the file's first assistant message.
    Reads last 50 lines via deque; safe on partially-written JSONL.
    """
    result = {"cc": 0, "is_first_turn": False, "found": False}
    if not transcript_path or not os.path.isfile(transcript_path):
        return result

    total_assistant = 0
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as f:
            for ln in f:
                if '"type":"assistant"' in ln or '"type": "assistant"' in ln:
                    total_assistant += 1
    except Exception:
        return result

    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as f:
            tail = deque(f, maxlen=50)
    except Exception:
        return result

    seen_assistant_from_end = 0
    last_cc = 0
    last_index = -1
    for ln in reversed(tail):
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
        except Exception:
            continue
        if obj.get("type") != "assistant":
            continue
        seen_assistant_from_end += 1
        usage = (obj.get("message") or {}).get("usage") or {}
        cc = usage.get("cache_creation_input_tokens", 0) or 0
        if cc > 0:
            last_cc = cc
            last_index = total_assistant - seen_assistant_from_end
            break

    if last_cc > 0:
        result["cc"] = last_cc
        result["is_first_turn"] = (last_index == 0)
        result["found"] = True
    return result


def render_cc_segment(cc, is_first_turn):
    """Render colored 'cc:Nk' segment. Caller must guard cc>0."""
    label = fmt_k(cc)
    if is_first_turn:
        return f"\033[33mcc:{label} (init){RESET}"
    if cc < 2000:
        return f"{DIM}cc:{label}{RESET}"
    if cc < 10000:
        return f"\033[33mcc:{label}{RESET}"
    if cc < 30000:
        return f"\033[31m\033[1mcc:{label} ⚠{RESET}"
    return f"\033[31m\033[7mcc:{label} ‼{RESET}"


def fmt_duration(ms):
    """Format milliseconds as Xm Xs."""
    total_s = int(ms) // 1000
    m = total_s // 60
    s = total_s % 60
    if m:
        return f"{m}m{s:02d}s"
    else:
        return f"{s}s"


def main():
    try:
        raw_stdin = sys.stdin.read()
        data = json.loads(raw_stdin) if raw_stdin.strip() else {}
    except Exception:
        data = {}

    model_name = (data.get("model") or {}).get("display_name", "Claude")
    cwd = (data.get("workspace") or {}).get("current_dir", "") or data.get("cwd", "")
    cw = data.get("context_window") or {}

    # Directory display
    dir_display = cwd if cwd else "?"

    # Git branch
    branch = get_git_branch(cwd)

    # Token counts
    current      = cw.get("current_usage") or {}
    window_size  = cw.get("context_window_size") or 200000
    input_tokens = current.get("input_tokens", 0) or 0
    cache_read   = current.get("cache_read_input_tokens", 0) or 0
    total_tokens = input_tokens + cache_read

    # Percentage
    used_pct = cw.get("used_percentage")
    if used_pct is not None:
        used_pct = float(used_pct)
    else:
        used_pct = (total_tokens / window_size * 100.0) if window_size else 0.0

    used_pct = min(100.0, max(0.0, used_pct))

    col = color_for_pct(used_pct)
    bar = make_bar(used_pct)
    blink_open = BLINK if used_pct >= 80 else ""

    # Session duration from cost.total_duration_ms
    duration_ms = (data.get("cost") or {}).get("total_duration_ms", 0) or 0
    session_time = fmt_duration(duration_ms)

    transcript_path = data.get("transcript_path")
    cc_info = read_last_cc(transcript_path)
    cc_segment = render_cc_segment(cc_info["cc"], cc_info["is_first_turn"]) if cc_info["found"] else None

    # Claude usage limits — prefer stdin rate_limits, fallback to check-usage.js
    rl = data.get("rate_limits") or {}
    usage_parts = []
    if rl.get("five_hour") or rl.get("seven_day"):
        # Native rate_limits from Claude Code stdin
        fh = rl.get("five_hour") or {}
        sd = rl.get("seven_day") or {}
        s_pct = round(fh.get("used_percentage", 0) or 0, 2)
        w_pct = round(sd.get("used_percentage", 0) or 0, 2)
        s_reset = fmt_resets_in(fh["resets_at"]) if fh.get("resets_at") else "?"
        w_reset = fmt_resets_in(sd["resets_at"]) if sd.get("resets_at") else "?"
        s_col = color_for_pct(s_pct)
        w_col = color_for_pct(w_pct)
        s_bar = make_bar(s_pct)
        w_bar = make_bar(w_pct)
        usage_parts.append(
            f"{s_col}session: {s_bar} {s_pct}% {DIM}resets {s_reset}{RESET}"
        )
        usage_parts.append(
            f"{w_col}weekly: {w_bar} {w_pct}% {DIM}resets {w_reset}{RESET}"
        )

    # Assemble
    sep = f" {DIM}|{RESET} "

    parts = [
        f"{DIM}{dir_display}{RESET}",
    ]
    if branch:
        parts.append(f"{DIM}({branch}){RESET}")

    parts += [
        f"{DIM}{model_name}{RESET}",
        f"{blink_open}{col}{bar} {used_pct:.0f}%{RESET}",
        f"{col}{fmt_tokens(total_tokens)} / {fmt_tokens(window_size)}{RESET}",
        f"{DIM}{session_time}{RESET}",
    ]
    if cc_segment:
        parts.append(cc_segment)
    parts += usage_parts

    print(sep.join(parts))


if __name__ == "__main__":
    main()
