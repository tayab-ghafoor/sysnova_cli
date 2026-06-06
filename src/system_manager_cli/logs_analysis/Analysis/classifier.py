"""Issue Classifier — classify log records into typed issue buckets.

New pipeline stage inserted between scanner and scrubber.
Classifies each record into a known issue type and tracks frequency.

Architecture Rules:
- Only called by app.py via the pipeline
- Stateless: receives scanned data, returns classified data
- No file I/O, no CLI output
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any


# ── Classification rules ──────────────────────────────────────────────
# Each entry: (issue_type, severity_boost, [regex_patterns])
_RULES: list[tuple[str, str, list[re.Pattern]]] = [
    ("memory", "high", [
        re.compile(r'\b(out\s*of\s*memory|oom|memory\s*leak|heap\s*space|malloc\s*fail'
                   r'|cannot\s*allocate|memory\s*exhausted)\b', re.IGNORECASE),
    ]),
    ("timeout", "medium", [
        re.compile(r'\b(timed?\s*out|connection\s*timeout|read\s*timeout|write\s*timeout'
                   r'|deadline\s*exceeded|request\s*timeout)\b', re.IGNORECASE),
    ]),
    ("network", "medium", [
        re.compile(r'\b(connection\s*refused|network\s*unreachable|no\s*route\s*to\s*host'
                   r'|dns\s*resolution|socket\s*error|econnrefused|econnreset'
                   r'|broken\s*pipe)\b', re.IGNORECASE),
    ]),
    ("authentication", "high", [
        re.compile(r'\b(auth(entication)?\s*(fail|error|denied)|unauthorized|forbidden'
                   r'|invalid\s*(token|credential|password|key)|permission\s*denied'
                   r'|access\s*denied|401|403)\b', re.IGNORECASE),
    ]),
    ("disk", "high", [
        re.compile(r'\b(disk\s*full|no\s*space\s*left|i/?o\s*error|read[-\s]only\s*file'
                   r'|filesystem\s*(full|error)|quota\s*exceeded|enospc)\b', re.IGNORECASE),
    ]),
    ("database", "high", [
        re.compile(r'\b(sql\s*error|database\s*(error|down|unreachable|timeout)'
                   r'|query\s*fail|deadlock|connection\s*pool\s*(exhausted|full)'
                   r'|too\s*many\s*connections|duplicate\s*key)\b', re.IGNORECASE),
    ]),
    ("runtime", "medium", [
        re.compile(r'\b(null\s*pointer|nullpointerexception|index\s*out\s*of\s*(range|bounds)'
                   r'|stack\s*overflow|segmentation\s*fault|sigsegv|assertion\s*fail'
                   r'|unhandled\s*exception|traceback|panic:)\b', re.IGNORECASE),
    ]),
    ("startup", "medium", [
        re.compile(r'\b(failed\s*to\s*start|startup\s*(fail|error)|initialization\s*error'
                   r'|bootstrap\s*fail|cannot\s*bind|address\s*already\s*in\s*use)\b',
                   re.IGNORECASE),
    ]),
    ("performance", "low", [
        re.compile(r'\b(slow\s*query|high\s*cpu|cpu\s*usage|latency\s*(high|spike)'
                   r'|response\s*time\s*exceeded|throughput\s*degraded|bottleneck)\b',
                   re.IGNORECASE),
    ]),
]

_UNKNOWN = "unknown"


def _classify_message(message: str) -> str:
    """Return the first matching issue type or 'unknown'."""
    for issue_type, _severity, patterns in _RULES:
        for pattern in patterns:
            if pattern.search(message):
                return issue_type
    return _UNKNOWN


class IssueClassifier:
    """Classify scanned records by issue type and build a frequency map."""

    def classify(self, scanned_data: dict[str, Any]) -> dict[str, Any]:
        records = scanned_data.get("records", [])
        classified_records: list[dict[str, Any]] = []

        type_counts: Counter[str] = Counter()
        type_samples: defaultdict[str, list[str]] = defaultdict(list)
        type_sources: defaultdict[str, set[str]] = defaultdict(set)

        for record in records:
            level = record.get("level", "INFO")
            # Only classify ERROR / CRITICAL / WARN records — ignore INFO/DEBUG noise
            if level not in ("ERROR", "CRITICAL", "WARN", "WARNING"):
                classified_records.append({**record, "issue_type": _UNKNOWN})
                continue

            text = record.get("message", "") or record.get("raw_text", "")
            issue_type = _classify_message(text)

            type_counts[issue_type] += 1
            source = record.get("source_name", "unknown")
            type_sources[issue_type].add(source)
            if len(type_samples[issue_type]) < 3:
                clean = record.get("clean_message", text)[:200]
                if clean:
                    type_samples[issue_type].append(clean)

            classified_records.append({**record, "issue_type": issue_type})

        # Build issue summary sorted by frequency
        issue_summary = [
            {
                "issue_type": itype,
                "count": count,
                "sources": sorted(type_sources[itype]),
                "samples": type_samples[itype],
            }
            for itype, count in type_counts.most_common()
            if itype != _UNKNOWN
        ]

        return {
            **scanned_data,
            "records": classified_records,
            "issue_summary": issue_summary,
            "classification_counts": dict(type_counts),
        }