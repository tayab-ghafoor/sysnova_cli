from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..Notifications.Emailer import Emailer
from ..config.config import Config
from ..ulits.logger import get_logger
from .Exception import BackupError
from .Validator import (
    get_folder_size,
    validate_backup_drive,
    validate_disk_space,
    validate_path_exists,
)


logger = get_logger(__name__, 'backup_manager.log')


class BackupManager:
    """Core service responsible for creating snapshot-style backups."""

    _IGNORE_PATTERNS = shutil.ignore_patterns(
        '__pycache__', '.git', 'node_modules', 'logs', 'reports'
    )

    def __init__(self, source_path: str | None = None, backup_root: str | Path | None = None):
        self._default_source_path = source_path
        self.backup_root = Path(backup_root) if backup_root else Path(Config.BACKUP_DRIVE)

    def execute_backup(self, target: str | None = None, backup_type: str = 'incremental') -> dict[str, Any]:
        """Create a timestamped backup for a file or directory."""
        source = validate_path_exists(target or self._default_source_path or '', 'any')
        backup_root = validate_backup_drive()
        source_size = get_folder_size(source)
        validate_disk_space(backup_root, max(source_size, 1))

        normalized_type = (backup_type or 'incremental').strip().lower()
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        destination_root = backup_root / normalized_type
        destination_root.mkdir(parents=True, exist_ok=True)
        snapshot_dir = destination_root / f'{source.name}_{timestamp}'

        try:
            if source.is_file():
                snapshot_dir.mkdir(parents=True, exist_ok=False)
                destination = snapshot_dir / source.name
                shutil.copy2(source, destination)
                file_count = 1
            else:
                shutil.copytree(source, snapshot_dir, ignore=self._IGNORE_PATTERNS)
                destination = snapshot_dir
                file_count = sum(1 for item in snapshot_dir.rglob('*') if item.is_file())

            backup_size = get_folder_size(destination)
            result = {
                'success': True,
                'backup_type': normalized_type,
                'execution_mode': 'snapshot-copy',
                'source_path': str(source.resolve()),
                'backup_path': str(destination.resolve()),
                'size_bytes': backup_size,
                'file_count': file_count,
                'created_at': datetime.now(timezone.utc).isoformat(),
            }
            logger.info('Backup completed for %s -> %s', source, destination)
            return result

        except Exception as exc:  # pragma: no cover - defensive wrapper
            logger.error('Backup failed for %s: %s', source, exc, exc_info=True)
            raise BackupError(str(exc)) from exc

    def create_backup(self, compress: bool = False) -> Path:
        """Compatibility wrapper for older callers."""
        result = self.execute_backup(self._default_source_path, 'full')
        return Path(result['backup_path'])

    def get_existing_backups(self) -> list[Path]:
        """Return existing backups sorted from newest to oldest."""
        if not self.backup_root.exists():
            return []
        backups = [path for path in self.backup_root.rglob('*') if path.is_dir()]
        return sorted(backups, key=lambda item: item.stat().st_mtime, reverse=True)

    def list_backups(self) -> list[str]:
        """Return backup paths for display or testing."""
        return [str(path) for path in self.get_existing_backups()]

    def send_backup_email(
        self,
        user_email: str,
        backup_path: str | Path,
        backup_type: str = 'Manual',
    ) -> bool:
        """Send a simple notification after backup completion."""
        emailer = Emailer()
        return emailer.send_alert(
            subject=f'Backup completed ({backup_type})',
            message=f'Backup available at {backup_path}',
            recipient_email=user_email,
        )