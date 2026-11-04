"""Read the Viewed agent state file written by the plugin's mod (ADR-0008).

The mod resolves Claude Code's subagent path layout and writes
`viewed-agent-<session_id>.json`; this module only reads it (ADR-0001: we
receive a path). Any doubt falls back to the main session (returns None).
"""

import json
import os
import re
from dataclasses import dataclass
from typing import Mapping, Optional


STATE_DIR_ENV = "CLAUDE_STATUSLINE_STATE_DIR"

_MODEL_ID = re.compile(r"^claude-([a-z]+)-(\d+)-(\d{1,2})(?:-\d{8})?$")
_DATE_SUFFIX = re.compile(r"-\d{8}$")
_WINDOW_ID = re.compile(r"^claude-([a-z]+)-(\d+)(?:-(\d{1,2}))?$")
_1M_SUFFIX = "[1m]"

DISABLE_1M_ENV = "CLAUDE_CODE_DISABLE_1M_CONTEXT"
WINDOW_200K = 200_000
WINDOW_1M = 1_000_000
WINDOW_STEPS = (WINDOW_200K, WINDOW_1M)

# Lowest version per family that runs the 1M window natively; older ones run
# 200K unless `[1m]` is selected (code.claude.com/docs/en/model-config).
_NATIVE_1M_FROM = {
    "fable": (5, 0),
    "mythos": (5, 0),
    "opus": (4, 7),
    "sonnet": (5, 0),
    "haiku": (5, 5),
}


@dataclass
class ViewedAgent:
    agent_id: str
    transcript_path: str
    agent_type: Optional[str]
    model: Optional[str]   # meta.json alias (e.g. "sonnet"); transcript wins
    effort: Optional[str]  # meta.json effort; transcript record wins


def state_dir(env: Mapping[str, str] = os.environ) -> str:
    """`$CLAUDE_STATUSLINE_STATE_DIR`, else `~/.claude/claude-statusline`."""
    override = env.get(STATE_DIR_ENV)
    if override:
        return override
    return os.path.join(os.path.expanduser("~"), ".claude", "claude-statusline")


def _str(v):
    return str(v) if v not in (None, "") else None


def read_state(session_id, directory) -> Optional[ViewedAgent]:
    """The subagent in view, or None for main / missing / unreadable / stale.

    Stale = the state names a subagent whose transcript no longer exists.
    File age is not staleness: the mod writes only on a view switch.
    """
    if not session_id or not directory:
        return None
    path = os.path.join(directory, f"viewed-agent-{session_id}.json")
    try:
        with open(path, encoding="utf-8") as f:
            obj = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(obj, dict):
        return None
    agent_id = _str(obj.get("agentId"))
    tpath = _str(obj.get("transcriptPath"))
    if not agent_id or not tpath or not os.path.isfile(tpath):
        return None
    return ViewedAgent(
        agent_id=agent_id,
        transcript_path=tpath,
        agent_type=_str(obj.get("agentType")),
        model=_str(obj.get("model")),
        effort=_str(obj.get("effort")),
    )


def model_name(model_id) -> Optional[str]:
    """`claude-<family>-<maj>-<min>[-date]` → `Family maj.min`; raw id otherwise."""
    if not model_id:
        return None
    m = _MODEL_ID.match(model_id)
    if not m:
        return model_id
    family, major, minor = m.groups()
    return f"{family.capitalize()} {major}.{minor}"


def _base_id(model_id):
    """Model id without `[1m]` and date suffix; (base, has_1m_suffix)."""
    mid = str(model_id).strip().lower()
    has_1m = mid.endswith(_1M_SUFFIX)
    if has_1m:
        mid = mid[: -len(_1M_SUFFIX)]
    return _DATE_SUFFIX.sub("", mid), has_1m


def _native_window(base):
    m = _WINDOW_ID.match(base)
    if not m or m.group(1) not in _NATIVE_1M_FROM:
        return None
    version = (int(m.group(2)), int(m.group(3) or 0))
    return WINDOW_1M if version >= _NATIVE_1M_FROM[m.group(1)] else WINDOW_200K


def default_window(model_id, env: Mapping[str, str] = os.environ) -> Optional[int]:
    """Documented window of a model in Claude Code; None if unknown."""
    if not model_id:
        return None
    base, has_1m = _base_id(model_id)
    window = _native_window(base)
    if window is None:
        return None
    if env.get(DISABLE_1M_ENV) not in (None, "", "0"):
        return WINDOW_200K
    return WINDOW_1M if has_1m else window


def subagent_window(model_id, used, main_model_id=None, main_window=None,
                    env: Mapping[str, str] = os.environ) -> Optional[int]:
    """A subagent's window is sized by its own model (docs: sub-agents).

    Same model as main → main's stdin window (covers `[1m]` and 1M-off).
    Else the model's default, capped at 200K when main shows 1M is off
    (a native-1M main model running at 200K). Stepped up if `used` exceeds it.
    """
    if not model_id or default_window(model_id, env) is None:
        return None
    main_base = _base_id(main_model_id)[0] if main_model_id else None
    if main_window and main_base == _base_id(model_id)[0]:
        window = int(main_window)
    else:
        window = default_window(model_id, env)
        main_native = _native_window(main_base) if main_base else None
        if main_window and main_native == WINDOW_1M and int(main_window) < WINDOW_1M:
            window = min(window, WINDOW_200K)
    for step in WINDOW_STEPS:
        if used > window and step > window:
            window = step
    return window
