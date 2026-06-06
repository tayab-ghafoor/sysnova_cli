from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_LEVEL_PATTERN = re.compile(r'\b(CRITICAL|ERROR|WARNING|WARN|INFO|DEBUG|TRACE)\b', re.IGNORECASE)
_TIMESTAMP_PATTERNS = [
    re.compile(r'^\[(?P<ts>[^\]]+)\]'),
    re.compile(r'^(?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})'),
    re.compile(r'^(?P<ts>[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})'),
]


class LogScanner:
    """Detect source metadata and structure from raw log records."""

    def scan(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        scanned_records = []
        level_counts: Counter[str] = Counter()
        extensions: Counter[str] = Counter()

        for record in raw_data.get('records', []):
            file_path = Path(record['file_path'])
            level = self._detect_level(record['raw_text'])
            timestamp = self._detect_timestamp(record['raw_text'])
            message = self._extract_message(record['raw_text'], level)
            scanned_record = {
                **record,
                'source_name': file_path.name,
                'extension': file_path.suffix.lower() or '<none>',
                'level': level,
                'timestamp': timestamp,
                'message': message,
            }
            scanned_records.append(scanned_record)
            level_counts[level] += 1
            extensions[scanned_record['extension']] += 1

        return {
            **raw_data,
            'records': scanned_records,
            'scan_summary': {
                'levels_detected': dict(level_counts),
                'extensions_detected': dict(extensions),
                'record_count': len(scanned_records),
            },
        }

    def _detect_level(self, raw_text: str) -> str:
        match = _LEVEL_PATTERN.search(raw_text or '')
        if not match:
            return 'INFO'
        level = match.group(1).upper()
        return 'WARN' if level == 'WARNING' else level

    def _detect_timestamp(self, raw_text: str) -> str | None:
        for pattern in _TIMESTAMP_PATTERNS:
            match = pattern.search(raw_text or '')
            if not match:
                continue
            value = match.group('ts')
            parsed = self._parse_timestamp(value)
            if parsed:
                return parsed.isoformat()
        return None

    @staticmethod
    def _parse_timestamp(value: str) -> datetime | None:
        candidates = (
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%b %d %H:%M:%S',
        )
        for fmt in candidates:
            try:
                parsed = datetime.strptime(value, fmt)
                if fmt == '%b %d %H:%M:%S':
                    parsed = parsed.replace(year=datetime.now(timezone.utc).year)
                return parsed
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    @staticmethod
    def _extract_message(raw_text: str, level: str) -> str:
        text = raw_text.strip()
        text = re.sub(r'^\[[^\]]+\]\s*', '', text)
        text = re.sub(r'^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}\s*', '', text)
        text = re.sub(r'^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s*', '', text)
        text = re.sub(rf'^\b{level}\b\s*', '', text, flags=re.IGNORECASE)
        return text or raw_text.strip()
