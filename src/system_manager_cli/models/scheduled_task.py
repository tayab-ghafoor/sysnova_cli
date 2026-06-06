"""Scheduled Task Model

Data structure representing a single scheduled task.
All persistence is handled by TaskScheduler, not this model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# Valid task types
TASK_TYPE_HEALTH = "HEALTH_MONITORING"
TASK_TYPE_LOGS = "LOGS_ANALYSIS"
TASK_TYPE_BACKUP = "BACKUP"

# Valid schedule frequencies
SCHEDULE_DAILY = "daily"
SCHEDULE_WEEKLY = "weekly"
SCHEDULE_MONTHLY = "monthly"
SCHEDULE_EVERY_MINUTE = "every_minute"   # Logs Analysis only

# Valid status values
STATUS_ACTIVE = "ACTIVE"
STATUS_DISABLED = "DISABLED"
STATUS_PAUSED = "PAUSED"

# Logs Analysis path source constants
LOGS_PATH_DEFAULT = "DEFAULT_PATH"
LOGS_PATH_CWD = "CURRENT_WORKING_DIRECTORY"
LOGS_PATH_CUSTOM = "CUSTOM"


@dataclass
class ScheduledTask:
    """Represents a single scheduled task."""

    id: int
    task_type: str                      # TASK_TYPE_* constant
    schedule_type: str                  # SCHEDULE_* constant
    run_time: str                       # HH:MM  (24-hour)
    status: str = STATUS_ACTIVE

    # Type-specific fields
    backup_paths: list[str] = field(default_factory=list)   # BACKUP only
    logs_path_source: Optional[str] = None                  # LOGS_ANALYSIS only
    logs_custom_path: Optional[str] = None                  # LOGS_ANALYSIS + CUSTOM only

    # Audit fields (ISO-8601 strings or None)
    created_at: Optional[str] = None
    last_run: Optional[str] = None
    next_run: Optional[str] = None

    # ------------------------------------------------------------------ #
    # Computed helpers                                                     #
    # ------------------------------------------------------------------ #

    def display_type(self) -> str:
        mapping = {
            TASK_TYPE_HEALTH: "Health Monitoring",
            TASK_TYPE_LOGS: "Logs Analysis",
            TASK_TYPE_BACKUP: "Backup",
        }
        return mapping.get(self.task_type, self.task_type)

    def display_schedule(self) -> str:
        mapping = {
            SCHEDULE_DAILY: "Daily",
            SCHEDULE_WEEKLY: "Weekly",
            SCHEDULE_MONTHLY: "Monthly",
            SCHEDULE_EVERY_MINUTE: "Every Minute",
        }
        return mapping.get(self.schedule_type, self.schedule_type)

    def display_path_info(self) -> str:
        """Return a human-readable description of the task's target."""
        if self.task_type == TASK_TYPE_BACKUP:
            return ", ".join(self.backup_paths) if self.backup_paths else "—"
        if self.task_type == TASK_TYPE_LOGS:
            if self.logs_path_source == LOGS_PATH_DEFAULT:
                return "Default path"
            if self.logs_path_source == LOGS_PATH_CWD:
                return "Current working directory"
            if self.logs_path_source == LOGS_PATH_CUSTOM:
                return self.logs_custom_path or "—"
        return "—"

    # ------------------------------------------------------------------ #
    # Serialisation                                                        #
    # ------------------------------------------------------------------ #

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_type": self.task_type,
            "schedule_type": self.schedule_type,
            "run_time": self.run_time,
            "status": self.status,
            "backup_paths": self.backup_paths,
            "logs_path_source": self.logs_path_source,
            "logs_custom_path": self.logs_custom_path,
            "created_at": self.created_at,
            "last_run": self.last_run,
            "next_run": self.next_run,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScheduledTask":
        return cls(
            id=data["id"],
            task_type=data["task_type"],
            schedule_type=data["schedule_type"],
            run_time=data["run_time"],
            status=data.get("status", STATUS_ACTIVE),
            backup_paths=data.get("backup_paths", []),
            logs_path_source=data.get("logs_path_source"),
            logs_custom_path=data.get("logs_custom_path"),
            created_at=data.get("created_at"),
            last_run=data.get("last_run"),
            next_run=data.get("next_run"),
        )