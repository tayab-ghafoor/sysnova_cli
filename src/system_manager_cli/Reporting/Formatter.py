"""Reporting formatters — bridge between domain results and CLI display."""

from __future__ import annotations

from typing import Any

from .Advanced_reporter import AdvancedReporter
from .Dashboard import DashboardBuilder
from .json_reporter import JsonReporter


report_builder    = AdvancedReporter()
dashboard_builder = DashboardBuilder()
json_reporter     = JsonReporter()


def _response(status: str, operation: str, display: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "status":    status,
        "operation": operation,
        "display":   display,
        "data":      data,
    }


class BackupFormatter:
    def format_backup_result(self, backup_result: dict[str, Any]) -> dict[str, Any]:
        metrics = {
            "backup_type":    backup_result.get("backup_type", "unknown"),
            "execution_mode": backup_result.get("execution_mode", "unknown"),
            "file_count":     backup_result.get("file_count", 0),
            "size_bytes":     backup_result.get("size_bytes", 0),
        }
        sections = {
            "Summary": dashboard_builder.build(metrics),
            "Paths": [
                f"- Source: {backup_result.get('source_path', 'n/a')}",
                f"- Backup: {backup_result.get('backup_path', 'n/a')}",
            ],
        }
        display = report_builder.build_report("Backup completed", sections)
        return _response("success", "Backup", display, backup_result)


class AnalysisFormatter:
    def format_analysis(self, analysis_result: dict[str, Any]) -> dict[str, Any]:
        summary = analysis_result.get("summary", {})
        metrics = {
            "files_scanned":      summary.get("files_scanned", 0),
            "records_processed":  summary.get("records_processed", 0),
            "anomalies_detected": summary.get("anomalies_detected", 0),
            "highest_severity":   summary.get("highest_severity", "none"),
        }
        recommendations      = analysis_result.get("recommendations", [])
        recommendation_lines = [
            f"- [{item.get('priority', 'medium').upper()}] {item.get('title', '')}: {item.get('action', '')}".rstrip()
            for item in recommendations
        ] or ["- No immediate action required."]
        sections = {
            "Summary":         dashboard_builder.build(metrics),
            "Recommendations": recommendation_lines,
        }
        display = report_builder.build_report("Log analysis completed", sections)
        return _response("success", "Log analysis", display, analysis_result)


class HealthFormatter:
    def format_health_status(self, health_status: dict[str, Any]) -> dict[str, Any]:
        metrics = {
            "overall_status":   health_status.get("overall_status", "unknown"),
            "disk_used_percent": health_status.get("disk", {}).get("used_percent", "n/a"),
            "config_valid":     health_status.get("config_valid", False),
        }
        warnings = health_status.get("warnings", []) or ["No active warnings."]
        sections = {
            "Summary":  dashboard_builder.build(metrics),
            "Warnings": [f"- {w}" for w in warnings],
        }
        display = report_builder.build_report("Health check completed", sections)
        return _response("success", "Health check", display, health_status)


class AuthFormatter:
    """Format authentication outcomes for the CLI layer.

    Handles both ``success`` (bool) and ``status`` (str) keys because
    different parts of the auth system use different conventions.
    """

    def format_auth_result(self, auth_result: dict[str, Any]) -> dict[str, Any]:
        # Normalise — accept both {"success": True} and {"status": "success"}
        raw_success = auth_result.get("success")
        raw_status  = auth_result.get("status", "")
        is_success  = (raw_success is True) or (raw_status == "success")

        if not is_success:
            msg = (
                auth_result.get("message")
                or auth_result.get("error")
                or "Unknown authentication error."
            )
            display = report_builder.build_report(
                "Authentication failed",
                {"Details": [f"- {msg}"]},
            )
            return _response("error", "Authentication", display, auth_result)

        user = auth_result.get("user", {})
        sections = {
            "User": [
                f"- Email   : {user.get('email', 'n/a')}",
                f"- Username: {user.get('username', 'n/a')}",
                f"- Name    : {user.get('full_name', 'n/a')}",
            ],
            "Session": [f"- Token issued: {bool(auth_result.get('token'))}"],
        }
        display = report_builder.build_report("Authentication successful", sections)
        return _response("success", "Authentication", display, auth_result)


def format_report(report: dict[str, Any]) -> str:
    """Compatibility helper for older callers."""
    return json_reporter.render(report)