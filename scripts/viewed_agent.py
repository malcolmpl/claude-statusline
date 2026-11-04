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

# Context window per model id (date suffix stripped). Unknown → None (count only).
CONTEXT_WINDOWS = {
    "claude-fable-5-1": 1_000_000,
    "claude-fable-5": 1_000_000,
    "claude-opus-5-5": 1_000_000,
    "claude-opus-5": 1_000_000,
    "claude-opus-4-8": 1_000_000,
    "claude-opus-4-7": 1_000_000,
    "claude-opus-4-6": 1_000_000,
    "claude-sonnet-5-5": 1_000_000,
    "claude-sonnet-5": 1_000_000,
    "claude-sonnet-4-6": 1_000_000,
    "claude-haiku-5-5": 1_000_000,
    "claude-haiku-4-5": 200_000,
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


def context_window(model_id) -> Optional[int]:
    if not model_id:
        return None
    return CONTEXT_WINDOWS.get(_DATE_SUFFIX.sub("", model_id))
