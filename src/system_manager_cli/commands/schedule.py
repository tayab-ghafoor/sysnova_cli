"""
commands/schedule.py — Direct CLI handler for: sysmanager schedule

Usage
─────
    sysmanager schedule list             # Table of all scheduled tasks
    sysmanager schedule list --json      # JSON output
    sysmanager schedule add              # Interactive wizard to create a task
    sysmanager schedule run <id>         # Execute task immediately
    sysmanager schedule remove <id>      # Delete a task
    sysmanager schedule enable  <id>     # Enable a disabled task
    sysmanager schedule disable <id>     # Disable without deleting

Exit codes
──────────
    0   success
    1   task not found / validation error
    2   argument error
    3   unexpected error
"""

from __future__ import annotations

import json
import sys
from argparse import Namespace
from datetime import datetime, timezone
from typing import Any


# ── UI helpers ────────────────────────────────────────────────────────────────

def _try_theme():
    try:
        from system_manager_cli.ulits.theme import T, colorize
        from system_manager_cli.ulits.screen import (
            box_top, box_bottom, box_row, section, term_width, command_bar,
        )
        from system_manager_cli.ulits.table import Table
        return T, colorize, box_top, box_bottom, box_row, section, term_width, command_bar, Table
    except ImportError:
        class _T:
            RESET = BOLD = DIM = PRIMARY = SUCCESS = WARNING = ERROR = ""
            HEADER = WHITE = ACCENT = ""
        T = _T()
        def colorize(t, *_): return t
        def box_top(w=0, color=""): return "=" * (w or 60)
        def box_bottom(w=0, color=""): return "=" * (w or 60)
        def box_row(t, w=0, padding=2, color=""): return f"  {t}"
        def section(label="", w=0, color=""): return f"── {label} ──"
        def term_width(): return 60
        def command_bar(hints=None): print("─" * 60)
        Table = None
        return T, colorize, box_top, box_bottom, box_row, section, term_width, command_bar, Table


def _err(msg: str) -> None:
    print(f"  [ERROR] {msg}", file=sys.stderr)


# ── Formatting helpers ─────────────────────────────────────────────────────────

def _format_next_run(iso: str | None) -> str:
    """Return a human-friendly 'next run' string."""
    if not iso:
        return "—"
    try:
        dt  = datetime.fromisoformat(iso)
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        diff = dt - now
        secs = diff.total_seconds()
        if secs < 0:
            return "overdue"
        if secs < 60:
            return f"in {int(secs)}s"
        if secs < 3600:
            return f"in {int(secs // 60)}m"
        if secs < 86400:
            return f"in {int(secs // 3600)}h"
        return dt.strftime("%d %b %H:%M")
    except ValueError:
        return iso[:16]


def _status_dot(status: str, T, colorize) -> str:
    return {
        "ACTIVE":   colorize("●", T.SUCCESS),
        "DISABLED": colorize("◉", T.WARNING),
        "PAUSED":   colorize("◉", T.WARNING),
    }.get(status.upper(), colorize("○", T.DIM))


_TASK_ICON = {
    "HEALTH_MONITORING": "❤ ",
    "LOGS_ANALYSIS":     "📊",
    "BACKUP":            "💾",
}


# ── List ──────────────────────────────────────────────────────────────────────

def _cmd_list(args: Namespace) -> int:
    (T, colorize, box_top, box_bottom, box_row,
     section, term_width, command_bar, Table) = _try_theme()

    use_json = getattr(args, "json", False)

    try:
        from system_manager_cli.core.task_scheduler import TaskScheduler
        scheduler = TaskScheduler()
        tasks = scheduler.get_all_tasks()
    except Exception as exc:
        _err(f"Could not load tasks: {exc}")
        return 3

    if use_json:
        print(json.dumps([t.to_dict() for t in tasks], indent=2, default=str))
        return 0

    w = min(term_width() - 2, 72)
    quiet = getattr(args, "quiet", False)

    if not quiet:
        print()
        print(colorize(box_top(w), T.PRIMARY))
        print(
            colorize("║", T.PRIMARY)
            + f"  {colorize('SCHEDULED TASKS', T.BOLD + T.WHITE)}"
            + " " * max(0, w - 17)
            + "  "
            + colorize("║", T.PRIMARY)
        )
        print(colorize(box_bottom(w), T.PRIMARY))

    if not tasks:
        print(f"\n  {colorize('No scheduled tasks found.', T.DIM)}")
        print(f"\n  Run  {colorize('sysmanager schedule add', T.PRIMARY)}  to create one.")
        return 0

    # Table
    if Table is not None:
        try:
            t = Table(
                headers=["ID", "Type", "Schedule", "Time", "Next Run", "Status"],
                col_align=["right", "left", "left", "left", "left", "left"],
                max_width=w,
            )
            for task in tasks:
                icon   = _TASK_ICON.get(task.task_type, "•")
                dot    = _status_dot(task.status, T, colorize)
                next_r = _format_next_run(task.next_run)
                sched  = task.display_schedule()

                t.add_row([
                    str(task.id),
                    f"{icon}  {task.display_type()}",
                    sched,
                    task.run_time,
                    next_r,
                    f"{dot} {task.status}",
                ])
            print()
            t.print()
        except Exception:
            _fallback_task_list(tasks, T, colorize)
    else:
        _fallback_task_list(tasks, T, colorize)

    # Path details below table
    print()
    print(colorize("  ── Task Details ─────────────────────────────────────────", T.DIM))
    for task in tasks:
        detail = task.display_path_info()
        if detail and detail != "—":
            icon = _TASK_ICON.get(task.task_type, "•")
            print(f"  {icon}  #{task.id}  {colorize(detail, T.DIM)}")

    print()
    return 0


def _fallback_task_list(tasks, T, colorize) -> None:
    """Plain-text fallback when Table is unavailable."""
    print()
    print(f"  {'ID':<4}  {'TYPE':<22}  {'SCHEDULE':<14}  {'TIME':<6}  STATUS")
    print("  " + "─" * 60)
    for task in tasks:
        icon = _TASK_ICON.get(task.task_type, "•")
        dot  = _status_dot(task.status, T, colorize)
        print(
            f"  {task.id:<4}  {icon} {task.display_type():<20}  "
            f"{task.display_schedule():<14}  {task.run_time:<6}  "
            f"{dot} {task.status}"
        )


# ── Add (interactive wizard) ──────────────────────────────────────────────────

def _cmd_add(args: Namespace) -> int:
    (T, colorize, box_top, box_bottom, box_row,
     section, term_width, command_bar, Table) = _try_theme()

    from system_manager_cli.CLI.schedule_menu import run_schedule_menu
    print(f"\n  {colorize('ℹ', T.PRIMARY)}  Launching interactive scheduler…")
    try:
        run_schedule_menu()
        return 0
    except Exception as exc:
        _err(f"Scheduler failed: {exc}")
        return 3


def _add_interactive() -> int:
    """Minimal interactive task-creation wizard for non-TUI mode."""
    (T, colorize, box_top, box_bottom, box_row,
     section, term_width, command_bar, Table) = _try_theme()

    from system_manager_cli.models.scheduled_task import (
        TASK_TYPE_HEALTH, TASK_TYPE_LOGS, TASK_TYPE_BACKUP,
        SCHEDULE_DAILY, SCHEDULE_WEEKLY, SCHEDULE_MONTHLY,
    )
    from system_manager_cli.core.task_scheduler import TaskScheduler

    w = min(term_width() - 2, 60)
    print()
    print(colorize(box_top(w), T.PRIMARY))
    print(colorize(box_row(colorize("  ADD SCHEDULED TASK", T.BOLD + T.WHITE), w), T.PRIMARY))
    print(colorize(box_bottom(w), T.PRIMARY))

    # Task type
    print()
    print("  Task type:")
    print(f"  {colorize('[1]', T.PRIMARY)} Health Monitoring")
    print(f"  {colorize('[2]', T.PRIMARY)} Logs Analysis")
    print(f"  {colorize('[3]', T.PRIMARY)} Data Backup")
    print(f"  {colorize('[0]', T.DIM)} Cancel")

    choice = input(f"\n  {colorize('>', T.PRIMARY)} ").strip()
    type_map = {"1": TASK_TYPE_HEALTH, "2": TASK_TYPE_LOGS, "3": TASK_TYPE_BACKUP}
    if choice not in type_map:
        print("\n  Cancelled.")
        return 0
    task_type = type_map[choice]

    # Schedule frequency
    print()
    print("  Frequency:")
    print(f"  {colorize('[1]', T.PRIMARY)} Daily")
    print(f"  {colorize('[2]', T.PRIMARY)} Weekly")
    print(f"  {colorize('[3]', T.PRIMARY)} Monthly")
    freq = input(f"\n  {colorize('>', T.PRIMARY)} ").strip()
    sched_map = {"1": SCHEDULE_DAILY, "2": SCHEDULE_WEEKLY, "3": SCHEDULE_MONTHLY}
    schedule_type = sched_map.get(freq, SCHEDULE_DAILY)

    # Time
    while True:
        raw_time = input("\n  Run time (HH:MM, 24h): ").strip()
        try:
            datetime.strptime(raw_time, "%H:%M")
            break
        except ValueError:
            print(f"  {colorize('✖', T.ERROR)}  Invalid format. Use HH:MM e.g. 09:30")

    # Optional path for backup / logs
    task_data: dict[str, Any] = {
        "task_type":    task_type,
        "schedule_type": schedule_type,
        "run_time":      raw_time,
    }

    if task_type == TASK_TYPE_BACKUP:
        raw_paths = input("\n  Source paths (comma-separated): ").strip()
        if raw_paths:
            task_data["backup_paths"] = [p.strip() for p in raw_paths.split(",") if p.strip()]

    if task_type == TASK_TYPE_LOGS:
        raw_path = input("\n  Logs path (blank = default): ").strip()
        if raw_path:
            from system_manager_cli.models.scheduled_task import LOGS_PATH_CUSTOM
            task_data["logs_path_source"] = LOGS_PATH_CUSTOM
            task_data["logs_custom_path"] = raw_path
        else:
            from system_manager_cli.models.scheduled_task import LOGS_PATH_DEFAULT
            task_data["logs_path_source"] = LOGS_PATH_DEFAULT

    try:
        scheduler = TaskScheduler()
        task = scheduler.add_task(task_data)
        print(
            f"\n  {colorize('✔', T.SUCCESS)}  Task #{task.id} scheduled — "
            f"{task.display_type()} {task.display_schedule()} at {task.run_time}"
        )
        return 0
    except Exception as exc:
        _err(f"Failed to create task: {exc}")
        return 3


# ── Run ───────────────────────────────────────────────────────────────────────

def _cmd_run(task_id: int, app, args: Namespace) -> int:
    (T, colorize, *_) = _try_theme()

    try:
        from system_manager_cli.core.task_scheduler import TaskScheduler
        scheduler = TaskScheduler()
        task = scheduler.get_task_by_id(task_id)
    except Exception as exc:
        _err(f"Could not load scheduler: {exc}")
        return 3

    if task is None:
        _err(f"Task #{task_id} not found.")
        return 1

    print(f"\n  {colorize('➤', T.PRIMARY)}  Running task #{task_id}: {task.display_type()}")

    try:
        result = app.execute_scheduled_task(task)
        status = result.get("status", "failed")
        if status == "completed":
            print(f"  {colorize('✔', T.SUCCESS)}  Task completed successfully.")
            scheduler.mark_executed(task_id)
            return 0
        else:
            err = result.get("error", "Unknown error")
            _err(f"Task failed: {err}")
            return 1
    except Exception as exc:
        _err(f"Execution error: {exc}")
        if getattr(args, "verbose", False):
            import traceback
            traceback.print_exc()
        return 3


# ── Remove ────────────────────────────────────────────────────────────────────

def _cmd_remove(task_id: int, args: Namespace) -> int:
    (T, colorize, *_) = _try_theme()

    try:
        from system_manager_cli.core.task_scheduler import TaskScheduler
        scheduler = TaskScheduler()
        task = scheduler.get_task_by_id(task_id)
    except Exception as exc:
        _err(f"Could not load scheduler: {exc}")
        return 3

    if task is None:
        _err(f"Task #{task_id} not found.")
        return 1

    print(f"\n  Task #{task_id}: {task.display_type()} — {task.display_schedule()} at {task.run_time}")

    if not getattr(args, "quiet", False):
        confirm = input(f"\n  {colorize('Remove this task? (y/n):', T.WARNING)} ").strip().lower()
        if confirm not in ("y", "yes"):
            print("  Cancelled.")
            return 0

    try:
        scheduler.remove_task(task_id)
        print(f"  {colorize('✔', T.SUCCESS)}  Task #{task_id} removed.")
        return 0
    except Exception as exc:
        _err(f"Remove failed: {exc}")
        return 3


# ── Enable / Disable ──────────────────────────────────────────────────────────

def _cmd_toggle(task_id: int, enable: bool) -> int:
    (T, colorize, *_) = _try_theme()

    try:
        from system_manager_cli.core.task_scheduler import TaskScheduler
        scheduler = TaskScheduler()
        task = scheduler.get_task_by_id(task_id)
    except Exception as exc:
        _err(f"Could not load scheduler: {exc}")
        return 3

    if task is None:
        _err(f"Task #{task_id} not found.")
        return 1

    new_status = "ACTIVE" if enable else "DISABLED"
    try:
        scheduler.update_task(task_id, {"status": new_status})
        verb = "enabled" if enable else "disabled"
        print(f"  {colorize('✔', T.SUCCESS)}  Task #{task_id} {verb}.")
        return 0
    except Exception as exc:
        _err(f"Update failed: {exc}")
        return 3


# ── Public entry point ─────────────────────────────────────────────────────────

def run(app, args: Namespace) -> int:
    """
    Execute the schedule command and its sub-commands.

    Args:
        app:  SystemManagerApp instance.
        args: Parsed argparse Namespace (args.schedule_cmd holds sub-command).

    Returns:
        Integer exit code.
    """
    sub = getattr(args, "schedule_cmd", None) or "list"

    try:
        if sub == "list":
            return _cmd_list(args)

        elif sub == "add":
            return _add_interactive()

        elif sub == "run":
            task_id = getattr(args, "task_id", None)
            if task_id is None:
                _err("Usage: sysmanager schedule run <task_id>")
                return 2
            return _cmd_run(task_id, app, args)

        elif sub == "remove":
            task_id = getattr(args, "task_id", None)
            if task_id is None:
                _err("Usage: sysmanager schedule remove <task_id>")
                return 2
            return _cmd_remove(task_id, args)

        elif sub == "enable":
            task_id = getattr(args, "task_id", None)
            if task_id is None:
                _err("Usage: sysmanager schedule enable <task_id>")
                return 2
            return _cmd_toggle(task_id, enable=True)

        elif sub == "disable":
            task_id = getattr(args, "task_id", None)
            if task_id is None:
                _err("Usage: sysmanager schedule disable <task_id>")
                return 2
            return _cmd_toggle(task_id, enable=False)

        else:
            _err(f"Unknown sub-command: {sub!r}. Run 'sysmanager schedule --help'.")
            return 2

    except KeyboardInterrupt:
        print("\n  Interrupted.")
        return 0
    except Exception as exc:
        _err(f"Unexpected error: {exc}")
        if getattr(args, "verbose", False):
            import traceback
            traceback.print_exc()
        return 3
