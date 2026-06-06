"""Notifier - Alert and Notification System

Purpose: Trigger alerts and notifications based on analysis results
Part of the analysis pipeline for alerting on anomalies and issues

Responsibilities:
- Receive analysis results from pipeline
- Evaluate conditions for alerts
- Trigger notifications through notification system
- Log alert events

Architecture Rules:
- Only called by app.py or analysis modules
- Returns alert status to app.py (not CLI)
- Uses notifications/ for actual sending
- Stateless evaluation only
"""

import time
from typing import Dict, Any, List
from system_manager_cli.ulits.logger import get_logger

logger = get_logger(__name__)

class Notifier:
    """
    Alert system for analysis pipeline results.

    Evaluates analysis output and triggers appropriate notifications.
    """

    def __init__(self):
        self.logger = logger

    def evaluate_and_notify(self, analysis_results: Dict[str, Any], thresholds: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Evaluate analysis results and trigger notifications if needed.

        Args:
            analysis_results: Results from analysis pipeline
            thresholds: Custom thresholds for alerts (optional)

        Returns:
            Dict containing evaluation results and any alerts triggered
        """
        try:
            self.logger.info("Evaluating analysis results for notifications")

            # Set default thresholds if not provided
            if thresholds is None:
                thresholds = self._get_default_thresholds()

            # Evaluate results against thresholds
            alerts = self._evaluate_thresholds(analysis_results, thresholds)

            # Trigger notifications for alerts
            notification_results = []
            for alert in alerts:
                result = self._trigger_notification(alert)
                notification_results.append(result)

            evaluation_result = {
                "analysis_id": analysis_results.get("id", "unknown"),
                "timestamp": time.time(),
                "alerts_evaluated": len(alerts),
                "notifications_sent": len([r for r in notification_results if r.get("status") == "sent"]),
                "alerts": alerts,
                "notification_results": notification_results
            }

            self.logger.info(f"Notification evaluation complete: {evaluation_result['alerts_evaluated']} alerts, {evaluation_result['notifications_sent']} notifications sent")
            return evaluation_result

        except Exception as e:
            self.logger.error(f"Notification evaluation failed: {str(e)}")
            return {
                "error": str(e),
                "status": "failed",
                "timestamp": time.time()
            }

    def _get_default_thresholds(self) -> Dict[str, Any]:
        """
        Get default alert thresholds.

        Returns:
            Default threshold configuration
        """
        return {
            "cpu_usage_percent": 90.0,
            "memory_usage_percent": 85.0,
            "error_count": 10,
            "anomaly_score": 0.8,
            "disk_usage_percent": 95.0
        }

    def _evaluate_thresholds(self, results: Dict[str, Any], thresholds: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Evaluate results against thresholds to generate alerts.

        Args:
            results: Analysis results
            thresholds: Alert thresholds

        Returns:
            List of alerts that triggered
        """
        alerts = []

        # Check CPU usage
        if "cpu_usage" in results and results["cpu_usage"] > thresholds["cpu_usage_percent"]:
            alerts.append({
                "type": "cpu_high",
                "severity": "warning",
                "message": f"High CPU usage: {results['cpu_usage']}%",
                "value": results["cpu_usage"],
                "threshold": thresholds["cpu_usage_percent"]
            })

        # Check memory usage
        if "memory_usage" in results and results["memory_usage"] > thresholds["memory_usage_percent"]:
            alerts.append({
                "type": "memory_high",
                "severity": "warning",
                "message": f"High memory usage: {results['memory_usage']}%",
                "value": results["memory_usage"],
                "threshold": thresholds["memory_usage_percent"]
            })

        # Check error count
        if "error_count" in results and results["error_count"] > thresholds["error_count"]:
            alerts.append({
                "type": "errors_high",
                "severity": "error",
                "message": f"High error count: {results['error_count']}",
                "value": results["error_count"],
                "threshold": thresholds["error_count"]
            })

        return alerts

    def _trigger_notification(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """
        Trigger a notification for an alert.

        Args:
            alert: Alert information

        Returns:
            Notification result
        """
        try:
            # In real implementation, this would call the notifications module
            # For now, just log the alert
            self.logger.warning(f"ALERT: {alert['message']} (Severity: {alert['severity']})")

            return {
                "alert_type": alert["type"],
                "status": "sent",
                "method": "log",  # Would be "email", "sms", etc. in real implementation
                "timestamp": time.time()
            }

        except Exception as e:
            self.logger.error(f"Failed to send notification for alert {alert['type']}: {str(e)}")
            return {
                "alert_type": alert["type"],
                "status": "failed",
                "error": str(e),
                "timestamp": time.time()
            }

    def get_notification_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent notification history.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of recent notifications
        """
        # Placeholder - in real implementation would query notification database
        return []