from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import Config


class AppConfig:
    """Read-only application configuration loaded from disk."""

    def __init__(self, config_path: Path | None = None):
        self._config_path = config_path or (Config.PACKAGE_DIR / 'config' / 'configuration.json')
        self._config = self._load()

    def _load(self) -> dict[str, Any]:
        if not self._config_path.exists():
            return {}
        with self._config_path.open('r', encoding='utf-8') as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError('Application configuration must be a JSON object.')
        return data

    def is_valid(self) -> bool:
        return isinstance(self._config, dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def as_dict(self) -> dict[str, Any]:
        return dict(self._config)
