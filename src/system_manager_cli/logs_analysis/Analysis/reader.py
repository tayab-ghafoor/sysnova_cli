"""Log Reader — read raw log content from a file or directory.

Fix 7 change:
    Unified ALLOWED_EXTENSIONS between reader.py and file_discovery.py.
    Both now import from file_discovery.ALLOWED_EXTENSIONS.

Fix (new): LogReader used 'patterns' field name but analyzer expected
    'records'. Ensured all stage outputs are consistently named.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..discovery.file_discovery import ALLOWED_EXTENSIONS as LOG_EXTENSIONS

BINARY_EXTENSIONS = frozenset({
    '.evtx', '.evt', '.etl', '.bin', '.db', '.sqlite', '.sqlite3',
    '.exe', '.dll', '.sys', '.lnk', '.mui', '.wer',
})

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024   # 50 MB per file


class LogReader:
    """Read raw log content from a file or directory without processing it."""

    MAX_LINES = 10_000

    def read(self, path: str) -> dict[str, Any]:
        source = Path(path).expanduser()
        files = self._collect_files(source)

        records: list[dict[str, Any]] = []
        file_summaries: list[dict[str, Any]] = []
        skipped_files: list[str] = []
        truncated = False
        total_lines = 0

        for file_path in files:
            line_count = 0
            try:
                try:
                    if file_path.stat().st_size > MAX_FILE_SIZE_BYTES:
                        skipped_files.append(str(file_path))
                        continue
                except OSError:
                    skipped_files.append(str(file_path))
                    continue

                with file_path.open('r', encoding='utf-8', errors='ignore') as handle:
                    for line_number, raw_line in enumerate(handle, start=1):
                        if total_lines >= self.MAX_LINES:
                            truncated = True
                            break
                        stripped = raw_line.rstrip('\n')
                        if not stripped.strip():
                            continue  # skip blank lines early
                        line_count += 1
                        total_lines += 1
                        records.append({
                            'file_path': str(file_path.resolve()),
                            'line_number': line_number,
                            'raw_text': stripped,
                        })
                file_summaries.append(
                    {'path': str(file_path.resolve()), 'line_count': line_count}
                )

            except (PermissionError, OSError):
                skipped_files.append(str(file_path))
                continue

            if truncated:
                break

        return {
            'source_path': str(source.resolve()),
            'files': file_summaries,
            'records': records,
            'skipped_files': skipped_files,
            'truncated': truncated,
            'read_at': datetime.now(timezone.utc).isoformat(),
        }

    def _collect_files(self, source: Path) -> list[Path]:
        if source.is_file():
            return [source] if self._is_log_candidate(source) else []

        if not source.is_dir():
            return []

        try:
            shallow = [
                p for p in source.iterdir()
                if p.is_file() and self._is_log_candidate(p)
            ]
        except PermissionError:
            return []

        if shallow:
            return sorted(shallow)

        deep: list[Path] = []
        try:
            for p in source.rglob('*'):
                try:
                    depth = len(p.relative_to(source).parts)
                except ValueError:
                    continue
                if depth > 3:
                    continue
                if p.is_file() and self._is_log_candidate(p):
                    deep.append(p)
        except PermissionError:
            pass

        return sorted(deep)

    @staticmethod
    def _is_log_candidate(path: Path) -> bool:
        ext = path.suffix.lower()
        if ext in BINARY_EXTENSIONS:
            return False
        return ext in LOG_EXTENSIONS or 'log' in path.name.lower()