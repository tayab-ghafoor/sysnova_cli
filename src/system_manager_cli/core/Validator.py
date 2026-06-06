from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import List, Tuple

from ..models.backup_result import PathValidationResult
from ..ulits.logger import get_logger          # FIX 1: import get_logger, not the non-existent `logger`
from ..config.config import Config
from .Exception import ConfigurationError, DiskSpaceError, PathError, PermissionError as BackupPermissionError  # FIX 2: alias to avoid shadowing the built-in PermissionError


VALID_PATH_TYPES = {'directory', 'file', 'any'}

# FIX 3: create the module-level logger properly via get_logger
logger = get_logger(__name__, 'validator.log')


def validate_path_exists(path_str: str, path_type: str = 'directory') -> Path:
    """Validate a file-system path and return it as a ``Path`` object."""
    if path_type not in VALID_PATH_TYPES:
        raise PathError(f"Unsupported path type '{path_type}'.")

    path = Path(path_str).expanduser()
    if not path.exists():
        raise PathError(f'Path does not exist: {path_str}')
    if path_type == 'directory' and not path.is_dir():
        raise PathError(f'Path is not a directory: {path_str}')
    if path_type == 'file' and not path.is_file():
        raise PathError(f'Path is not a file: {path_str}')
    return path


def validate_path_readable(path: Path) -> None:
    """Ensure a path can be read."""
    candidate = path if path.exists() else path.parent
    if not os.access(candidate, os.R_OK):
        raise BackupPermissionError(f'No read permission for path: {path}')  # FIX 2 applied


def validate_path_writable(path: Path) -> None:
    """Ensure a path can be written to."""
    candidate = path if path.exists() else path.parent
    if not os.access(candidate, os.W_OK):
        raise BackupPermissionError(f'No write permission for path: {path}')  # FIX 2 applied


def validate_disk_space(path: Path, required_bytes: int) -> None:
    """Ensure enough free space is available for an operation."""
    usage = shutil.disk_usage(path)
    if usage.free < required_bytes:
        raise DiskSpaceError(
            f'Insufficient disk space at {path}. '
            f'Required {required_bytes} bytes, available {usage.free} bytes.'
        )


def validate_folder_not_empty(path: Path) -> None:
    """Ensure a directory contains at least one entry."""
    if not any(path.iterdir()):
        raise PathError(f'Folder is empty: {path}')


def validate_config_email() -> None:
    """Ensure outbound email configuration is present."""
    missing = [
        name
        for name in ('EMAIL_SENDER', 'EMAIL_PASSWORD')
        if not getattr(Config, name)
    ]
    if missing:
        raise ConfigurationError(f'Missing email configuration: {", ".join(missing)}')


def validate_backup_drive() -> Path:
    """Ensure the configured backup destination exists and is writable."""
    Config.ensure_directories()
    backup_drive = Path(Config.BACKUP_DRIVE)
    backup_drive.mkdir(parents=True, exist_ok=True)
    validate_path_writable(backup_drive)
    return backup_drive


def get_folder_size(path: Path) -> int:
    """Return the size of a file or directory in bytes."""
    if path.is_file():
        return path.stat().st_size

    total = 0
    for item in path.rglob('*'):
        if item.is_file():
            total += item.stat().st_size
    return total


def validate_paths(raw_input: str) -> Tuple[List[PathValidationResult], bool]:
    """
    Parse comma-separated paths and validate each one.

    Returns:
        (results, all_valid)
        results   — list of PathValidationResult for each path
        all_valid — True only if every path exists
    """
    paths = [p.strip() for p in raw_input.split(",") if p.strip()]
    results: List[PathValidationResult] = []

    for path in paths:
        exists = os.path.exists(path)
        if exists:
            logger.debug(f"Path verified: {path}")
            results.append(PathValidationResult(path=path, exists=True))
        else:
            logger.warning(f"Path not found: {path}")
            results.append(PathValidationResult(
                path=path,
                exists=False,
                error="Path doesn't exist or is incorrect",
            ))

    all_valid = all(r.exists for r in results)
    return results, all_valid


def validate_single_path(path: str) -> PathValidationResult:
    """Validate a single path."""
    path = path.strip()
    exists = os.path.exists(path)
    if exists:
        logger.debug(f"Destination path verified: {path}")
        return PathValidationResult(path=path, exists=True)
    else:
        logger.warning(f"Destination path not found: {path}")
        return PathValidationResult(
            path=path,
            exists=False,
            error="Path doesn't exist or is incorrect",
        )