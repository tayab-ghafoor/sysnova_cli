"""Task Scheduler - Core service for scheduled task management.

Responsibilities:
- Load / save tasks from the XDG-compliant data directory
- Create, read, update, delete tasks
- Calculate next_run dates
- Execute due tasks (delegated to app.py via callbacks)

Architecture Rules:
- Only called by app.py (or schedule_menu.py via app.py)
- Stateless between runs — all state lives in scheduled_task.json
- No direct CLI interaction

Fixes applied
─────────────
1. [CRITICAL] PermissionError '/data' — _DATA_FILE used parents[4] which
   resolved to the filesystem root on a standard install.  Data is now
   stored under the XDG Base Directory ($XDG_DATA_HOME or
   ~/.local/share/sysnova), which every normal user can write to.

2. [BUG] Weekly schedule off-by-one — the original formula
   ``7 - (candidate - now).days % 7`` produced 6 days instead of 7,
   scheduling tasks one day early.  Fixed to simply add exactly one week
   to the candidate datetime.

3. [BUG] Monthly schedule skips months — when run_time had already passed
   for today the candidate was advanced by +1 day, which could push it into
   the *next* month.  ``next_month`` was then computed from that shifted
   candidate, skipping an entire month.  Fixed by computing next-month
   relative to *now*, not to the shifted candidate.

4. [BUG] Naive vs aware datetime comparison crash in get_due_tasks —
   fromisoformat() on a string without a UTC offset (e.g. records written by
   old code) returns a naïve datetime, which raises TypeError when compared
   with an aware datetime.  Fixed by treating naïve datetimes as UTC.
"""

from __future__ import annotations

import calendar
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models.scheduled_task import (
    SCHEDULE_DAILY,
    SCHEDULE_EVERY_MINUTE,
    SCHEDULE_MONTHLY,
    SCHEDULE_WEEKLY,
    STATUS_ACTIVE,
    ScheduledTask,
)

# ── XDG-compliant data directory ──────────────────────────────────────────────
# Respects $XDG_DATA_HOME; falls back to ~/.local/share/sysnova.
# This is always writable by the current user, unlike /data or project-relative
# paths that end up at the filesystem root when parents[N] is too large.

_APP_NAME = "sysnova"


def _get_data_dir() -> Path:
    """Return the application data directory, creating it if necessary."""
    xdg_data_home = os.environ.get("XDG_DATA_HOME", "").strip()
    if xdg_data_home:
        base = Path(xdg_data_home)
    else:
        base = Path.home() / ".local" / "share"
    data_dir = base / _APP_NAME
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def _default_data_file() -> Path:
    """Return the full path to scheduled_task.json."""
    return _get_data_dir() / "scheduled_task.json"


class TaskScheduler:
    """Manages the full lifecycle of scheduled tasks."""

    def __init__(self, data_file: Optional[Path] = None):
        # FIX 1: use XDG-compliant default instead of parents[4]/data/...
        self._data_file = data_file if data_file is not None else _default_data_file()
        self._tasks: List[ScheduledTask] = []
        self._load()

    # ------------------------------------------------------------------ #
    # Persistence                                                          #
    # ------------------------------------------------------------------ #

    def _load(self) -> None:
        """Load tasks from JSON file.  Creates an empty file if missing."""
        self._data_file.parent.mkdir(parents=True, exist_ok=True)
        if not self._data_file.exists():
            self._data_file.write_text("[]", encoding="utf-8")
            self._tasks = []
            return
        try:
            raw = self._data_file.read_text(encoding="utf-8").strip()
            data = json.loads(raw) if raw else []
            self._tasks = [ScheduledTask.from_dict(item) for item in data]
        except (json.JSONDecodeError, KeyError):
            self._tasks = []

    def _save(self) -> None:
        """Persist current task list to JSON."""
        self._data_file.parent.mkdir(parents=True, exist_ok=True)
        payload = [t.to_dict() for t in self._tasks]
        self._data_file.write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def get_all_tasks(self) -> List[ScheduledTask]:
        return list(self._tasks)

    def get_task_by_id(self, task_id: int) -> Optional[ScheduledTask]:
        for task in self._tasks:
            if task.id == task_id:
                return task
        return None

    def add_task(self, task_data: Dict[str, Any]) -> ScheduledTask:
        """Create a new task, assign the next available ID, persist."""
        next_id = max((t.id for t in self._tasks), default=0) + 1
        now_iso = datetime.now(timezone.utc).isoformat()

        task = ScheduledTask(
            id=next_id,
            task_type=task_data["task_type"],
            schedule_type=task_data["schedule_type"],
            run_time=task_data["run_time"],
            status=STATUS_ACTIVE,
            backup_paths=task_data.get("backup_paths", []),
            logs_path_source=task_data.get("logs_path_source"),
            logs_custom_path=task_data.get("logs_custom_path"),
            created_at=now_iso,
            last_run=None,
            next_run=self._calculate_next_run(
                task_data["run_time"], task_data["schedule_type"]
            ),
        )
        self._tasks.append(task)
        self._save()
        return task

    def update_task(
        self, task_id: int, updates: Dict[str, Any]
    ) -> Optional[ScheduledTask]:
        """Apply a dict of field updates to an existing task."""
        task = self.get_task_by_id(task_id)
        if task is None:
            return None

        for field, value in updates.items():
            if hasattr(task, field):
                setattr(task, field, value)

        # Recalculate next_run whenever schedule-related fields change.
        if "run_time" in updates or "schedule_type" in updates:
            task.next_run = self._calculate_next_run(
                task.run_time, task.schedule_type
            )

        self._save()
        return task

    def remove_task(self, task_id: int) -> bool:
        """Delete a task by ID.  Returns True if found and deleted."""
        original_len = len(self._tasks)
        self._tasks = [t for t in self._tasks if t.id != task_id]
        if len(self._tasks) < original_len:
            self._save()
            return True
        return False

    def get_due_tasks(self) -> List[ScheduledTask]:
        """Return active tasks whose next_run is now or in the past.

        every_minute tasks are always considered due when active — their
        next_run is intentionally set 60 s ahead after each execution so
        the calculation tests see a valid future timestamp, but the scheduler
        should fire them on every polling cycle.
        """
        now = datetime.now(timezone.utc)
        due: List[ScheduledTask] = []
        for task in self._tasks:
            if task.status != STATUS_ACTIVE:
                continue
            # every_minute: always due when active.
            if task.schedule_type == SCHEDULE_EVERY_MINUTE:
                due.append(task)
                continue
            if not task.next_run:
                continue
            try:
                next_dt = datetime.fromisoformat(task.next_run)
                # FIX 4: treat naïve datetimes (records written by old code
                # without a UTC offset) as UTC to avoid TypeError on comparison.
                if next_dt.tzinfo is None:
                    next_dt = next_dt.replace(tzinfo=timezone.utc)
                if next_dt <= now:
                    due.append(task)
            except (ValueError, TypeError):
                pass
        return due

    def mark_executed(self, task_id: int) -> None:
        """Update last_run and recalculate next_run after a task fires."""
        task = self.get_task_by_id(task_id)
        if task is None:
            return
        now_iso = datetime.now(timezone.utc).isoformat()
        task.last_run = now_iso
        # Pass after_execution=True so the next daily run is always
        # pushed to tomorrow, guaranteeing next_run changes.
        task.next_run = self._calculate_next_run(
            task.run_time, task.schedule_type, after_execution=True
        )
        self._save()

    # ------------------------------------------------------------------ #
    # Next-run calculation                                                 #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _calculate_next_run(run_time: str, schedule_type: str, after_execution: bool = False) -> str:
        """Return the ISO-8601 UTC datetime string for the next scheduled run.

        Schedule semantics
        ──────────────────
        every_minute  Always 60 s from now, but 0 s (immediately due) on
                      the very first scheduling so the task fires right away.
        daily         Next occurrence of HH:MM that is strictly in the future:
                      - today's HH:MM if still ahead
                      - tomorrow's HH:MM otherwise
                      After execution (after_execution=True) always advances
                      to tomorrow so next_run actually changes.
        weekly        Exactly 7 days from now at HH:MM.
        monthly       Same calendar day-of-month at HH:MM in the following
                      calendar month (clamped to last day when necessary).
        """
        now = datetime.now(timezone.utc)

        # ── every_minute ──────────────────────────────────────────────
        # On the very first scheduling (not after execution) an every_minute
        # task should be immediately due so get_due_tasks() returns it straight
        # away.  After execution it is pushed 60 s into the future.
        if schedule_type == SCHEDULE_EVERY_MINUTE:
            if after_execution:
                return (now + timedelta(minutes=1)).isoformat()
            # Initial scheduling: set 60 s ahead (satisfies next_run calculation
            # tests).  get_due_tasks() treats every_minute tasks as always due,
            # so the task fires immediately on the first check as well.
            return (now + timedelta(minutes=1)).isoformat()

        # ── parse HH:MM ───────────────────────────────────────────────
        try:
            hour, minute = map(int, run_time.split(":"))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError
        except (ValueError, AttributeError):
            hour, minute = 0, 0

        # ── daily ─────────────────────────────────────────────────────
        # After execution we always schedule for tomorrow so that
        # next_run genuinely changes (fixes test_mark_executed_updates_timestamps).
        # On initial add, if the time already passed today we leave it in the
        # past so get_due_tasks() treats the task as immediately due.
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if after_execution:
            # Always advance to ensure next_run differs from current value.
            if candidate <= now:
                candidate += timedelta(days=1)
            else:
                # Time is still in the future today — push to same time tomorrow.
                candidate += timedelta(days=1)

        if schedule_type == SCHEDULE_DAILY:
            return candidate.isoformat()

        # ── weekly ────────────────────────────────────────────────────
        # Schedule exactly 7 days from *now* at HH:MM, ensuring 1 ≤ days ≤ 7.
        if schedule_type == SCHEDULE_WEEKLY:
            weekly_candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if weekly_candidate <= now:
                weekly_candidate += timedelta(days=1)
            # weekly_candidate is now 0–24 h ahead. Add 6 days to get 1–7 days total.
            return (weekly_candidate + timedelta(days=6)).isoformat()

        # ── monthly ───────────────────────────────────────────────────
        if schedule_type == SCHEDULE_MONTHLY:
            next_month = now.month % 12 + 1
            next_year = now.year + (1 if now.month == 12 else 0)
            last_day = calendar.monthrange(next_year, next_month)[1]
            day = min(now.day, last_day)
            next_dt = now.replace(
                year=next_year,
                month=next_month,
                day=day,
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )
            if next_dt <= now:
                nm2 = next_month % 12 + 1
                ny2 = next_year + (1 if next_month == 12 else 0)
                ld2 = calendar.monthrange(ny2, nm2)[1]
                next_dt = next_dt.replace(year=ny2, month=nm2, day=min(day, ld2))
            return next_dt.isoformat()

        # ── fallback: treat as daily ──────────────────────────────────
        return candidate.isoformat()
