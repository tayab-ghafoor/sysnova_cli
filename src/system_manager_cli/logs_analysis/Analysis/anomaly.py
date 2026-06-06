from __future__ import annotations

from typing import Any


class AnomalyDetector:
    """Flag unusual or high-risk patterns from correlated analysis data."""

    def detect(self, correlated_data: dict[str, Any]) -> dict[str, Any]:
        metrics = correlated_data.get('metrics', {})
        relationships = correlated_data.get('relationships', [])
        anomalies = []

        total_records = metrics.get('records_processed', 0)
        error_rate = metrics.get('error_rate', 0.0)
        critical_count = metrics.get('critical_count', 0)

        if total_records == 0:
            anomalies.append(
                {
                    'type': 'no_data',
                    'severity': 'low',
                    'description': 'No records were available after the analysis pipeline.',
                }
            )

        if critical_count > 0:
            anomalies.append(
                {
                    'type': 'critical_events',
                    'severity': 'critical',
                    'description': f'{critical_count} critical log entries were detected.',
                    'evidence': {'critical_count': critical_count},
                }
            )

        if error_rate >= 0.2:
            anomalies.append(
                {
                    'type': 'high_error_rate',
                    'severity': 'high',
                    'description': f'Error rate is elevated at {error_rate:.1%}.',
                    'evidence': {'error_rate': error_rate},
                }
            )
        elif error_rate >= 0.1:
            anomalies.append(
                {
                    'type': 'moderate_error_rate',
                    'severity': 'medium',
                    'description': f'Error rate is notable at {error_rate:.1%}.',
                    'evidence': {'error_rate': error_rate},
                }
            )

        busiest_period = correlated_data.get('correlation_summary', {}).get('busiest_period')
        if busiest_period and busiest_period.get('count', 0) >= max(20, int(total_records * 0.25)):
            anomalies.append(
                {
                    'type': 'traffic_spike',
                    'severity': 'medium',
                    'description': 'A concentrated burst of log activity was detected.',
                    'evidence': busiest_period,
                }
            )

        for relationship in relationships:
            if relationship.get('type') == 'multi_source_pattern':
                anomalies.append(
                    {
                        'type': 'cross_source_issue',
                        'severity': 'medium',
                        'description': relationship.get('description', 'Pattern spans multiple sources.'),
                        'evidence': relationship.get('evidence', {}),
                    }
                )
            elif relationship.get('type') == 'repeated_error_pattern':
                anomalies.append(
                    {
                        'type': 'recurring_error',
                        'severity': 'high',
                        'description': relationship.get('description', 'Repeated error pattern detected.'),
                        'evidence': relationship.get('evidence', {}),
                    }
                )

        return {
            **correlated_data,
            'anomalies': anomalies,
        }
