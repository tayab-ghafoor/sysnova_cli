"""AI Log Analyzer — sends top critical/error issues to Anthropic API.

Upgraded version:
- Uses classified issue_type from IssueClassifier for smarter prompts
- Health context is injected into prompt when relevant
- Structured JSON output with strict validation
- Per-issue-type prompt templates (memory → RAM context, timeout → CPU context)
- Deduplication by issue_type to avoid sending identical prompts
- Graceful degradation — original data returned unchanged on any failure

Architecture Rules:
- Only called by app.py (never by CLI directly)
- Stateless: no file I/O, no side effects
- Returns enriched pipeline_result dict
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from ...ulits.logger import get_logger

logger = get_logger(__name__)

MAX_AI_ISSUES = 5

# ── Issue-type → relevant health metric mapping ───────────────────────
_HEALTH_METRIC_MAP: dict[str, list[str]] = {
    "memory":   ["memory_percent", "memory_available_mb"],
    "timeout":  ["cpu_percent"],
    "disk":     ["disk_used_pct", "disk_free_gb"],
    "database": ["memory_percent", "cpu_percent"],
    "performance": ["cpu_percent", "memory_percent"],
    "network":  [],
    "runtime":  [],
    "authentication": [],
    "startup":  [],
}

# ── Prompt templates per issue type ──────────────────────────────────
_PROMPT_INTRO = (
    "You are a senior SRE / DevOps engineer.\n"
    "Analyze the log anomaly below and respond ONLY with valid JSON "
    "(no markdown fences, no extra text) with exactly these keys:\n"
    "  \"error_summary\"      – one plain-English sentence\n"
    "  \"likely_root_cause\"  – 2-3 sentences on the most probable cause\n"
    "  \"actionable_fix\"     – a JSON array of strings, where each string is one concrete remediation step\n"
    "  \"priority\"           – one of: critical / high / medium / low\n\n"
)

_PROMPT_HEALTH_SECTION = (
    "Relevant system health at time of analysis:\n{health_lines}\n\n"
)

_PROMPT_BODY = (
    "Issue type    : {issue_type}\n"
    "Severity      : {severity}\n"
    "Frequency     : {count} occurrence(s)\n"
    "Description   : {description}\n"
    "Log samples   :\n{samples}\n"
    "Affected sources: {sources}\n"
)


def _build_prompt(
    anomaly: dict[str, Any],
    health_context: dict[str, Any] | None,
) -> str:
    issue_type = anomaly.get("type", "unknown")
    severity   = anomaly.get("severity", "unknown")
    description = anomaly.get("description", "")
    evidence   = anomaly.get("evidence", {})
    samples    = anomaly.get("samples", [])
    sources    = anomaly.get("sources", [])
    count      = evidence.get("count", evidence.get("critical_count", 1))

    samples_text = "\n".join(f"  [{i+1}] {s}" for i, s in enumerate(samples[:3]))
    if not samples_text:
        samples_text = "  (no sample messages available)"

    sources_text = ", ".join(sources[:5]) if sources else "unknown"

    health_section = ""
    if health_context:
        relevant_keys = _HEALTH_METRIC_MAP.get(issue_type, [])
        lines = []
        for key in relevant_keys:
            val = health_context.get(key)
            if val is not None:
                label = key.replace("_", " ").title()
                lines.append(f"  {label}: {val}")
        if lines:
            health_section = _PROMPT_HEALTH_SECTION.format(
                health_lines="\n".join(lines)
            )

    return (
        _PROMPT_INTRO
        + health_section
        + _PROMPT_BODY.format(
            issue_type=issue_type,
            severity=severity,
            count=count,
            description=description,
            samples=samples_text,
            sources=sources_text,
        )
    )


class AILogAnalyzer:
    """Enrich critical log issues with AI-powered root-cause analysis."""

    def __init__(self):
        self._api_available: bool | None = None

    # ── Public ────────────────────────────────────────────────────────

    def enrich(
        self,
        pipeline_result: dict[str, Any],
        health_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self._check_api_available():
            logger.warning("Anthropic API key not found — skipping AI enrichment.")
            pipeline_result["ai_solutions"] = []
            pipeline_result["ai_available"] = False
            return pipeline_result

        top_issues = self._pick_top_issues(pipeline_result)
        if not top_issues:
            pipeline_result["ai_solutions"] = []
            pipeline_result["ai_available"] = True
            return pipeline_result

        solutions = []
        for issue in top_issues:
            solution = self._analyze_issue(issue, health_context)
            if solution:
                solutions.append(solution)

        pipeline_result["ai_solutions"] = solutions
        pipeline_result["ai_available"] = True
        return pipeline_result

    # ── Internal ──────────────────────────────────────────────────────

    def _check_api_available(self) -> bool:
        if self._api_available is None:
            key = os.environ.get("ANTHROPIC_API_KEY", "")
            self._api_available = bool(key and not key.startswith("your_"))
        return self._api_available

    def _pick_top_issues(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Return up to MAX_AI_ISSUES anomalies.
        Enriches each anomaly with sample messages from classified records
        so the AI receives concrete log text.
        """
        anomalies = result.get("anomalies", [])
        severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}

        # Build a quick lookup: issue_type → sample messages
        samples_by_type: dict[str, list[str]] = {}
        for entry in result.get("issue_summary", []):
            samples_by_type[entry["issue_type"]] = entry.get("samples", [])

        sources_by_type: dict[str, list[str]] = {}
        for entry in result.get("issue_summary", []):
            sources_by_type[entry["issue_type"]] = entry.get("sources", [])

        sorted_anomalies = sorted(
            anomalies,
            key=lambda a: severity_rank.get(a.get("severity", "low"), 0),
            reverse=True,
        )

        # Only critical/high for AI
        filtered = [
            a for a in sorted_anomalies
            if a.get("severity") in ("critical", "high")
        ]

        # Deduplicate by issue type (prefer anomaly type that maps to classified issues)
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for a in filtered:
            issue_type = a.get("type", "")
            if issue_type not in seen:
                seen.add(issue_type)
                # Inject samples + sources from IssueClassifier if available
                enriched = dict(a)
                if issue_type in samples_by_type:
                    enriched["samples"] = samples_by_type[issue_type]
                    enriched["sources"] = sources_by_type.get(issue_type, [])
                unique.append(enriched)
            if len(unique) >= MAX_AI_ISSUES:
                break

        return unique

    def _analyze_issue(
        self,
        anomaly: dict[str, Any],
        health_context: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        import urllib.request

        prompt  = _build_prompt(anomaly, health_context)
        payload = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 600,
            "messages": [{"role": "user", "content": prompt}],
        }).encode("utf-8")

        try:
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": os.environ.get("ANTHROPIC_API_KEY", ""),
                    "anthropic-version": "2023-06-01",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))

            raw_text = ""
            for block in body.get("content", []):
                if block.get("type") == "text":
                    raw_text += block.get("text", "")

            # Strip markdown fences if present
            raw_text = re.sub(r"```(?:json)?|```", "", raw_text).strip()
            ai_data  = json.loads(raw_text)

            # Validate required keys
            required = {"error_summary", "likely_root_cause", "actionable_fix", "priority"}
            if not required.issubset(ai_data.keys()):
                logger.warning(
                    "AI response missing keys for '%s': got %s",
                    anomaly.get("type"), list(ai_data.keys()),
                )
                return None

            return {
                "issue_type":        anomaly.get("type", "unknown"),
                "severity":          anomaly.get("severity", "unknown"),
                "error_summary":     str(ai_data["error_summary"])[:300],
                "likely_root_cause": str(ai_data["likely_root_cause"])[:500],
                "actionable_fix":    ai_data["actionable_fix"],
                "priority":          ai_data.get("priority", anomaly.get("severity", "high")),
                "health_relevant":   bool(
                    _HEALTH_METRIC_MAP.get(anomaly.get("type", ""), [])
                ),
            }

        except json.JSONDecodeError as exc:
            logger.warning(
                "AI response for '%s' was not valid JSON: %s",
                anomaly.get("type"), exc,
            )
            return None
        except Exception as exc:
            logger.warning(
                "AI analysis failed for '%s': %s",
                anomaly.get("type"), exc,
            )
            return None