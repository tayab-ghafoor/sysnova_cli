"""
screen.py — Screen layout helpers: status bar, box drawing, section dividers,
            progress bars, confirmation dialogs, and error panels.

All rendering is done with plain sys.stdout.write() so it works on every
terminal.  Uses theme.py for colours and adapts gracefully when ANSI is off.

Key components
──────────────
  StatusBar   — persistent top-of-screen header bar
  box_*()     — top / row / bottom / divider helpers for bordered panels
  progress_bar() — inline horizontal ASCII progress bar
  confirm()   — styled yes/no dialog
  error_panel() — bordered error display
  section()   — section divider line
  clear()     — cross-platform screen clear
"""

from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime
from typing import Sequence

from .theme import T, colorize, strip_ansi, visible_len

# ─────────────────────────────────────────────────────────────────────────────
# Terminal width helper
# ─────────────────────────────────────────────────────────────────────────────

def term_width() -> int:
    """Return current terminal width (columns).  Default 80."""
    try:
        return shutil.get_terminal_size((80, 24)).columns
    except Exception:
        return 80


def clear() -> None:
    """Cross-platform screen clear."""
    os.system("cls" if sys.platform == "win32" else "clear")


# ─────────────────────────────────────────────────────────────────────────────
# StatusBar
# ─────────────────────────────────────────────────────────────────────────────

class StatusBar:
    """
    Renders a top-of-screen status bar:

        ╔════════════════════════════════════════════════════════╗
        ║  ⚡ SysManager CLI  │  john_doe  │  v1.0  │  14:32:05  ║
        ╚════════════════════════════════════════════════════════╝

    Usage:
        bar = StatusBar(username="john_doe", version="1.0.0")
        bar.render()            # prints bar to stdout
        bar.render(clear=True)  # clears screen first
    """

    VERSION = "1.0.0"

    def __init__(
        self,
        username: str = "",
        version:  str = "",
        backend_ok: bool | None = None,
    ) -> None:
        self.username   = username
        self.version    = version or self.VERSION
        self.backend_ok = backend_ok

    # ── Public ────────────────────────────────────────────────────────

    def render(self, do_clear: bool = False) -> None:
        """Print the status bar.  Optionally clear the screen first."""
        if do_clear:
            clear()
        w = term_width()
        print(self._build(w))

    def update(self, username: str = "", backend_ok: bool | None = None) -> None:
        """Update mutable fields without re-rendering."""
        if username:
            self.username = username
        if backend_ok is not None:
            self.backend_ok = backend_ok

    # ── Internal ──────────────────────────────────────────────────────

    def _backend_indicator(self) -> str:
        if self.backend_ok is None:
            return ""
        if self.backend_ok:
            return colorize("● Live", T.SUCCESS)
        return colorize("◉ Offline", T.WARNING)

    def _build(self, w: int) -> str:
        app    = colorize("⚡ SysManager CLI", T.HEADER)
        user   = colorize(self.username, T.WHITE) if self.username else ""
        ver    = colorize(f"v{self.version}", T.DIM)
        ts     = colorize(datetime.now().strftime("%H:%M:%S"), T.DIM)
        be     = self._backend_indicator()

        parts  = [app]
        if user:
            parts.append(user)
        parts.append(ver)
        parts.append(ts)
        if be:
            parts.append(be)

        sep    = colorize("  │  ", T.DIM)
        inner  = sep.join(parts)
        inner_plain = strip_ansi(inner)

        # Build bordered line; pad to w-4 to leave space for ║  … ║
        box_w  = w - 2                                   # ╔ … ╗ width
        inner_w = box_w - 4                              # ║  … ║ padding
        content_plain_len = len(inner_plain)
        padding = max(0, inner_w - content_plain_len)

        top = "╔" + "═" * box_w + "╗"
        mid = "║  " + inner + " " * padding + "  ║"
        bot = "╚" + "═" * box_w + "╝"

        return f"{top}\n{mid}\n{bot}"


# ─────────────────────────────────────────────────────────────────────────────
# Box drawing primitives
# ─────────────────────────────────────────────────────────────────────────────

def box_top(width: int = 0, color: str = "") -> str:
    """Return the top border of a box:  ╔══════╗"""
    w = width or (term_width() - 2)
    line = "╔" + "═" * w + "╗"
    return colorize(line, color) if color else line


def box_bottom(width: int = 0, color: str = "") -> str:
    """Return the bottom border of a box:  ╚══════╝"""
    w = width or (term_width() - 2)
    line = "╚" + "═" * w + "╝"
    return colorize(line, color) if color else line


def box_row(text: str, width: int = 0, padding: int = 2, color: str = "") -> str:
    """
    Return a single box row:  ║  text…  ║

    *text* may contain ANSI codes; visible length is used for padding.
    """
    w = width or (term_width() - 2)
    inner = w - padding * 2
    text_plain_len = visible_len(text)
    space = max(0, inner - text_plain_len)
    pad   = " " * padding
    line  = "║" + pad + text + " " * space + pad + "║"
    return colorize(line, color) if color else line


def box_divider(width: int = 0) -> str:
    """Return a mid-box divider:  ╠══════╣"""
    w = width or (term_width() - 2)
    return "╠" + "═" * w + "╣"


def section(label: str = "", width: int = 0, color: str = T.DIM) -> str:
    """
    Return a section divider:  ── Label ─────────────────────

    If *label* is empty, returns a plain divider line.
    """
    w = width or (term_width() - 4)
    if label:
        dash_left  = "── "
        dash_right = " " + "─" * max(0, w - len(dash_left) - len(label) - 1)
        line = dash_left + label + dash_right
    else:
        line = "─" * w
    return colorize(line, color)


def print_box(title: str, lines: Sequence[str], width: int = 0) -> None:
    """
    Print a complete bordered box with a title row and content lines.

    Example:
        print_box("HEALTH MONITOR", ["CPU  42%", "RAM  61%"])
    """
    w = width or (term_width() - 2)
    print(box_top(w))
    print(box_row(colorize(title, T.HEADER), w))
    print(box_bottom(w))
    for line in lines:
        print(f"  {line}")


# ─────────────────────────────────────────────────────────────────────────────
# Progress bars
# ─────────────────────────────────────────────────────────────────────────────

def progress_bar(
    value:    float,
    maximum:  float = 100.0,
    width:    int   = 20,
    label:    str   = "",
    unit:     str   = "%",
    *,
    threshold_warn: float = 75.0,
    threshold_crit: float = 90.0,
) -> str:
    """
    Return a coloured inline progress bar string.

    Example:
        print(progress_bar(42.3, label="CPU"))
        # CPU  ████████░░░░░░░░░░░░  42.3%
    """
    pct = (value / maximum * 100) if maximum else 0.0
    pct = max(0.0, min(pct, 100.0))

    filled  = int(pct / 100 * width)
    bar     = "█" * filled + "░" * (width - filled)

    if pct >= threshold_crit:
        color = T.ERROR
        icon  = "🔴"
    elif pct >= threshold_warn:
        color = T.WARNING
        icon  = "🟡"
    else:
        color = T.SUCCESS
        icon  = "🟢"

    colored_bar = colorize(bar, color)
    pct_str     = colorize(f"{pct:.1f}{unit}", T.BOLD)

    if label:
        lbl = colorize(label, T.DIM)
        return f"{icon} {lbl:<14} {colored_bar}  {pct_str}"
    return f"{colored_bar}  {pct_str}"


# ─────────────────────────────────────────────────────────────────────────────
# Confirmation dialog
# ─────────────────────────────────────────────────────────────────────────────

def confirm(
    question:    str,
    detail:      str = "",
    yes_label:   str = "Yes",
    no_label:    str = "No",
    default:     str = "",           # "y" | "n" | ""
    width:       int = 0,
) -> bool:
    """
    Display a styled yes/no confirmation box and return True for yes.

    Example:
        if confirm("Compress backup to ZIP?",
                   detail="Reduces size by ~40% but takes longer."):
            do_zip()
    """
    w = width or min(60, term_width() - 4)
    inner = w - 4

    print()
    print("  ┌" + "─" * (w - 2) + "┐")

    # Question line
    q = colorize(question, T.BOLD)
    q_plain = question
    pad = max(0, inner - len(q_plain))
    print(f"  │  {q}{' ' * pad}  │")

    if detail:
        print("  │" + " " * (w - 2) + "│")
        for segment in _wrap(detail, inner):
            seg_pad = max(0, inner - len(segment))
            print(f"  │  {colorize(segment, T.DIM)}{' ' * seg_pad}  │")

    print("  │" + " " * (w - 2) + "│")

    y_lbl = colorize(f"[Y] {yes_label}", T.SUCCESS)
    n_lbl = colorize(f"[N] {no_label}", T.ERROR)
    btn   = f"{y_lbl}    {n_lbl}"
    btn_plain_len = len(yes_label) + len(no_label) + 10
    btn_pad = max(0, inner - btn_plain_len)
    print(f"  │  {btn}{' ' * btn_pad}  │")

    print("  └" + "─" * (w - 2) + "┘")

    hint = ""
    if default == "y":
        hint = " (default: Yes)"
    elif default == "n":
        hint = " (default: No)"

    while True:
        raw = input(f"\n  {colorize('> ', T.PRIMARY)}").strip().lower()
        if not raw and default:
            return default == "y"
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print(f"  {colorize('Please enter Y or N.', T.WARNING)}")


# ─────────────────────────────────────────────────────────────────────────────
# Error panel
# ─────────────────────────────────────────────────────────────────────────────

def error_panel(
    title:   str,
    message: str,
    hints:   Sequence[str] | None = None,
    actions: str = "[R] Retry   [0] Cancel",
    width:   int = 0,
) -> None:
    """
    Display a styled error panel.

    Example:
        error_panel(
            "PATH NOT FOUND",
            "/invalid/path does not exist.",
            hints=["Check for typos", "Ensure the drive is mounted"],
        )
    """
    w = width or min(64, term_width() - 4)
    inner = w - 4

    print()
    print("  ┌" + "─" * (w - 2) + "┐")
    title_str = colorize(f"  ✖  {title}", T.ERROR + T.BOLD)
    title_pad = max(0, inner - len(title) - 5)
    print(f"  │{title_str}{' ' * title_pad}  │")
    print("  │" + " " * (w - 2) + "│")

    for seg in _wrap(message, inner):
        seg_pad = max(0, inner - len(seg))
        print(f"  │  {seg}{' ' * seg_pad}  │")

    if hints:
        print("  │" + " " * (w - 2) + "│")
        hint_lbl = colorize("  Possible causes:", T.DIM)
        hint_pad = max(0, inner - 18)
        print(f"  │{hint_lbl}{' ' * hint_pad}  │")
        for h in hints:
            h_str = f"   • {h}"
            h_pad = max(0, inner - len(h_str))
            print(f"  │  {colorize(h_str, T.DIM)}{' ' * h_pad}  │")

    print("  │" + " " * (w - 2) + "│")
    act_pad = max(0, inner - len(actions))
    print(f"  │  {colorize(actions, T.DIM)}{' ' * act_pad}  │")
    print("  └" + "─" * (w - 2) + "┘")


# ─────────────────────────────────────────────────────────────────────────────
# Command bar (persistent footer)
# ─────────────────────────────────────────────────────────────────────────────

def command_bar(hints: Sequence[str] | None = None) -> None:
    """
    Print the command footer bar.

    Example hints: ["[1-7] Navigate", "[q] Quit", "[?] Help"]
    """
    default_hints = ["[1-7] Select", "[q] Quit", "[?] Help"]
    items = hints or default_hints
    w = term_width() - 2
    sep = colorize("  │  ", T.DIM)
    content = sep.join(colorize(h, T.DIM) for h in items)
    print(colorize("─" * w, T.DIM))
    print(f" {content}")


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def _wrap(text: str, width: int) -> list[str]:
    """Simple word-wrap for plain text (no ANSI)."""
    words   = text.split()
    lines:  list[str] = []
    current = ""
    for word in words:
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = (current + " " + word).strip()
    if current:
        lines.append(current)
    return lines or [""]


def print_divider(char: str = "─", width: int = 0) -> None:
    """Print a full-width divider line."""
    w = width or (term_width() - 2)
    print(colorize(char * w, T.DIM))


def print_kv(label: str, value: str, label_width: int = 20) -> None:
    """Print a single key: value pair with aligned columns."""
    lbl = colorize(label.ljust(label_width), T.DIM)
    print(f"  {lbl}  {value}")


def print_success(msg: str) -> None:
    print(f"  {colorize('✔', T.SUCCESS)}  {msg}")


def print_error(msg: str) -> None:
    print(f"  {colorize('✖', T.ERROR)}  {msg}")


def print_warning(msg: str) -> None:
    print(f"  {colorize('⚠', T.WARNING)}  {msg}")


def print_info(msg: str) -> None:
    print(f"  {colorize('ℹ', T.BLUE)}  {msg}")


def print_step(msg: str) -> None:
    print(f"\n  {colorize('➤', T.PRIMARY)}  {msg}")


def pause(prompt: str = "Press Enter to continue…") -> None:
    """Wait for the user to press Enter."""
    try:
        input(f"\n  {colorize(prompt, T.DIM)}")
    except (EOFError, KeyboardInterrupt):
        print()