"""Settings manager — global configuration without tight coupling."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional
from system_manager_cli.config.config import Config
from system_manager_cli.core.Exception import CliException
from system_manager_cli.ulits.logger import get_logger

logger = get_logger(__name__)


class SettingsError(CliException):
    """Raised for settings-related errors."""


class SettingsManager:
    """Manages global application settings with file persistence."""

    def __init__(self, settings_file: Optional[str] = None):
        self.logger       = logger
        self.settings_file = settings_file or self._get_default_settings_file()
        self._settings: Dict[str, Any] = {}
        self._load_settings()

    # â”€â”€ File location â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _get_default_settings_file(self) -> str:
        # Store settings in the writable app data directory under 'data'.
        Config.ensure_directories()
        return str(Config.DATA_DIR / "settings.json")

    # â”€â”€ Load / Save â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _load_settings(self) -> None:
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                # Deep-merge defaults with file (so new keys appear without wiping saved values)
                defaults = self._get_default_settings()
                self._deep_merge(defaults, loaded)
                self._settings = defaults
            else:
                self._settings = self._get_default_settings()
                self._save_settings()
        except Exception as exc:
            self.logger.warning("Failed to load settings: %s", exc)
            self._settings = self._get_default_settings()

    def _save_settings(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            self.logger.error("Failed to save settings: %s", exc)
            raise SettingsError(f"Failed to save settings: {exc}")

    # â”€â”€ Defaults â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _get_default_settings(self) -> Dict[str, Any]:
        return {
            "app": {
                "name":      "SysNova",
                "version":   "1.0.0",
                "debug":     False,
                "log_level": "INFO",
            },
            "backup": {
                "default_type":       "incremental",
                "compression":        True,
                "retention_days":     30,
                "max_backup_size_mb": 1000,
            },
            "analysis": {
                "enable_anomaly_detection": True,
                "log_retention_days":       7,
                "max_log_size_mb":          100,
                "max_reports":              10,
                "ai_enabled":               True,
            },
            "notifications": {
                "email_enabled":  False,
                "email_server":   "",
                "email_port":     587,
                "email_username": "",
                "email_password": "",
                "alert_email":    "",
            },
            "security": {
                "session_timeout_minutes":    60,
                "max_login_attempts":         3,
                "password_min_length":        8,
                "require_email_verification": True,
            },
            "ui": {
                "theme":       "default",
                "language":    "en",
                "date_format": "YYYY-MM-DD",
                "time_format": "HH:mm:ss",
            },
            # â† NEW: File Organizer settings
            "file_organizer": {
                "delete_temp_permanently": False,
            },
        }

    # â”€â”€ Public API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value via dot-separated key (e.g. 'file_organizer.delete_temp_permanently')."""
        keys  = key.split(".")
        value = self._settings
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any) -> None:
        """Set a value via dot-separated key and persist immediately."""
        keys     = key.split(".")
        settings = self._settings
        for k in keys[:-1]:
            if k not in settings or not isinstance(settings[k], dict):
                settings[k] = {}
            settings = settings[k]
        settings[keys[-1]] = value
        self._save_settings()

    def get_section(self, section: str) -> Dict[str, Any]:
        return self._settings.get(section, {})

    def set_section(self, section: str, values: Dict[str, Any]) -> None:
        if section not in self._settings:
            self._settings[section] = {}
        self._settings[section].update(values)
        self._save_settings()

    def reset_section(self, section: str) -> None:
        defaults = self._get_default_settings()
        if section in defaults:
            self._settings[section] = defaults[section].copy()
            self._save_settings()
        else:
            raise SettingsError(f"Unknown section: {section}")

    def reset_all(self) -> None:
        self._settings = self._get_default_settings()
        self._save_settings()

    def get_all_settings(self) -> Dict[str, Any]:
        return self._settings.copy()

    def validate_settings(self) -> Dict[str, Any]:
        issues = []
        if self.get("notifications.email_enabled"):
            for s in ["notifications.email_server", "notifications.email_username",
                      "notifications.email_password", "notifications.alert_email"]:
                if not self.get(s):
                    issues.append(f"Missing required email setting: {s}")
        if self.get("security.password_min_length", 0) < 6:
            issues.append("Password minimum length should be at least 6 characters")
        if self.get("backup.retention_days", 0) < 1:
            issues.append("Backup retention days should be at least 1")
        return {"valid": len(issues) == 0, "issues": issues}

    def export_settings(self, file_path: str) -> None:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self._settings, f, indent=2, ensure_ascii=False)

    def import_settings(self, file_path: str, merge: bool = True) -> None:
        with open(file_path, "r", encoding="utf-8") as f:
            imported = json.load(f)
        if merge:
            self._deep_merge(self._settings, imported)
        else:
            self._settings = imported
        self._save_settings()

    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value
