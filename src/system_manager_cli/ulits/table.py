"""
table.py — Fast, ANSI-aware terminal table renderer.

Zero external dependencies.  Works on Windows CMD, PowerShell, and any
POSIX terminal.  Automatically adapts column widths, handles ANSI escape
sequences in cell values, and truncates cells that are too wide.

Usage:
    from system_manager_cli.ulits.table import Table
    from system_manager_cli.ulits.theme import T

    t = Table(
        headers=["ID", "Type", "Status", "Next Run"],
        col_colors=[T.DIM, T.WHITE, T.SUCCESS, T.PRIMARY],
        max_width=80,
    )
    t.add_row([1, "Backup", "ACTIVE", "14:00"])
    t.add_row([2, "Health", colorize("STOPPED", T.WARNING), "—"])
    t.print()

Output:
    ┌────┬──────────┬──────────┬──────────┐
    │ ID │ Type     │ Status   │ Next Run │
    ├────┼──────────┼──────────┼──────────┤
    │  1 │ Backup   │ ACTIVE   │ 14:00    │
    │  2 │ Health   │ STOPPED  │ —        │
    └────┴──────────┴──────────┴──────────┘
"""

from __future__ import annotations

import shutil
from typing import Any, Sequence

from .theme import T, colorize, truncate, visible_len


# ─────────────────────────────────────────────────────────────────────────────
# Table
# ─────────────────────────────────────────────────────────────────────────────

class Table:
    """
    Renders a bordered terminal table.

    Args:
        headers:    Column header labels.
        col_colors: Optional per-column ANSI style token applied to *cell values*
                    (not headers).  Must be same length as headers or shorter.
        col_align:  'left' | 'right' | 'center' per column.  Default 'left'.
        max_width:  Maximum total table width in characters.  0 = auto (terminal
                    width).  Columns are shrunk proportionally if needed.
        indent:     Leading spaces before each table line (default 2).
        min_col:    Minimum column width (default 4).
    """

    _BOX_TOP  = ("┌", "┬", "┐", "─")
    _BOX_HEAD = ("├", "┼", "┤", "─")
    _BOX_ROW  = ("│",)
    _BOX_BOT  = ("└", "┴", "┘", "─")

    def __init__(
        self,
        headers: Sequence[str],
        col_colors: Sequence[str] | None = None,
        col_align:  Sequence[str] | None = None,
        max_width:  int = 0,
        indent:     int = 2,
        min_col:    int = 4,
    ) -> None:
        self.headers    = [str(h) for h in headers]
        self.col_colors = list(col_colors or [])
        self.col_align  = list(col_align  or [])
        self.max_width  = max_width or self._term_width() - indent
        self.indent     = indent
        self.min_col    = min_col
        self.rows: list[list[str]] = []

    # ── Public API ────────────────────────────────────────────────────

    def add_row(self, row: Sequence[Any]) -> "Table":
        """Append a row.  Values are str-converted.  Returns self for chaining."""
        self.rows.append([str(v) for v in row])
        return self

    def clear(self) -> "Table":
        self.rows.clear()
        return self

    def print(self, file: Any = None) -> None:
        """Render and print the table to *file* (default stdout)."""
        import sys
        out = file or sys.stdout
        for line in self._render():
            out.write(line + "\n")
        out.flush()

    def render_str(self) -> str:
        """Return the full table as a single string."""
        return "\n".join(self._render())

    # ── Internal ──────────────────────────────────────────────────────

    @staticmethod
    def _term_width() -> int:
        try:
            return shutil.get_terminal_size((80, 24)).columns
        except Exception:
            return 80

    def _col_widths(self) -> list[int]:
        """
        Calculate optimal column widths respecting max_width.
        ANSI escapes in cell values do not count toward width.
        """
        n = len(self.headers)
        # Minimum = max(header width, longest cell value, min_col)
        widths = [max(visible_len(h), self.min_col) for h in self.headers]

        for row in self.rows:
            for i, cell in enumerate(row):
                if i < n:
                    widths[i] = max(widths[i], visible_len(cell))

        # Total width: borders + padding.  Each col uses "─" + 2 spaces padding.
        # Layout: "│ " + content + " " repeated for each col, plus outer "│"
        # total = 1 (left │) + sum(w + 2) + (n-1) (inner │) + 1 (right │) + indent
        total = 1 + sum(w + 2 for w in widths) + (n - 1) + 1 + self.indent
        excess = total - self.max_width

        if excess > 0:
            # Shrink widest columns first
            widths = self._shrink(widths, excess)

        return widths

    @staticmethod
    def _shrink(widths: list[int], excess: int) -> list[int]:
        """Distribute 'excess' character reduction across columns."""
        widths = list(widths)
        while excess > 0:
            # Find the widest column that can still shrink
            max_w = max(widths)
            idx   = widths.index(max_w)
            if widths[idx] <= 4:
                break
            widths[idx] -= 1
            excess -= 1
        return widths

    def _align_cell(self, text: str, width: int, align: str) -> str:
        """Pad/align *text* to *width* printable characters."""
        vl = visible_len(text)
        if vl >= width:
            return truncate(text, width)
        padding = width - vl
        if align == "right":
            return " " * padding + text
        if align == "center":
            left  = padding // 2
            right = padding - left
            return " " * left + text + " " * right
        return text + " " * padding   # left (default)

    def _border(self, widths: list[int], left: str, mid: str, right: str, fill: str) -> str:
        segments = [fill * (w + 2) for w in widths]
        return " " * self.indent + left + mid.join(segments) + right

    def _data_row(self, cells: list[str], widths: list[int], is_header: bool = False) -> str:
        parts = []
        for i, width in enumerate(widths):
            raw   = cells[i] if i < len(cells) else ""
            align = self.col_align[i] if i < len(self.col_align) else "left"
            if not is_header and i < len(self.col_colors) and self.col_colors[i]:
                color = self.col_colors[i]
                cell  = color + self._align_cell(raw, width, align) + T.RESET
            else:
                cell  = self._align_cell(raw, width, align)
            if is_header:
                cell = T.BOLD + cell + T.RESET
            parts.append(f" {cell} ")
        indent = " " * self.indent
        return indent + "│" + "│".join(parts) + "│"

    def _render(self) -> list[str]:
        widths = self._col_widths()
        lines: list[str] = []

        lines.append(self._border(widths, "┌", "┬", "┐", "─"))
        lines.append(self._data_row(self.headers, widths, is_header=True))
        lines.append(self._border(widths, "├", "┼", "┤", "─"))

        for row in self.rows:
            lines.append(self._data_row(row, widths, is_header=False))

        lines.append(self._border(widths, "└", "┴", "┘", "─"))
        return lines


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: key-value detail block (used in health / analysis screens)
# ─────────────────────────────────────────────────────────────────────────────

def kv_table(
    rows: Sequence[tuple[str, str]],
    label_width: int = 24,
    indent: int = 2,
) -> None:
    """
    Print a simple two-column label: value table without borders.

    Example:
        kv_table([("CPU Usage", "42%"), ("RAM", "61%")])

    Output:
      CPU Usage          42%
      RAM                61%
    """
    pad = " " * indent
    for label, value in rows:
        lbl_display = colorize(label.ljust(label_width), T.DIM)
        print(f"{pad}{lbl_display}  {value}")