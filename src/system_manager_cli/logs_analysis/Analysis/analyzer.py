from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from ...core.Exception import LogAnalysisError


class LogAnalyzer:
    """Analyze cleaned log records for patterns and metrics."""

    def analyze(self, cleaned_data: dict[str, Any]) -> dict[str, Any]:
        records = cleaned_data.get('records', [])
        if not records:
            raise LogAnalysisError('No log records available for analysis.')

        annotated_records = []
        pattern_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        level_counts: Counter[str] = Counter()
        error_samples = []
        warning_samples = []
        timestamps = []

        for record in records:
            normalized = self._normalize_message(record.get('clean_message', ''))
            annotated = {**record, 'normalized_message': normalized}
            annotated_records.append(annotated)
            pattern_groups[normalized].append(annotated)
            level = annotated.get('level', 'INFO')
            level_counts[level] += 1
            if level in {'ERROR', 'CRITICAL'} and len(error_samples) < 5:
                error_samples.append(annotated['clean_message'])
            if level == 'WARN' and len(warning_samples) < 5:
                warning_samples.append(annotated['clean_message'])
            parsed_timestamp = self._parse_timestamp(annotated.get('timestamp'))
            if parsed_timestamp:
                timestamps.append(parsed_timestamp)

        patterns = []
        for pattern, grouped_records in sorted(pattern_groups.items(), key=lambda item: len(item[1]), reverse=True):
            patterns.append(
                {
                    'pattern': pattern,
                    'count': len(grouped_records),
                    'levels': dict(Counter(item.get('level', 'INFO') for item in grouped_records)),
                    'sources': sorted({item.get('source_name', 'unknown') for item in grouped_records}),
                    'sample_messages': [item.get('clean_message', '') for item in grouped_records[:3]],
                }
            )

        total_records = len(annotated_records)
        error_count = level_counts.get('ERROR', 0) + level_counts.get('CRITICAL', 0)
        warning_count = level_counts.get('WARN', 0)
        metrics = {
            'files_scanned': len(cleaned_data.get('files', [])),
            'records_processed': total_records,
            'error_count': error_count,
            'warning_count': warning_count,
            'critical_count': level_counts.get('CRITICAL', 0),
            'error_rate': round(error_count / total_records, 4) if total_records else 0.0,
            'levels': dict(level_counts),
            'time_range': self._time_range(timestamps),
        }

        return {
            **cleaned_data,
            'records': annotated_records,
            'metrics': metrics,
            'patterns': patterns[:10],
            'samples': {
                'error_examples': error_samples,
                'warning_examples': warning_samples,
            },
        }

    @staticmethod
    def _normalize_message(message: str) -> str:
        normalized = message.lower()
        normalized = re.sub(r'\b[0-9a-f]{8,}\b', '<hex>', normalized)
        normalized = re.sub(r'\b\d+\b', '<num>', normalized)
        return normalized.strip() or '<empty-message>'

    @staticmethod
    def _parse_timestamp(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    @staticmethod
    def _time_range(timestamps: list[datetime]) -> dict[str, str] | None:
        if not timestamps:
            return None
        return {
            'start': min(timestamps).isoformat(),
            'end': max(timestamps).isoformat(),
        }
