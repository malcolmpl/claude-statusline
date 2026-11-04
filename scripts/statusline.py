#!/usr/bin/env python3
"""Claude Code statusline: cwd, git branch, model name, context usage, token count, session time."""

import json
import sys
import subprocess

from transcript import latest, main_session_kind, miss_label
from render import DIM, RESET, assemble, render_gauge, render_cc_segment, render_model

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


CTX_SHOW_MAX_BELOW = 1_000_000


def ctx_used(current_usage):
    """Context tokens of the last request: uncached + cache read + cache write."""
    cu = current_usage or {}
    return sum(cu.get(k, 0) or 0 for k in
               ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))


def ctx_tail(used, window_size):
    """'used / max' for small windows; 'used' alone for 1M+ windows."""
    if window_size >= CTX_SHOW_MAX_BELOW:
        return fmt_tokens(used)
    return f"{fmt_tokens(used)} / {fmt_tokens(window_size)}"


def pick_effort(transcript_effort, data):
    """Effort from the transcript's last assistant record, else stdin `effort.level`."""
    if transcript_effort:
        return transcript_effort
    level = (data.get("effort") or {}).get("level")
    return str(level) if level else None


def main_cc_segment(turn, prompt_cache):
    """cc segment for the main session (ADR-0009): label from Claude Code's miss cause."""
    if not turn:
        return None
    return render_cc_segment(turn.cc, main_session_kind(turn), miss_label(prompt_cache, turn))


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
    total_tokens = ctx_used(current)

    # Percentage
    used_pct = cw.get("used_percentage")
    if used_pct is not None:
        used_pct = float(used_pct)
    else:
        used_pct = (total_tokens / window_size * 100.0) if window_size else 0.0

    used_pct = min(100.0, max(0.0, used_pct))

    # Session duration from cost.total_duration_ms
    duration_ms = (data.get("cost") or {}).get("total_duration_ms", 0) or 0
    session_time = fmt_duration(duration_ms)

    lt = latest(data.get("transcript_path"))
    effort = pick_effort(lt.effort, data)
    cc_segment = main_cc_segment(lt.cc_turn, data.get("prompt_cache"))

    # Claude usage limits — native rate_limits from Claude Code stdin
    rl = data.get("rate_limits") or {}
    usage_parts = []
    if rl.get("five_hour") or rl.get("seven_day"):
        fh = rl.get("five_hour") or {}
        sd = rl.get("seven_day") or {}
        s_pct = round(fh.get("used_percentage", 0) or 0, 2)
        w_pct = round(sd.get("used_percentage", 0) or 0, 2)
        s_reset = f"↻{fmt_resets_in(fh['resets_at'])}" if fh.get("resets_at") else None
        w_reset = f"↻{fmt_resets_in(sd['resets_at'])}" if sd.get("resets_at") else None
        usage_parts.append(render_gauge(s_pct, label="5h", suffix=s_reset))
        usage_parts.append(render_gauge(w_pct, label="7d", suffix=w_reset))

    # Location line
    location = [f"{DIM}{dir_display}{RESET}"]
    if branch:
        location.append(f"{DIM}({branch}){RESET}")

    # Usage line
    usage = [
        render_model(model_name, effort),
        render_gauge(used_pct, label="ctx", tail=ctx_tail(total_tokens, window_size)),
        f"{DIM}{session_time}{RESET}",
    ]
    if cc_segment:
        usage.append(cc_segment)
    usage += usage_parts

    print(assemble(location, usage))


if __name__ == "__main__":
    main()
