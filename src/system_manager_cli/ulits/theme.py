"""
theme.py - Centralized color, style, and icon constants for SysNova.

Provides graceful degradation when ANSI is not supported (e.g., plain-text
redirect, Windows CMD without colorama). Import this module everywhere instead
of hard-coding ANSI codes.

Usage:
    from system_manager_cli.ulits.theme import T, icon, colorize, supports_color
    print(T.SUCCESS + "Done!" + T.RESET)
    print(icon.OK + "  All checks passed")
    print(colorize("Warning!", T.WARNING))
"""

from __future__ import annotations

import os
import sys

# ── colorama bootstrap (Windows ANSI fix) ─────────────────────────────────────
try:
    import colorama  # type: ignore
    colorama.init(autoreset=False, strip=False)
    _COLORAMA_OK = True
except ImportError:
    _COLORAMA_OK = False


def supports_color() -> bool:
    """
    Return True when the current terminal supports ANSI escape codes.

    Checks:
    - Explicit NO_COLOR / TERM=dumb env vars (standard CLI convention)
    - Whether stdout is a real TTY
    - colorama availability on Windows
    """
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    if not hasattr(sys.stdout, "isatty"):
        return False
    if not sys.stdout.isatty():
        # Allow color when running under pytest's capture (–s) or CI that sets
        # FORCE_COLOR.
        if not os.environ.get("FORCE_COLOR"):
            return False
    if sys.platform == "win32" and not _COLORAMA_OK:
        return False
    return True


_USE_COLOR = supports_color()


def _ansi(code: str) -> str:
    """Return the ANSI escape sequence if color is supported, else empty string."""
    return f"\033[{code}m" if _USE_COLOR else ""


# ─────────────────────────────────────────────────────────────────────────────
# T  — style tokens
# ─────────────────────────────────────────────────────────────────────────────

class _Theme:
    """Namespace of ANSI style tokens.  All values degrade to '' if no color."""

    # Reset
    RESET   = _ansi("0")

    # Font weight / decoration
    BOLD    = _ansi("1")
    DIM     = _ansi("2")
    ITALIC  = _ansi("3")
    UNDER   = _ansi("4")

    # Semantic colors (foreground)
    PRIMARY  = _ansi("96")   # Cyan  — headers, selections, borders
    SUCCESS  = _ansi("92")   # Green — completed, healthy
    WARNING  = _ansi("93")   # Yellow — warnings
    ERROR    = _ansi("91")   # Red — failures
    CRITICAL = _ansi("1;91") # Bold Red — critical events
    DIM_TEXT = _ansi("2")    # Dim — secondary, timestamps, hints
    ACCENT   = _ansi("95")   # Magenta — AI features, special
    BLUE     = _ansi("94")   # Blue — info, live monitoring
    WHITE    = _ansi("97")   # Bright white — emphasis
    ORANGE   = _ansi("33")   # Orange / dark yellow — medium severity

    # Compound shortcuts
    HEADER   = _ansi("1;96") # Bold Cyan
    LABEL    = _ansi("1")    # Bold
    HINT     = _ansi("2")    # Dim

    # Background (used sparingly)
    BG_RED   = _ansi("41")
    BG_GREEN = _ansi("42")

    def wrap(self, text: str, *codes: str) -> str:
        """Wrap text with one or more style tokens, auto-reset at end."""
        prefix = "".join(codes)
        return f"{prefix}{text}{self.RESET}"


T = _Theme()


# ─────────────────────────────────────────────────────────────────────────────
# icon  — reusable status / decoration symbols
# ─────────────────────────────────────────────────────────────────────────────

class _Icons:
    """Unicode status icons used across all screens."""

    # Status indicators
    OK       = T.SUCCESS + "✔" + T.RESET
    FAIL     = T.ERROR   + "✖" + T.RESET
    WARN     = T.WARNING + "⚠" + T.RESET
    INFO     = T.BLUE    + "ℹ" + T.RESET
    RUN      = T.SUCCESS + "●" + T.RESET
    IDLE     = T.WARNING + "◉" + T.RESET
    SPIN     = T.PRIMARY + "⟳" + T.RESET
    FAST     = T.WHITE   + "⚡" + T.RESET
    AUTH     = T.PRIMARY + "🔐" + T.RESET
    AI_ICON  = T.ACCENT  + "✦" + T.RESET

    # Severity badges (returns colored text)
    @staticmethod
    def severity(level: str) -> str:
        level = level.lower()
        mapping = {
            "critical": T.CRITICAL + "🔴 CRITICAL" + T.RESET,
            "high":     T.ORANGE   + "🟠 HIGH    " + T.RESET,
            "medium":   T.WARNING  + "🟡 MEDIUM  " + T.RESET,
            "low":      T.SUCCESS  + "🟢 LOW     " + T.RESET,
            "none":     T.SUCCESS  + "✅ NONE    " + T.RESET,
        }
        return mapping.get(level, T.BLUE + level.upper() + T.RESET)

    # Job status dots
    @staticmethod
    def job_status(status: str) -> str:
        mapping = {
            "running":   T.SUCCESS + "● RUNNING " + T.RESET,
            "stopped":   T.WARNING + "◉ STOPPED " + T.RESET,
            "crashed":   T.ERROR   + "✖ CRASHED " + T.RESET,
            "completed": T.PRIMARY + "✔ DONE    " + T.RESET,
        }
        return mapping.get(status, status)


icon = _Icons()


# ─────────────────────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────────────────────

def colorize(text: str, *style_codes: str) -> str:
    """
    Apply one or more style tokens to *text* and auto-reset.

    Example:
        colorize("Hello", T.BOLD, T.PRIMARY)
    """
    if not style_codes or not _USE_COLOR:
        return text
    return "".join(style_codes) + text + T.RESET


def strip_ansi(text: str) -> str:
    """Remove all ANSI escape sequences from *text* (for length calculations)."""
    import re
    return re.sub(r"\033\[[0-9;]*m", "", text)


def visible_len(text: str) -> int:
    """Return the printable length of *text*, ignoring ANSI escapes."""
    return len(strip_ansi(text))


def pad_right(text: str, width: int, char: str = " ") -> str:
    """Right-pad *text* to *width* printable characters (ANSI-aware)."""
    vl = visible_len(text)
    if vl >= width:
        return text
    return text + char * (width - vl)


def truncate(text: str, max_len: int, ellipsis: str = "…") -> str:
    """Truncate visible text to *max_len* characters."""
    plain = strip_ansi(text)
    if len(plain) <= max_len:
        return text
    return plain[: max_len - len(ellipsis)] + ellipsis
