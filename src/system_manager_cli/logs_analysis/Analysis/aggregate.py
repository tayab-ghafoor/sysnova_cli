from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any


class LogAggregator:
    """Group analyzed data into summaries for downstream correlation."""

    def aggregate(self, analyzed_data: dict[str, Any]) -> dict[str, Any]:
        records = analyzed_data.get('records', [])
        by_level = dict(Counter(record.get('level', 'INFO') for record in records))
        by_source = dict(Counter(record.get('source_name', 'unknown') for record in records))
        timeline: defaultdict[str, int] = defaultdict(int)

        for record in records:
            parsed_timestamp = self._parse_timestamp(record.get('timestamp'))
            if not parsed_timestamp:
                continue
            bucket = parsed_timestamp.replace(minute=0, second=0, microsecond=0).isoformat()
            timeline[bucket] += 1

        top_patterns = [
            {
                'pattern': item.get('pattern', '<unknown>'),
                'count': item.get('count', 0),
                'sources': item.get('sources', []),
            }
            for item in analyzed_data.get('patterns', [])[:5]
        ]

        return {
            **analyzed_data,
            'groups': {
                'by_level': by_level,
                'by_source': by_source,
                'timeline': dict(sorted(timeline.items())),
                'top_patterns': top_patterns,
            },
        }

    @staticmethod
    def _parse_timestamp(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
