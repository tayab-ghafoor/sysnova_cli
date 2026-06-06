from __future__ import annotations

from typing import Any


RECOMMENDATION_MAP = {
    'critical_events': {
        'priority': 'high',
        'title': 'Investigate critical events',
        'action': 'Review the critical log entries first and verify affected services are still healthy.',
    },
    'high_error_rate': {
        'priority': 'high',
        'title': 'Reduce the error rate',
        'action': 'Inspect the most common error patterns and correlate them with the busiest period.',
    },
    'moderate_error_rate': {
        'priority': 'medium',
        'title': 'Monitor rising errors',
        'action': 'Track repeated warnings and errors before they grow into an outage.',
    },
    'traffic_spike': {
        'priority': 'medium',
        'title': 'Review the activity spike',
        'action': 'Check whether the busiest period lines up with deployments, scheduled jobs, or incoming traffic bursts.',
    },
    'cross_source_issue': {
        'priority': 'medium',
        'title': 'Look for a shared dependency',
        'action': 'Because the same pattern appears in multiple sources, inspect shared services or infrastructure first.',
    },
    'recurring_error': {
        'priority': 'high',
        'title': 'Fix the recurring failure',
        'action': 'Start with the repeated error pattern and confirm whether retries or misconfiguration are amplifying it.',
    },
    'no_data': {
        'priority': 'low',
        'title': 'Validate log coverage',
        'action': 'Confirm the selected path contains readable logs and the expected application is writing to them.',
    },
}


class Recommender:
    """Convert detected anomalies into actionable next steps."""

    def recommend(self, anomaly_data: dict[str, Any]) -> dict[str, Any]:
        anomalies = anomaly_data.get('anomalies', [])
        recommendations = []
        seen_titles = set()

        for anomaly in anomalies:
            template = RECOMMENDATION_MAP.get(anomaly.get('type'))
            if not template:
                continue
            title = template['title']
            if title in seen_titles:
                continue
            seen_titles.add(title)
            recommendations.append(
                {
                    'priority': template['priority'],
                    'title': title,
                    'action': template['action'],
                    'based_on': anomaly.get('type'),
                }
            )

        if not recommendations:
            recommendations.append(
                {
                    'priority': 'low',
                    'title': 'Keep monitoring',
                    'action': 'No urgent anomaly was detected. Keep collecting logs and rerun analysis after the next change window.',
                    'based_on': 'healthy_run',
                }
            )

        severity_rank = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
        highest_severity = 'none'
        if anomalies:
            highest_severity = max(
                (anomaly.get('severity', 'low') for anomaly in anomalies),
                key=lambda item: severity_rank.get(item, 0),
            )

        metrics = anomaly_data.get('metrics', {})
        summary = {
            'files_scanned': metrics.get('files_scanned', 0),
            'records_processed': metrics.get('records_processed', 0),
            'anomalies_detected': len(anomalies),
            'highest_severity': highest_severity,
        }

        return {
            'summary': summary,
            'metrics': metrics,
            'anomalies': anomalies,
            'relationships': anomaly_data.get('relationships', []),
            'recommendations': recommendations,
        }
