"""ANSI palette, percentage gauge, cc-segment renderer, and line assembly.

Presentation primitives shared by statusline.py and cache_stats.py.
Imports Kind from transcript (one-way: domain knows nothing about rendering).
"""

from transcript import Kind, fmt_k


RESET   = "\033[0m"
DIM     = "\033[2m"
BLINK   = "\033[5m"
YELLOW  = "\033[33m"
RED     = "\033[31m"
BOLD    = "\033[1m"
INVERSE = "\033[7m"


BLINK_THRESHOLD = 80


def _color_for_pct(pct):
    if pct >= 80:
        return "\033[31m"        # Red (blinking applied separately)
    elif pct >= 70:
        return "\033[38;5;208m"  # Orange
    elif pct >= 60:
        return "\033[33m"        # Yellow
    else:
        return "\033[32m"        # Green


def _make_bar(pct, width=10):
    filled = int(pct / 100 * width)
    filled = max(0, min(width, filled))
    return "▰" * filled + "▱" * (width - filled)


def render_gauge(pct, *, label=None, suffix=None, tail=None):
    col = _color_for_pct(pct)
    bar = _make_bar(pct)
    blink = BLINK if pct >= BLINK_THRESHOLD else ""
    head = f"{DIM}{label}:{RESET} " if label else ""
    tail_part = f" {col}{tail}{RESET}" if tail else ""
    suff_part = f" {DIM}{suffix}{RESET}" if suffix else ""
    return f"{head}{blink}{col}{bar} {pct:.0f}%{RESET}{tail_part}{suff_part}"


def render_model(model, effort, prefix=None):
    """Model name, with Effort appended when known (never guessed).

    `prefix` (e.g. '↳Explore') marks a Viewed subagent.
    """
    parts = [p for p in (prefix, model, effort) if p]
    return f"{DIM}{' '.join(parts)}{RESET}"


def render_count(text, *, label=None):
    """Gauge stand-in when no max is known: label + count, no bar or %."""
    head = f"{DIM}{label}:{RESET} " if label else ""
    return f"{head}{text}"


def render_cc_segment(cc, kind, miss=None):
    """Render colored 'cc:Nk' segment. Caller must guard cc>0.

    `miss` is a cache-miss label ('TTL!', 'rebuild!', 'srv?'); it wins over kind.
    """
    label = fmt_k(cc)
    if miss is None and kind == Kind.TTL_REFRESH:
        miss = "TTL!"
    if miss:
        return f"{RED}{BOLD}cc:{label} ({miss}){RESET}"
    if kind == Kind.FIRST_TURN:
        return f"{DIM}cc:{label}{RESET}"
    # DATA_LOAD or NORMAL — size-based palette
    if cc < 2000:
        return f"{DIM}cc:{label}{RESET}"
    if cc < 10000:
        return f"{YELLOW}cc:{label}{RESET}"
    if cc < 30000:
        return f"{RED}{BOLD}cc:{label} ⚠{RESET}"
    return f"{RED}{INVERSE}cc:{label} ‼{RESET}"


SEP = f" {DIM}|{RESET} "


def assemble(location_parts, usage_parts):
    """Join rendered segments into Location line + Usage line (see CONTEXT.md)."""
    return f"{SEP.join(location_parts)}\n{SEP.join(usage_parts)}"
