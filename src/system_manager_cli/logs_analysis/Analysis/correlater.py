from __future__ import annotations

from typing import Any


class LogCorrelater:
    """Identify relationships between aggregated log signals."""

    def correlate(self, aggregated_data: dict[str, Any]) -> dict[str, Any]:
        relationships = []

        for pattern in aggregated_data.get('patterns', []):
            sources = pattern.get('sources', [])
            levels = pattern.get('levels', {})
            count = pattern.get('count', 0)
            if len(sources) > 1:
                relationships.append(
                    {
                        'type': 'multi_source_pattern',
                        'description': f"Pattern appears across {len(sources)} sources",
                        'pattern': pattern.get('pattern', '<unknown>'),
                        'evidence': {'sources': sources, 'count': count},
                    }
                )
            if count >= 10 and (levels.get('ERROR', 0) or levels.get('CRITICAL', 0)):
                relationships.append(
                    {
                        'type': 'repeated_error_pattern',
                        'description': 'A recurring error-like pattern appears frequently',
                        'pattern': pattern.get('pattern', '<unknown>'),
                        'evidence': {'count': count, 'levels': levels},
                    }
                )

        timeline = aggregated_data.get('groups', {}).get('timeline', {})
        busiest_period = None
        if timeline:
            period, count = max(timeline.items(), key=lambda item: item[1])
            busiest_period = {'period': period, 'count': count}

        return {
            **aggregated_data,
            'relationships': relationships,
            'correlation_summary': {
                'relationship_count': len(relationships),
                'busiest_period': busiest_period,
            },
        }
