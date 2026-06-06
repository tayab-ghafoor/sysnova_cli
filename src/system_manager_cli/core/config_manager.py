"""Backup configuration manager.

User-editable backup configuration must live in the writable application data
directory. Installed packages, PyInstaller extraction directories, Program
Files, and /usr/local/bin are not safe places to write runtime state.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..config.config import Config
from ..models.config_model import BackupConfig
from ..ulits.logger import get_logger

logger = get_logger(__name__)

def _config_path() -> Path:
    return Config.DATA_DIR / "backup_config.json"


def _default_config_path() -> Path:
    return Config.PACKAGE_DIR / "config" / "backup_config.json"


def load_config() -> BackupConfig:
    """Load backup config from JSON.  Returns default config if file missing."""
    Config.ensure_directories()
    config_path = _config_path()
    default_config_path = _default_config_path()
    if not config_path.exists():
        if default_config_path.exists():
            try:
                data = json.loads(default_config_path.read_text(encoding="utf-8"))
                logger.debug("Default config loaded from %s", default_config_path)
                return BackupConfig.from_dict(data)
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning("Ignoring invalid default backup config at %s: %s", default_config_path, exc)
        logger.debug("No config file found at %s. Using default config.", config_path)
        return BackupConfig()
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        logger.debug("Config loaded from %s", config_path)
        return BackupConfig.from_dict(data)
    except (json.JSONDecodeError, KeyError) as exc:
        logger.error("Failed to parse config at %s: %s. Resetting to defaults.", config_path, exc)
        return BackupConfig()


def save_config(config: BackupConfig) -> bool:
    """Save backup config to JSON.  Returns True on success."""
    try:
        Config.ensure_directories()
        config_path = _config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps(config.to_dict(), indent=4), encoding="utf-8"
        )
        logger.debug("Config saved to %s", config_path)
        return True
    except OSError as exc:
        logger.error("Failed to save backup config: %s", exc)
        return False


def update_destination(config: BackupConfig, new_destination: str) -> BackupConfig:
    """Update the saved destination path and persist."""
    config.last_destination_path = new_destination
    save_config(config)
    return config


def add_rclone_remote(config: BackupConfig, storage_name: str, remote_name: str) -> BackupConfig:
    """Add or update an rclone remote and persist."""
    config.add_remote(storage_name, remote_name)
    save_config(config)
    return config
