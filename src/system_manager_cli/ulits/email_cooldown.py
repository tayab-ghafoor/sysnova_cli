"""
email_cooldown.py — Manages cooldown periods for sending emails.

This prevents alert spamming by ensuring that emails of a certain type
to a specific recipient are not sent more frequently than a defined
cooldown period.
"""

import json
import threading
import time
from pathlib import Path
from typing import Dict

class EmailCooldownManager:
    """
    Manages cooldown periods for sending emails to prevent spamming.
    Cooldown data is persisted to a JSON file.
    """
    def __init__(self, cooldown_seconds: int = 300):
        self.cooldown_seconds = cooldown_seconds
        self._cooldown_lock = threading.RLock()
        self._cooldown_data: Dict[str, Dict[str, float]] = self._load_cooldown()

    def _get_cooldown_file(self) -> Path:
        """Return path to cooldown JSON file."""
        try:
            from system_manager_cli.config.config import Config
            return Path(Config.DATA_DIR) / ".email_cooldown.json"
        except ImportError:
            # Fallback for standalone usage or if Config is not yet available
            return Path.home() / ".system_manager_cli" / ".email_cooldown.json"

    def _load_cooldown(self) -> Dict[str, Dict[str, float]]:
        """Load cooldown data from the JSON file."""
        cooldown_file = self._get_cooldown_file()
        if not cooldown_file.exists():
            return {}
        try:
            with open(cooldown_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {rec: {typ: float(ts) for typ, ts in types.items()} for rec, types in data.items()}
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_cooldown(self) -> None:
        """Save cooldown data to the JSON file."""
        cooldown_file = self._get_cooldown_file()
        cooldown_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cooldown_file, "w", encoding="utf-8") as f:
            json.dump(self._cooldown_data, f, indent=2)

    def should_send_email(self, recipient: str, email_type: str) -> bool:
        """Check if an email of this type can be sent to the recipient based on cooldown."""
        if self.cooldown_seconds <= 0: # Cooldown disabled
            return True

        with self._cooldown_lock:
            now = time.time()
            next_allowed = self._cooldown_data.get(recipient, {}).get(email_type, 0)
            if now >= next_allowed:
                self._cooldown_data.setdefault(recipient, {})[email_type] = now + self.cooldown_seconds
                self._save_cooldown()
                return True
            return False