"""Menu display helpers — Phase 2 redesign.

Preserves backward-compatible display_main_menu() / display_login_menu()
while adding the new styled versions used by main.py and CLIManager.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

# ── Phase-1 UI imports (graceful fallback) ────────────────────────────────────
try:
    from system_manager_cli.ulits.theme import T, colorize, icon
    from system_manager_cli.ulits.screen import (
        box_top, box_bottom, box_row, box_divider,
        section, command_bar, term_width,
    )
    _HAS_THEME = True
except ImportError:
    _HAS_THEME = False

    class _T:
        RESET = BOLD = DIM = PRIMARY = SUCCESS = WARNING = ERROR = ""
        HEADER = WHITE = ACCENT = BLUE = ORANGE = CRITICAL = DIM_TEXT = ""
    T = _T()

    def colorize(text: str, *_: str) -> str:  # type: ignore[misc]
        return text

    class _Icon:
        OK = "✔"
        FAIL = "✖"
        WARN = "⚠"
        INFO = "ℹ"
        RUN = "●"
        IDLE = "◉"
    icon = _Icon()

    def box_top(width: int = 0, color: str = "") -> str:
        return "=" * (width or 60)

    def box_bottom(width: int = 0, color: str = "") -> str:
        return "=" * (width or 60)

    def box_row(text: str, width: int = 0, padding: int = 2, color: str = "") -> str:
        return f"  {text}"

    def box_divider(width: int = 0) -> str:
        return "=" * (width or 60)

    def section(label: str = "", width: int = 0, color: str = "") -> str:
        return f"── {label} " + "─" * max(0, (width or 60) - len(label) - 4)

    def command_bar(hints: Any = None) -> None:
        print("─" * 60)

    def term_width() -> int:
        return 60


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _live_cpu_ram() -> tuple[str, str]:
    """Return quick CPU% and RAM% strings (best effort, non-blocking)."""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0)
        ram = psutil.virtual_memory().percent
        cpu_color = T.ERROR if cpu >= 90 else T.WARNING if cpu >= 75 else T.SUCCESS
        ram_color = T.ERROR if ram >= 90 else T.WARNING if ram >= 75 else T.SUCCESS
        return (
            colorize(f"{cpu:.0f}%", cpu_color),
            colorize(f"{ram:.0f}%", ram_color),
        )
    except Exception:
        return colorize("–", T.DIM), colorize("–", T.DIM)


def _active_bg_jobs() -> int:
    """Return count of running background log analysis jobs."""
    try:
        import json
        from pathlib import Path
        from system_manager_cli.config.config import Config
        reg = Path(Config.DATA_DIR) / "background_jobs.json"
        if not reg.exists():
            return 0
        data = json.loads(reg.read_text(encoding="utf-8"))
        return sum(1 for j in data.get("jobs", []) if j.get("status") == "running")
    except Exception:
        return 0


def _active_tasks() -> int:
    """Return count of ACTIVE scheduled tasks."""
    try:
        from system_manager_cli.core.task_scheduler import TaskScheduler
        return len(TaskScheduler().get_all_tasks())
    except Exception:
        return 0


def _backend_indicator() -> str:
    try:
        from system_manager_cli.core.backend_client import _load_token
        if _load_token():
            return colorize("● Live", T.SUCCESS)
    except Exception:
        pass
    return colorize("◉ Local", T.DIM)


# ─────────────────────────────────────────────────────────────────────────────
# MenuDisplay
# ─────────────────────────────────────────────────────────────────────────────

class MenuDisplay:
    """Styled menu renderer.  All display_*() methods return the user's choice."""

    # ── Login Screen ──────────────────────────────────────────────────

    @staticmethod
    def display_login_menu() -> str:
        w = min(term_width() - 2, 64)
        print()
        print(colorize(box_top(w), T.PRIMARY))
        print(colorize(box_row("  ⚡ SYSNOVA", w, padding=2), T.PRIMARY))
        print(colorize(box_row("     Intelligent System Management Platform", w, padding=2), T.DIM))
        print(colorize(box_bottom(w), T.PRIMARY))

        print()
        print(colorize(section("LOGIN OPTIONS", w - 4), T.DIM))
        print()
        print(f"  {colorize('[1]', T.PRIMARY)}  Login")
        print(f"  {colorize('[2]', T.PRIMARY)}  Register")
        print(f"  {colorize('[3]', T.PRIMARY)}  Verify Email")
        print(f"  {colorize('[0]', T.DIM)}  Exit")
        print()
        print(colorize("─" * (w - 2), T.DIM))

        return input(f"  {colorize('>', T.PRIMARY)} ").strip()

    # ── Main Menu ─────────────────────────────────────────────────────

    @staticmethod
    def display_main_menu(username: str = "") -> str:
        w = min(term_width() - 2, 66)

        # ── Status bar ─────────────────────────────────────────────────
        cpu_s, ram_s = _live_cpu_ram()
        be_s = _backend_indicator()
        user_s = colorize(username, T.WHITE) if username else colorize("guest", T.DIM)
        ts_s = colorize(_ts(), T.DIM)

        status_inner = (
            f"  ⚡ {colorize('SysNova', T.HEADER)}"
            f"  {colorize('│', T.DIM)}  {user_s}"
            f"  {colorize('│', T.DIM)}  {ts_s}"
            f"  {colorize('│', T.DIM)}  {be_s}"
        )

        print()
        print(colorize(box_top(w), T.PRIMARY))
        print(colorize("║", T.PRIMARY) + status_inner + colorize("║", T.PRIMARY))
        print(colorize(box_divider(w), T.DIM))
        print(colorize(box_row(colorize("  MAIN MENU", T.BOLD + T.WHITE), w), T.PRIMARY))
        print(colorize(box_bottom(w), T.PRIMARY))

        # ── Menu items ─────────────────────────────────────────────────
        jobs = _active_bg_jobs()
        tasks = _active_tasks()

        jobs_hint = (
            colorize(f"  {jobs} job(s) running  ●", T.SUCCESS)
            if jobs else colorize("  Ready", T.DIM)
        )
        tasks_hint = (
            colorize(f"  {tasks} active", T.SUCCESS if tasks else T.DIM)
            if tasks else colorize("  No tasks", T.DIM)
        )

        inner_w = w - 4  # "  │ … │"

        def _item(key: str, emoji: str, label: str, hint: str = "") -> None:
            k = colorize(f"[{key}]", T.PRIMARY)
            lb = colorize(label, T.WHITE)
            ht = colorize(hint, T.DIM) if hint else ""
            print(f"  {k}  {emoji}  {lb:<28}{ht}")

        print()
        print(colorize("  ── SYSTEM ─────────────────────────────────────────", T.DIM))
        _item("1", "❤ ", "Health Monitor", f"  CPU {cpu_s}  RAM {ram_s}")
        _item("2", "🗂", "File Organizer", "  Ready")
        print()
        print(colorize("  ── ANALYSIS ───────────────────────────────────────", T.DIM))
        _item("3", "📊", "Logs Analysis", jobs_hint)
        print()
        print(colorize("  ── DATA ────────────────────────────────────────────", T.DIM))
        _item("4", "💾", "Backup System", "")
        _item("5", "⏰", "Schedule Tasks", tasks_hint)
        print()
        print(colorize("  ── CONFIG ──────────────────────────────────────────", T.DIM))
        _item("6", "⚙ ", "Settings", "")
        _item("7", "⏻ ", "Logout", "")
        _item("0", "✖ ", "Exit", "")
        print()

        command_bar(["Type number or command", "[?] help", "[q] quit"])
        return input(f"  {colorize('>', T.PRIMARY)} ").strip()

    # ── Verify Email Menu ─────────────────────────────────────────────

    @staticmethod
    def display_verify_menu() -> str:
        w = min(term_width() - 2, 50)
        print()
        print(colorize(box_top(w), T.PRIMARY))
        print(colorize(box_row(colorize("  AUTHENTICATION", T.BOLD + T.WHITE), w), T.PRIMARY))
        print(colorize(box_bottom(w), T.PRIMARY))
        print()
        print(f"  {colorize('[1]', T.PRIMARY)}  Verify email")
        print(f"  {colorize('[0]', T.DIM)}  Back")
        print()
        return input(f"  {colorize('>', T.PRIMARY)} ").strip()

    # ── Post-Login Quick Status ───────────────────────────────────────

    @staticmethod
    def show_login_success(username: str) -> None:
        cpu_s, ram_s = _live_cpu_ram()
        tasks = _active_tasks()
        print()
        print(
            f"  {colorize('✔', T.SUCCESS)}  {colorize(f'Welcome back, {username}!', T.BOLD)}"
        )
        print()
        print(colorize("  ── Quick Status ──────────────────────────────────────", T.DIM))
        print(f"  CPU {cpu_s}  │  RAM {ram_s}  │  {tasks} task(s) active")
        print(colorize("  ──────────────────────────────────────────────────────", T.DIM))
        input(f"\n  {colorize('Press Enter to continue...', T.DIM)}")
