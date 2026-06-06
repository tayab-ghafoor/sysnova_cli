from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config.config import Config


class JsonReporter:
    """Serialize reporting payloads to JSON for external consumers."""

    def render(self, report: dict[str, Any]) -> str:
        return json.dumps(report, indent=2, default=str)

    def save(self, report: dict[str, Any], prefix: str = 'report', max_reports: int | None = None) -> str:
        Config.ensure_directories()
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        destination = Path(Config.REPORTS_DIR) / f'{prefix}_{timestamp}.json'
        destination.write_text(self.render(report), encoding='utf-8')
        self.cleanup(prefix=prefix, max_reports=max_reports)
        return str(destination.resolve())

    def cleanup(self, prefix: str = 'report', max_reports: int | None = None) -> int:
        """Keep only the newest report files for this prefix."""
        if max_reports is None:
            max_reports = self._configured_max_reports()
        try:
            max_reports = int(max_reports)
        except (TypeError, ValueError):
            max_reports = 10
        if max_reports <= 0:
            return 0

        reports_dir = Path(Config.REPORTS_DIR)
        files = sorted(
            reports_dir.glob(f"{prefix}_*.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        removed = 0
        for old_file in files[max_reports:]:
            try:
                old_file.unlink()
                removed += 1
            except OSError:
                continue
        return removed

    @staticmethod
    def _configured_max_reports() -> int:
        try:
            from ..core.settings_manager import SettingsManager

            return int(SettingsManager().get("analysis.max_reports", 10))
        except Exception:
            return 10



def save_report(report: dict[str, Any]) -> str:
    return JsonReporter().save(report)
