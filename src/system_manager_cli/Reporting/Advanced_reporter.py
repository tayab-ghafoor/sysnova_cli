from __future__ import annotations

from typing import Iterable, Mapping


class AdvancedReporter:
    """Compose structured multi-section text reports."""

    def build_report(self, title: str, sections: Mapping[str, str | Iterable[str]]) -> str:
        lines = [title, '=' * len(title)]
        for heading, content in sections.items():
            lines.append('')
            lines.append(f'{heading}:')
            if isinstance(content, str):
                lines.append(content)
            else:
                lines.extend(str(item) for item in content)
        return '\n'.join(lines)
