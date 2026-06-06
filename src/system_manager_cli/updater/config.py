"""
Update Configuration

Centralised, validated settings for the automatic update system.
All values can be overridden via environment variables.
"""

from __future__ import annotations

import os
from pathlib import Path


def _bool_env(key: str, default: bool) -> bool:
    raw = os.environ.get(key, "").strip().lower()
    if raw in ("1", "true", "yes"):
        return True
    if raw in ("0", "false", "no"):
        return False
    return default


def _int_env(key: str, default: int) -> int:
    try:
        return int(os.environ[key])
    except (KeyError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Core update server settings
# ---------------------------------------------------------------------------
UPDATE_CONFIG: dict = {
    # URL that returns the update manifest JSON (see WEBSITE_NOTES.md for schema)
    "version_url": (
        os.environ.get("UPDATE_URL")
        or os.environ.get("UPDATE_VERSION_URL")
        or "https://systemmanagement.bela002.com/api/update.json"
    ),

    # Enable / disable the silent background auto-updater thread
    "auto_update_enabled": _bool_env("AUTO_UPDATE_ENABLED", True),

    # How many hours between background update checks
    "check_interval_hours": _int_env("UPDATE_CHECK_INTERVAL_HOURS", 24),

    # Number of timestamped backups to keep on disk
    "backup_count": _int_env("UPDATE_BACKUP_COUNT", 3),

    # Seconds to wait for the download HTTP response
    "download_timeout": _int_env("UPDATE_DOWNLOAD_TIMEOUT", 60),

    # Write an update.log file inside the state directory
    "enable_logging": _bool_env("UPDATE_ENABLE_LOGGING", True),

    # Subdirectory (relative to exe directory) where modules live
    "modules_path": Path(os.environ.get("MODULES_PATH", "current")),
}

# ---------------------------------------------------------------------------
# Optional HTTP authentication for the update server
# ---------------------------------------------------------------------------
UPDATE_AUTH: dict = {
    "username": os.environ.get("UPDATE_USERNAME"),
    "password": os.environ.get("UPDATE_PASSWORD"),
    "api_key":  os.environ.get("UPDATE_API_KEY"),
}