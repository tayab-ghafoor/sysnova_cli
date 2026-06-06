"""Health Monitor — evaluate project-level system health.

Fix 4 change:
    The `backup_dir` path check previously always returned True after the
    first run because Config.ensure_directories() creates the backup
    directory at startup.  This made the health check useless for its
    primary purpose: detecting that an *external* backup drive is mounted.

    New behaviour:
      - If BACKUP_DRIVE env var is set to a custom path (i.e. the user
        configured a real external drive), the check tests whether the
        path is actually reachable/mounted — not just whether a local
        fallback folder was auto-created.
      - If BACKUP_DRIVE is not set (using the default local fallback),
        the check still passes as before, but a note is added to warnings
        to let the user know they are using local storage only.
"""

from __future__ import annotations

import os
import shutil
from typing import Any

from ...config.app_config import AppConfig
from ...config.config import Config
from ...core.Exception import HealthMonitorError

try:
    import psutil
except ImportError:  # pragma: no cover - optional dependency
    psutil = None

# The default fallback path used when BACKUP_DRIVE is not set in .env
_DEFAULT_BACKUP_PATH = str(Config.BACKUPS_DIR)


def _backup_drive_is_configured() -> bool:
    """Return True when BACKUP_DRIVE env var points to a non-default location."""
    env_val = os.getenv("BACKUP_DRIVE", "").strip()
    return bool(env_val) and env_val != _DEFAULT_BACKUP_PATH


def _check_backup_dir() -> tuple[bool, str | None]:
    """
    Check backup directory availability.

    Returns:
        (is_available, warning_message | None)

    Logic:
        - External drive configured (BACKUP_DRIVE env set):
            Check the path actually exists right now.
            If not → the drive is probably not mounted.
        - No external drive configured (using local fallback):
            Path always exists (created by ensure_directories).
            Return True but add an informational warning.
    """
    backup_path = Config.BACKUP_DRIVE

    if _backup_drive_is_configured():
        # Real external path — test live reachability
        available = backup_path.exists()
        warning   = None if available else (
            f"Backup drive not reachable: {backup_path}. "
            "Check that the external drive is mounted."
        )
        return available, warning
    else:
        # Local fallback — always created, always reachable
        available = backup_path.exists()
        warning   = (
            "BACKUP_DRIVE is not configured. "
            "Backups are stored locally at the default path. "
            "Set BACKUP_DRIVE in your .env to use an external drive."
        )
        return available, warning


class HealthMonitor:
    """Evaluate project-level health without interacting with the CLI."""

    def check_system_health(self) -> dict[str, Any]:
        try:
            Config.ensure_directories()
            config_valid   = AppConfig().is_valid()
            warnings: list[str] = []
            overall_status = "healthy"

            # ── Disk ──────────────────────────────────────────────────────
            disk_usage       = shutil.disk_usage(Config.APP_DATA_ROOT)
            disk_used_percent = round(
                (disk_usage.used / disk_usage.total) * 100, 2
            )

            if disk_used_percent >= 95:
                warnings.append("Disk usage is critically high.")
                overall_status = "critical"
            elif disk_used_percent >= Config.DISK_THRESHOLD:
                warnings.append("Disk usage is above the configured threshold.")
                overall_status = "warning"

            # ── CPU / RAM (psutil) ─────────────────────────────────────────
            cpu    = None
            memory = None

            if psutil is not None:
                cpu    = round(psutil.cpu_percent(interval=0.1), 2)
                memory = round(psutil.virtual_memory().percent, 2)

                if cpu >= 95 or memory >= 95:
                    overall_status = "critical"
                elif overall_status == "healthy" and (
                    cpu >= Config.CPU_THRESHOLD or memory >= Config.RAM_THRESHOLD
                ):
                    overall_status = "warning"

                if cpu >= Config.CPU_THRESHOLD:
                    warnings.append("CPU usage is above the configured threshold.")
                if memory >= Config.RAM_THRESHOLD:
                    warnings.append("Memory usage is above the configured threshold.")
            else:
                warnings.append(
                    "psutil is not installed; CPU and memory metrics are unavailable."
                )

            # ── Path checks ───────────────────────────────────────────────
            backup_available, backup_warning = _check_backup_dir()

            if backup_warning:
                warnings.append(backup_warning)

            path_checks = {
                "data_dir":    Config.DATA_DIR.exists(),
                "logs_dir":    Config.LOGS_DIR.exists(),
                "reports_dir": Config.REPORTS_DIR.exists(),
                # Fix 4: backup_dir now reflects real drive availability,
                # not just whether the local fallback folder was created.
                "backup_dir":  backup_available,
            }

            if not all(path_checks.values()):
                warnings.append("One or more required project directories are missing.")
                if overall_status == "healthy":
                    overall_status = "warning"

            # ── Config validation ─────────────────────────────────────────
            if not config_valid:
                warnings.append("Application configuration failed validation.")
                if overall_status == "healthy":
                    overall_status = "warning"

            return {
                "overall_status":  overall_status,
                "config_valid":    config_valid,
                "disk": {
                    "used_percent": disk_used_percent,
                    "free_bytes":   disk_usage.free,
                },
                "cpu_percent":    cpu,
                "memory_percent": memory,
                "paths":          path_checks,
                # Extra detail for the UI — was the backup check against
                # a real external drive or just the local fallback?
                "backup_drive_external": _backup_drive_is_configured(),
                "warnings":       warnings,
            }

        except Exception as exc:  # pragma: no cover - defensive wrapper
            raise HealthMonitorError(str(exc)) from exc