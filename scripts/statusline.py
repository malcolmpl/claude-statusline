#!/usr/bin/env python3
"""Claude Code statusline: cwd, git branch, model name, context usage, token count, session time."""

import json
import sys
import os
import subprocess

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

    # Claude usage limits — prefer stdin rate_limits, fallback to check-usage.js
    rl = data.get("rate_limits") or {}
    usage_parts = []
    if rl.get("five_hour") or rl.get("seven_day"):
        # Native rate_limits from Claude Code stdin
        fh = rl.get("five_hour") or {}
        sd = rl.get("seven_day") or {}
        s_pct = fh.get("used_percentage", 0) or 0
        w_pct = sd.get("used_percentage", 0) or 0
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
    parts += usage_parts

    print(sep.join(parts))


if __name__ == "__main__":
    main()
