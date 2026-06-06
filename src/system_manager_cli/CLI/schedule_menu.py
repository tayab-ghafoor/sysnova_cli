"""Schedule Menu - CLI interaction layer for Task Scheduling (Main Menu option 5).

Handles all user-facing prompts, input validation, and display for:
  1. Schedule a task
  2. View scheduled tasks
  3. Edit a scheduled task
  4. Remove a scheduled task

Architecture Rules:
- This module ONLY handles I/O.
- All business logic is in TaskScheduler (core/task_scheduler.py).
- Calls app.py methods for actual task execution.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import List, Optional, Tuple

from ..core.task_scheduler import TaskScheduler
from ..models.scheduled_task import (
    LOGS_PATH_CWD,
    LOGS_PATH_CUSTOM,
    LOGS_PATH_DEFAULT,
    SCHEDULE_DAILY,
    SCHEDULE_EVERY_MINUTE,
    SCHEDULE_MONTHLY,
    SCHEDULE_WEEKLY,
    TASK_TYPE_BACKUP,
    TASK_TYPE_HEALTH,
    TASK_TYPE_LOGS,
    ScheduledTask,
)


# ─────────────────────────────────────────────────────────────────────────────
# Display helpers
# ─────────────────────────────────────────────────────────────────────────────

def _divider(char: str = "=", width: int = 50) -> None:
    print(char * width)


def _header(title: str) -> None:
    _divider()
    print(f"  {title}")
    _divider()


def _prompt(message: str) -> str:
    return input(f"\n  {message} ").strip()


def _pause() -> None:
    input("\n  Press any key to continue...")


def _yes_no(question: str) -> bool:
    while True:
        ans = _prompt(f"{question} (Y/N):").upper()
        if ans in ("Y", "YES"):
            return True
        if ans in ("N", "NO"):
            return False
        print("  ❌  Please enter Y or N.")


# ─────────────────────────────────────────────────────────────────────────────
# Input validators
# ─────────────────────────────────────────────────────────────────────────────

def _collect_time() -> str:
    """Prompt repeatedly until a valid HH:MM (24-hour) time is entered."""
    while True:
        raw = _prompt("Enter time at which task runs (24-hour format, HH:MM):")
        try:
            datetime.strptime(raw, "%H:%M")
            return raw
        except ValueError:
            print("  ❌  Invalid time format. Please use HH:MM (e.g. 14:30).")


def _collect_schedule_type(allow_every_minute: bool = False) -> str:
    """Prompt for schedule frequency.  Returns a SCHEDULE_* constant."""
    options = "daily, weekly, monthly"
    default_label = "daily"

    if allow_every_minute:
        options += ", every_minute"

    while True:
        raw = _prompt(
            f"How often should the task run? ({options}) [{default_label}]:"
        ).lower()

        if raw == "" or raw == "daily":
            return SCHEDULE_DAILY
        if raw == "weekly":
            return SCHEDULE_WEEKLY
        if raw == "monthly":
            return SCHEDULE_MONTHLY
        if allow_every_minute and raw in ("every_minute", "every minute"):
            return SCHEDULE_EVERY_MINUTE

        valid = "daily, weekly, monthly" + (", every_minute" if allow_every_minute else "")
        print(f"  ❌  Invalid option. Please enter one of: {valid}")


def _collect_backup_paths() -> List[str]:
    """Prompt for comma-separated backup paths, validating each one."""
    while True:
        raw = _prompt("Enter files/folders path (comma-separated for multiple paths):")
        if not raw:
            print("  ❌  Path cannot be empty. Please enter at least one path.")
            continue

        candidates = [p.strip() for p in raw.split(",") if p.strip()]
        valid_paths: List[str] = []
        all_ok = True

        for path in candidates:
            if os.path.exists(path):
                print(f"  ✅  Path verified: {path}")
                valid_paths.append(path)
            else:
                print(f"  ❌  '{path}' is incorrect or does not exist. Please enter a correct path.")
                all_ok = False

        if all_ok and valid_paths:
            return valid_paths

        # At least one path was wrong — loop back and ask again
        print()


def _collect_logs_path_source() -> Tuple[str, Optional[str]]:
    """
    Show the Logs Analysis path-source sub-menu.

    Returns:
        (logs_path_source, logs_custom_path)
        logs_custom_path is None unless LOGS_PATH_CUSTOM is chosen.
    """
    print()
    _divider("-", 50)
    print("  LOGS ANALYSIS AND GENERATING REPORTS MENU")
    _divider("-", 50)
    print("  1. Analyse logs from default path")
    print("  2. Analyse logs from current working directory")
    print("  3. Enter custom path")
    _divider("-", 50)

    while True:
        choice = _prompt("Select anyone number (1-3):")

        if choice == "1":
            return LOGS_PATH_DEFAULT, None

        if choice == "2":
            return LOGS_PATH_CWD, None

        if choice == "3":
            while True:
                custom = _prompt("Enter a custom path for logs analysis:")
                if not custom:
                    print("  ❌  Path cannot be empty.")
                    continue
                if os.path.exists(custom):
                    print(f"  ✅  Path verified: {custom}")
                    return LOGS_PATH_CUSTOM, custom
                print(
                    f"  ❌  '{custom}' is incorrect or does not exist. "
                    "Please enter a correct path."
                )

        print("  ❌  Please enter 1, 2, or 3.")


# ─────────────────────────────────────────────────────────────────────────────
# Task display table
# ─────────────────────────────────────────────────────────────────────────────

def _format_iso_date(iso: Optional[str]) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso


def _print_tasks_table(tasks: List[ScheduledTask]) -> None:
    if not tasks:
        print("\n  No scheduled tasks found.")
        return

    col_w = [4, 20, 14, 15, 10, 17, 17]
    headers = ["ID", "TYPE", "SCHEDULE", "TIME", "STATUS", "LAST RUN", "NEXT RUN"]

    sep = "  +" + "+".join("-" * (w + 2) for w in col_w) + "+"
    row_fmt = "  |" + "|".join(f" {{:<{w}}} " for w in col_w) + "|"

    print()
    print(sep)
    print(row_fmt.format(*headers))
    print(sep)

    for task in tasks:
        schedule_display = task.display_schedule()
        if task.schedule_type == SCHEDULE_EVERY_MINUTE:
            time_display = "Every 1 min"
        else:
            time_display = task.run_time

        print(row_fmt.format(
            str(task.id),
            task.display_type()[:20],
            schedule_display[:14],
            time_display[:15],
            task.status[:10],
            _format_iso_date(task.last_run)[:17],
            _format_iso_date(task.next_run)[:17],
        ))

    print(sep)


# ─────────────────────────────────────────────────────────────────────────────
# Sub-flows  (1 per menu item)
# ─────────────────────────────────────────────────────────────────────────────

def _schedule_task(scheduler: TaskScheduler) -> None:
    """Flow for 'Schedule a Task' (menu option 1)."""
    _header("SCHEDULE A TASK")
    print("  Which operation do you want to schedule?")
    print("  1. Health Monitoring")
    print("  2. Logs Analysis")
    print("  3. Backup Data")
    _divider("-", 50)

    while True:
        choice = _prompt("Select option (1-3):")

        # ── Health Monitoring ─────────────────────────────────────────
        if choice == "1":
            run_time = _collect_time()
            schedule_type = _collect_schedule_type(allow_every_minute=False)

            task = scheduler.add_task({
                "task_type": TASK_TYPE_HEALTH,
                "schedule_type": schedule_type,
                "run_time": run_time,
            })
            print(
                f"\n  ✅  Task scheduled for Health Monitoring at {run_time} "
                f"({task.display_schedule()})."
            )
            break

        # ── Logs Analysis ─────────────────────────────────────────────
        elif choice == "2":
            logs_source, custom_path = _collect_logs_path_source()
            run_time = _collect_time()
            schedule_type = _collect_schedule_type(allow_every_minute=True)

            # Build the confirmation label
            if logs_source == LOGS_PATH_DEFAULT:
                path_label = "default path"
            elif logs_source == LOGS_PATH_CWD:
                path_label = "current working directory"
            else:
                path_label = custom_path or "custom path"

            task = scheduler.add_task({
                "task_type": TASK_TYPE_LOGS,
                "schedule_type": schedule_type,
                "run_time": run_time,
                "logs_path_source": logs_source,
                "logs_custom_path": custom_path,
            })
            print(
                f"\n  ✅  Task scheduled for Logs Analysis "
                f"({path_label}) at {run_time} ({task.display_schedule()})."
            )
            break

        # ── Backup Data ───────────────────────────────────────────────
        elif choice == "3":
            backup_paths = _collect_backup_paths()
            run_time = _collect_time()
            schedule_type = _collect_schedule_type(allow_every_minute=False)

            task = scheduler.add_task({
                "task_type": TASK_TYPE_BACKUP,
                "schedule_type": schedule_type,
                "run_time": run_time,
                "backup_paths": backup_paths,
            })
            print(
                f"\n  ✅  Task scheduled for Data Backup at {run_time} "
                f"({task.display_schedule()})."
            )
            break

        else:
            print("  ❌  Please enter 1, 2, or 3.")


def _view_tasks(scheduler: TaskScheduler) -> None:
    """Flow for 'View Scheduled Tasks' (menu option 2)."""
    _header("VIEW SCHEDULED TASKS")
    tasks = scheduler.get_all_tasks()

    if not tasks:
        print("\n  No scheduled tasks found.")
    else:
        _print_tasks_table(tasks)

    _pause()


def _edit_task(scheduler: TaskScheduler) -> None:
    """Flow for 'Edit Scheduled Task' (menu option 3)."""
    _header("EDIT SCHEDULED TASK")
    tasks = scheduler.get_all_tasks()

    if not tasks:
        print("\n  No scheduled tasks found.")
        _pause()
        return

    _print_tasks_table(tasks)

    # ── Select task ───────────────────────────────────────────────────
    valid_ids = {t.id for t in tasks}
    while True:
        raw = _prompt("Enter task ID to edit:")
        try:
            task_id = int(raw)
            if task_id in valid_ids:
                break
            print(f"  ❌  Task ID {task_id} not found.")
        except ValueError:
            print("  ❌  Please enter a valid numeric task ID.")

    task = scheduler.get_task_by_id(task_id)
    assert task is not None  # guaranteed by the loop above

    print(f"\n  Editing task #{task.id} — {task.display_type()}")
    _divider("-", 50)

    # ── New task type ─────────────────────────────────────────────────
    print("  Enter new task type:")
    print("  1. Health Monitoring")
    print("  2. Logs Analysis")
    print("  3. Backup Data")

    while True:
        choice = _prompt("Select option (1-3):")

        updates: dict = {}

        if choice == "1":
            updates["task_type"] = TASK_TYPE_HEALTH
            updates["backup_paths"] = []
            updates["logs_path_source"] = None
            updates["logs_custom_path"] = None
            break

        elif choice == "2":
            logs_source, custom_path = _collect_logs_path_source()
            updates["task_type"] = TASK_TYPE_LOGS
            updates["logs_path_source"] = logs_source
            updates["logs_custom_path"] = custom_path
            updates["backup_paths"] = []
            break

        elif choice == "3":
            backup_paths = _collect_backup_paths()
            updates["task_type"] = TASK_TYPE_BACKUP
            updates["backup_paths"] = backup_paths
            updates["logs_path_source"] = None
            updates["logs_custom_path"] = None
            break

        else:
            print("  ❌  Please enter 1, 2, or 3.")

    # ── New schedule type & time ──────────────────────────────────────
    allow_minute = updates.get("task_type") == TASK_TYPE_LOGS
    updates["schedule_type"] = _collect_schedule_type(allow_every_minute=allow_minute)
    updates["run_time"] = _collect_time()

    scheduler.update_task(task_id, updates)
    print("\n  ✅  Task updated successfully.")
    _pause()


def _remove_task(scheduler: TaskScheduler) -> None:
    """Flow for 'Remove Scheduled Task' (menu option 4)."""
    _header("REMOVE SCHEDULED TASK")
    tasks = scheduler.get_all_tasks()

    if not tasks:
        print("\n  No scheduled tasks found.")
        _pause()
        return

    _print_tasks_table(tasks)

    # ── Select task ───────────────────────────────────────────────────
    valid_ids = {t.id for t in tasks}
    while True:
        raw = _prompt("Enter task ID to remove:")
        try:
            task_id = int(raw)
            if task_id in valid_ids:
                break
            print(f"  ❌  Task ID {task_id} not found.")
        except ValueError:
            print("  ❌  Please enter a valid numeric task ID.")

    # ── Confirm ───────────────────────────────────────────────────────
    if _yes_no(f"  Are you sure you want to remove task #{task_id}?"):
        scheduler.remove_task(task_id)
        print("\n  ✅  Task removed successfully.")
    else:
        print("\n  ℹ️   Removal cancelled.")

    _pause()


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────
def run_schedule_menu(app=None, session_id: str = "") -> None:
    """
    Entry point called from main.py when user selects option 5.
    Runs the Task Scheduling sub-menu in a loop until the user
    chooses 'Back to Main Menu'.
 
    Args:
        app:        SystemManagerApp instance (accepted for API compatibility,
                    not used — TaskScheduler is instantiated directly).
        session_id: Active session ID (accepted for compatibility, not used).
    """
    scheduler = TaskScheduler()
 
    while True:
        print()
        _divider()
        print("       TASKS SCHEDULING MENU")
        _divider()
        print("  1. Schedule a Task")
        print("  2. View Scheduled Tasks")
        print("  3. Edit Scheduled Task")
        print("  4. Remove Scheduled Task")
        print("  5. Back to Main Menu")
        _divider()
 
        choice = _prompt("Select any number (1-5):")
 
        if choice == "1":
            _schedule_task(scheduler)
        elif choice == "2":
            _view_tasks(scheduler)
        elif choice == "3":
            _edit_task(scheduler)
        elif choice == "4":
            _remove_task(scheduler)
        elif choice == "5":
            break
        else:
            print("  ❌  Invalid selection. Please enter a number from 1 to 5.")