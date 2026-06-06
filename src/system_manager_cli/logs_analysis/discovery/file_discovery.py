"""File Discovery Module for Logs Analysis System

Responsibility:
    Find relevant log files in specified directory

Key Features:
    - Extension filtering (.log, .txt, .out, .err, .json files)
    - File size filtering (ignores files >50MB)
    - Ignores hidden/system folders
    - Safe error handling with clear exceptions

Architecture Rules:
    ✓ No parsing, classification, or AI logic
    ✓ No dependency on orchestrator
    ✓ Testable in isolation
    ✓ Returns raw data (file paths only)

Design note on recency filtering:
    This module does NOT filter by modification time.
    Deciding what counts as "recent" is a caller concern, not a
    discovery concern.  Scheduled tasks run at fixed times and
    cannot guarantee logs were written in any particular window.
    Pass the returned list through your own time filter if needed.
"""

from pathlib import Path
from typing import List

# Matches the extensions accepted by Analysis/reader.py so both
# discovery implementations stay in sync.  If you need to change
# the allowed set, change it here — reader.py imports this constant.
ALLOWED_EXTENSIONS: frozenset[str] = frozenset({
    ".log", ".txt", ".out", ".err", ".json"
})

MAX_FILE_SIZE_MB    = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


def discover_logs(directory: str) -> List[str]:
    """
    Discover log files in the specified directory.

    Applies two filters only:
      1. File extension must be in ALLOWED_EXTENSIONS
      2. File size must be ≤ 50 MB

    Recency filtering is intentionally omitted — see module docstring.

    Args:
        directory (str): Path to search for log files (top-level only,
                         no recursion into sub-directories).

    Returns:
        List[str]: Absolute paths to discovered log files, sorted
                   alphabetically for deterministic ordering.

    Raises:
        TypeError:          If directory is not a string.
        FileNotFoundError:  If directory doesn't exist.
        NotADirectoryError: If path is not a directory.
        PermissionError:    If unable to access directory.

    Example:
        >>> logs = discover_logs("/var/log")
        >>> for log_path in logs:
        ...     print(log_path)
    """
    # ----------------------------------------------------------------
    # INPUT VALIDATION
    # ----------------------------------------------------------------
    if not isinstance(directory, str):
        raise TypeError(
            f"directory must be a string, got {type(directory).__name__}"
        )

    path = Path(directory)

    if not path.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    if not path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {directory}")

    # ----------------------------------------------------------------
    # FILE DISCOVERY
    # ----------------------------------------------------------------
    discovered_files: List[str] = []

    try:
        for item in path.iterdir():
            try:
                # Skip hidden / system files and folders
                if item.name.startswith("."):
                    continue

                # Top-level files only — no recursion
                if item.is_dir():
                    continue

                # ── Filter 1: Extension ───────────────────────────
                if item.suffix.lower() not in ALLOWED_EXTENSIONS:
                    continue

                # ── Filter 2: File size ───────────────────────────
                try:
                    if item.stat().st_size > MAX_FILE_SIZE_BYTES:
                        continue
                except (OSError, ValueError):
                    continue

                discovered_files.append(str(item.absolute()))

            except (OSError, PermissionError):
                # Skip individual files we cannot access
                continue

    except PermissionError as exc:
        raise PermissionError(
            f"Permission denied accessing directory: {directory}"
        ) from exc
    except OSError as exc:
        raise OSError(f"Error reading directory: {directory}") from exc

    return sorted(discovered_files)