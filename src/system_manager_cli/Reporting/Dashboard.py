from __future__ import annotations

from typing import Any, Mapping


class DashboardBuilder:
    """Build compact key-value dashboards for formatted output."""

    def build(self, metrics: Mapping[str, Any]) -> list[str]:
        lines = []
        for key, value in metrics.items():
            label = key.replace('_', ' ').title()
            lines.append(f'- {label}: {value}')
        return lines
