#!/usr/bin/env python3
"""Claude Code statusline: cwd, git branch, model name, context usage, token count, session time."""

import json
import os
import sys
import threading
from collections import namedtuple

from transcript import latest, main_session_kind, miss_label
from render import DIM, RESET, assemble, render_count, render_gauge, render_cc_segment, render_model
import viewed_agent
import reaper

# Run deadlines (#3): a stdin pipe that is never closed, or any other hang,
# must not leave the process alive. Module-level so tests can lower them.
STDIN_TIMEOUT_S = 2.0
WATCHDOG_S = 5.0

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def _find_git_dir(cwd):
    """Git dir of the repo holding cwd: walk up to `.git`, follow a `gitdir:` file."""
    d = os.path.abspath(cwd)
    while True:
        dot_git = os.path.join(d, ".git")
        if os.path.isdir(dot_git):
            return dot_git
        if os.path.isfile(dot_git):  # worktree / submodule
            with open(dot_git, encoding="utf-8") as f:
                line = f.readline().strip()
            if not line.startswith("gitdir:"):
                return None
            return os.path.normpath(os.path.join(d, line[len("gitdir:"):].strip()))
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def get_git_branch(cwd):
    """Branch name, or short SHA on detached HEAD; read from HEAD, no `git` spawn (#5)."""
    if not cwd:
        return None
    try:
        git_dir = _find_git_dir(cwd)
        if not git_dir:
            return None
        with open(os.path.join(git_dir, "HEAD"), encoding="utf-8") as f:
            head = f.read().strip()
    except Exception:
        return None
    if head.startswith("ref:"):
        ref = head[4:].strip()
        if ref == "refs/heads/.invalid":  # reftable backend: real HEAD is not in this file
            return None
        for prefix in ("refs/heads/", "refs/remotes/", "refs/tags/", "refs/"):
            if ref.startswith(prefix):  # as `git symbolic-ref --short`
                return ref[len(prefix):]
        return ref
    if len(head) >= 7 and all(c in "0123456789abcdef" for c in head.lower()):
        return head[:7]
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


CTX_USED_ONLY_FROM = 1_000_000


def ctx_used(current_usage):
    """Context tokens of the last request: uncached + cache read + cache write."""
    cu = current_usage or {}
    return sum(cu.get(k, 0) or 0 for k in
               ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))


def ctx_tail(used, window_size):
    """'used / max' for small windows; 'used' alone for 1M+ windows."""
    if window_size >= CTX_USED_ONLY_FROM:
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


ViewSegments = namedtuple("ViewSegments", "model ctx cc")


def ctx_gauge(used, window_size, used_pct=None):
    """Context Gauge; count only when the window is unknown."""
    if not window_size:
        return render_count(fmt_tokens(used), label="ctx")
    if used_pct is None:
        used_pct = used / window_size * 100.0
    used_pct = min(100.0, max(0.0, float(used_pct)))
    return render_gauge(used_pct, label="ctx", tail=ctx_tail(used, window_size))


def subagent_segments(agent, data=None, env=None):
    """Model, ctx and cc segments of a Viewed subagent (ADR-0008).

    Effort: transcript record, else meta.json; never stdin (session-level).
    ctx window: the subagent's own model, main's stdin window when the model
    is the same (viewed_agent.subagent_window).
    cc: ADR-0002 ratio heuristic as classified (prompt_cache excludes subagents).
    """
    data = data or {}
    env = os.environ if env is None else env
    tail = latest(agent.transcript_path)
    last = tail.last_turn
    model_id = last.model if last else None
    model = viewed_agent.model_name(model_id) or agent.model or "?"
    effort = tail.effort or agent.effort
    prefix = f"↳{agent.agent_type}" if agent.agent_type else "↳agent"
    used = last.ctx_tokens if last else 0
    cc = tail.cc_turn
    return ViewSegments(
        model=render_model(model, effort, prefix=prefix),
        ctx=ctx_gauge(used, viewed_agent.subagent_window(
            model_id, used,
            (data.get("model") or {}).get("id"),
            (data.get("context_window") or {}).get("context_window_size"),
            env)),
        cc=render_cc_segment(cc.cc, cc.kind) if cc else None,
    )


def main_segments(data):
    """Model, ctx and cc segments of the main session (stdin + main transcript)."""
    model_name = (data.get("model") or {}).get("display_name", "Claude")
    cw = data.get("context_window") or {}
    window_size = cw.get("context_window_size") or 200000
    total_tokens = ctx_used(cw.get("current_usage") or {})
    tail = latest(data.get("transcript_path"))
    return ViewSegments(
        model=render_model(model_name, pick_effort(tail.effort, data)),
        ctx=ctx_gauge(total_tokens, window_size, cw.get("used_percentage")),
        cc=main_cc_segment(tail.cc_turn, data.get("prompt_cache")),
    )


def view_segments(data, state_dir=None):
    """Segments of the Viewed agent: a subagent per the mod's state file, else main."""
    if state_dir is None:
        state_dir = viewed_agent.state_dir()
    agent = viewed_agent.read_state(data.get("session_id"), state_dir)
    if agent:
        return subagent_segments(agent, data)  # main transcript not parsed (1 s refresh)
    return main_segments(data)


def start_watchdog():
    """Hard-exit (no output) wherever the run is stuck once WATCHDOG_S elapses."""
    timer = threading.Timer(WATCHDOG_S, os._exit, args=(0,))
    timer.daemon = True
    timer.start()


def read_stdin():
    """Read stdin to EOF, or hard-exit silently after STDIN_TIMEOUT_S.

    A daemon thread + join, because select/non-blocking reads do not work on
    Windows anonymous pipes. os._exit, because the blocked reader thread
    would otherwise keep the process alive.
    """
    box = []

    def reader():
        try:
            box.append(sys.stdin.read())
        except Exception:
            box.append("")

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    t.join(STDIN_TIMEOUT_S)
    if t.is_alive():
        os._exit(0)
    return box[0] if box else ""


def main():
    start_watchdog()
    try:
        raw_stdin = read_stdin()
        data = json.loads(raw_stdin) if raw_stdin.strip() else {}
    except Exception:
        data = {}

    cwd = (data.get("workspace") or {}).get("current_dir", "") or data.get("cwd", "")

    # Directory display
    dir_display = cwd if cwd else "?"

    # Git branch
    branch = get_git_branch(cwd)

    # Session duration from cost.total_duration_ms
    duration_ms = (data.get("cost") or {}).get("total_duration_ms", 0) or 0
    session_time = fmt_duration(duration_ms)

    view = view_segments(data)

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
    usage = [view.model, view.ctx, f"{DIM}{session_time}{RESET}"]
    if view.cc:
        usage.append(view.cc)
    usage += usage_parts

    print(assemble(location, usage), flush=True)
    # After the output: a rare (once per window) reap must not delay the line.
    reaper.run(os.path.abspath(__file__), viewed_agent.state_dir())


if __name__ == "__main__":
    main()
