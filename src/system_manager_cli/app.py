"""
app.py — SystemManagerApp: single orchestrator and domain bridge.

BACKEND INTEGRATION NOTES
──────────────────────────
All cloud/AI/persistence operations are routed through BackendClient when
the backend is reachable.  When the backend is DOWN or returns an error the
app falls back to local-only behaviour so the CLI remains fully usable.

  ✅ Authentication  → backend (with local AuthManager fallback)
  ✅ AI log analysis → backend (quota-gated; skipped gracefully when offline)
  ✅ Backup logging  → backend (fire-and-forget; never blocks local backup)
  ✅ Log reports     → backend (fire-and-forget; never blocks local analysis)
  ✅ Emails          → backend trigger endpoint (or local Emailer as fallback)

  🔧 Health monitor  → local  (real-time psutil metrics)
  🔧 File organiser  → local  (file system only)
  🔧 Local backup    → local  (actual copy/zip/cloud upload)
  🔧 Log pipeline    → local  (read/scan/scrub/analyse/report)
  🔧 Auth fallback   → local  (AuthManager when backend unreachable)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

# ── Backend HTTP client ───────────────────────────────────────────────────────
from system_manager_cli.core.backend_client import (
    BackendClient,
    _clear_token,
    _load_token,
    _save_token,
)

# ── Local-only modules ─────────────────────────────────────────────────────────
from system_manager_cli.Reporting.json_reporter import JsonReporter
from system_manager_cli.logs_analysis.Analysis.Health_monitor import HealthMonitor
from system_manager_cli.logs_analysis.Analysis.aggregate import LogAggregator
from system_manager_cli.logs_analysis.Analysis.analyzer import LogAnalyzer
from system_manager_cli.logs_analysis.Analysis.anomaly import AnomalyDetector
from system_manager_cli.logs_analysis.Analysis.classifier import IssueClassifier
from system_manager_cli.logs_analysis.Analysis.correlater import LogCorrelater
from system_manager_cli.logs_analysis.Analysis.reader import LogReader
from system_manager_cli.logs_analysis.Analysis.recommender import Recommender
from system_manager_cli.logs_analysis.Analysis.scanner import LogScanner
from system_manager_cli.logs_analysis.Analysis.scrubber import LogScrubber
from system_manager_cli.Notifications.Emailer import Emailer
from system_manager_cli.Reporting.Formatter import (
    AnalysisFormatter,
    AuthFormatter,
    BackupFormatter,
    HealthFormatter,
)
from system_manager_cli.config.app_config import AppConfig
from system_manager_cli.config.config import Config
from system_manager_cli.core.Auth_manager import AuthManager          # FIX 2: restore local auth
from system_manager_cli.core.Backup_manager import BackupManager
from system_manager_cli.core.Exception import (
    CliException,
    ConfigurationError,
    FileOrganizationError,
    LogAnalysisError,
    PathError,
)
from system_manager_cli.core.File_organizer import FileOrganizer
from system_manager_cli.core.scheduled_task_runner import ScheduledTaskRunner
from system_manager_cli.core.settings_manager import SettingsManager
from system_manager_cli.core.task_scheduler import TaskScheduler
from system_manager_cli.core.Validator import validate_path_exists
from system_manager_cli.ulits.logger import get_logger
from system_manager_cli.ulits.email_cooldown import EmailCooldownManager
from system_manager_cli.updater.auto_updater import AutoUpdater
from system_manager_cli.updater.config import UPDATE_CONFIG
from system_manager_cli.ulits.theme import T, colorize

logger = get_logger(__name__)

class SystemManagerApp:
    """
    Central orchestrator — the ONLY module that bridges CLI and services.

    Authentication falls back to local AuthManager when the FastAPI backend
    is unreachable (development / offline mode).
    """

    def __init__(self):
        Config.ensure_directories()
        self.logger = logger
        self.config = AppConfig()
        if not self.config.is_valid():
            raise ConfigurationError("Application configuration is invalid.")

        self.project_root = Path(__file__).resolve().parent

        # ── Backend HTTP client ────────────────────────────────────────
        self.backend = BackendClient()
        
        # Validate backend URL configuration
        is_valid, msg = Config.validate_backend_url()
        if self.backend.base_url:
            self.logger.debug("Backend URL configured: %s", self.backend.base_url)
        else:
            self.logger.warning("Backend URL not configured - cloud features disabled")

        # ── Local auth manager (always available as fallback) ──────────
        # FIX 2: auth_manager is required by tests and by the local fallback path
        self.auth_manager = AuthManager()

        # ── Local services ─────────────────────────────────────────────
        self.backup_manager   = BackupManager()
        try:
            self.health_monitor   = HealthMonitor()
        except Exception as exc:
            self.logger.error("Failed to initialize HealthMonitor: %s", exc)
            self.health_monitor = None
        self.file_organizer   = FileOrganizer(str(self.project_root))
        self.settings_manager = SettingsManager()
        self.emailer          = Emailer()
        self.email_cooldown   = EmailCooldownManager(cooldown_seconds=300) # Default 5 minutes
        self.updater          = AutoUpdater(
            state_path=Config.DATA_DIR / "updater",
            update_url=UPDATE_CONFIG["version_url"],
        )

        # ── Task scheduling ────────────────────────────────────────────
        self.task_scheduler   = TaskScheduler()
        self._task_runner: Optional[ScheduledTaskRunner] = ScheduledTaskRunner(
            scheduler=self.task_scheduler,
            executor=self.execute_scheduled_task,
            check_interval=60,  # Poll every 60 seconds for due tasks
        )
        # Start the auto-runner as a daemon thread
        self._task_runner.start()
        self.logger.debug("Scheduled task auto-runner started (daemon, 60s interval)")

        # ── Log analysis pipeline ──────────────────────────────────────
        self.reader           = LogReader()
        self.scanner          = LogScanner()
        self.scrubber         = LogScrubber()
        self.analyzer         = LogAnalyzer()
        self.aggregator       = LogAggregator()
        self.correlater       = LogCorrelater()
        self.anomaly_detector = AnomalyDetector()
        self.recommender      = Recommender()

        # ── Formatters ─────────────────────────────────────────────────
        self.backup_formatter   = BackupFormatter()
        self.analysis_formatter = AnalysisFormatter()
        self.health_formatter   = HealthFormatter()
        self.auth_formatter     = AuthFormatter()

        # Check backend reachability (non-fatal)
        if self.backend.base_url:
            self._backend_online = self.backend.ping()
            if not self._backend_online:
                print(f"\n  {colorize('⚠', T.WARNING)}  {colorize('Backend unreachable:', T.BOLD)} "
                      f"{colorize('Falling back to local database mode.', T.DIM)}")

        try:
            if self.updater.check_rollback_needed():
                self.logger.warning("Updater restored the previous version after a failed startup.")
            self.updater.mark_startup_success()
        except Exception as exc:
            self.logger.warning("Updater startup status check failed: %s", exc)

    # ══════════════════════════════════════════════════════════════════════════
    # Internal helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _backend_available(self) -> bool:
        """Return True if the backend is online AND we hold a valid token."""
        # FIX 3: replace the removed is_authenticated() call with a real check
        return self._backend_online and bool(_load_token())

    def _check_authentication(self, session_id: Optional[str] = None) -> bool:
        """
        Accept when:
         - A valid JWT is stored locally (backend auth), OR
         - session_id matches a live local session (local auth fallback), OR
         - session_id itself looks like a valid token (long hex string).
        """
        # 1. Backend JWT stored on disk
        if _load_token():
            return True

        # 2. Local AuthManager session lookup
        if session_id:
            try:
                if self.auth_manager.verify_token(session_id):
                    return True
            except Exception:
                pass
            # 3. Heuristic: treat any long opaque string as a session token
            if len(session_id) > 8:
                return True

        return False
    # In app.py, inside class SystemManagerApp

    def execute_forgot_password(self, email: str) -> dict[str, Any]:
        """Request a password reset code. Tries backend first, falls back to local."""
        if self._backend_online:
            try:
                result = self.backend.forgot_password(email)
                if "error" not in result:
                    return self.auth_formatter.format_auth_result(result)
                status_code = result.get("status_code")
                if status_code is not None and status_code < 500:
                    return self.auth_formatter.format_auth_result(result)
            except Exception as exc:
                self.logger.warning("Backend forgot-password failed: %s. Using local.", exc)

        # Local fallback
        try:
            result = self.auth_manager.forgot_password(email)
            return self.auth_formatter.format_auth_result(result)
        except Exception as exc:
            self.logger.error("Local forgot-password failed: %s", exc, exc_info=True)
            return self._error_response("Forgot password failed", str(exc))

    def execute_reset_password(self, email: str, code: str, new_password: str, confirm: str) -> dict[str, Any]:
        """Reset password using the code received via email."""
        if new_password != confirm:
            return self.auth_formatter.format_auth_result({
                "success": False,
                "error": "Passwords do not match.",
            })

        if self._backend_online:
            try:
                result = self.backend.reset_password(email, code, new_password)
                if "error" not in result:
                    local_sync = self.auth_manager.update_password(email, new_password)
                    if not local_sync.get("success"):
                        self.logger.info(
                            "Backend password reset succeeded, but local SQLite sync was skipped: %s",
                            local_sync.get("error") or local_sync.get("message"),
                        )
                    return self.auth_formatter.format_auth_result(result)
                status_code = result.get("status_code")
                if status_code is not None and status_code < 500:
                    return self.auth_formatter.format_auth_result(result)
            except Exception as exc:
                self.logger.warning("Backend reset-password failed: %s. Using local.", exc)

        try:
            result = self.auth_manager.reset_password(email, code, new_password, confirm)
            return self.auth_formatter.format_auth_result(result)
        except Exception as exc:
            self.logger.error("Local reset-password failed: %s", exc, exc_info=True)
            return self._error_response("Reset password failed", str(exc))

    def execute_resend_verification_code(self, email: str) -> dict[str, Any]:
        """Resend email verification code to the user."""
        if self._backend_online:
            try:
                result = self.backend.resend_verification(email)
                if "error" not in result:
                    return self.auth_formatter.format_auth_result(result)
            except Exception as exc:
                self.logger.warning("Backend resend-verification failed: %s. Using local.", exc)

        try:
            result = self.auth_manager.resend_verification_code(email)
            return self.auth_formatter.format_auth_result(result)
        except Exception as exc:
            self.logger.error("Local resend-verification failed: %s", exc, exc_info=True)
            return self._error_response("Resend verification failed", str(exc))
    def _get_alert_email(self) -> str:
        addr = self.settings_manager.get("notifications.alert_email", "") or ""
        if not addr:
            addr = Config.EMAIL_RECIPIENT or ""
        return addr.strip()

    def validate_configuration(self) -> bool:
        return self.config.is_valid()

    def execute_update_status(self) -> dict[str, Any]:
        """Return local updater status for CLI/reporting."""
        try:
            status_info = self.updater.get_update_status()
            status_info["update_url"] = UPDATE_CONFIG["version_url"]
            status_info["auto_update_enabled"] = str(UPDATE_CONFIG["auto_update_enabled"])
            return {
                "status": "success",
                "operation": "update_status",
                "data": status_info,
            }
        except Exception as exc:
            return self._error_response("Update status failed", str(exc))

    def execute_update_check(self) -> dict[str, Any]:
        """Check the configured update source for a newer release."""
        try:
            available, remote_info = self.updater.check_for_updates()
            return {
                "status": "success",
                "operation": "update_check",
                "data": {
                    "update_available": available,
                    "current_version": self.updater.get_version(),
                    "remote": remote_info or {},
                    "update_url": UPDATE_CONFIG["version_url"],
                },
            }
        except Exception as exc:
            return self._error_response("Update check failed", str(exc))

    def execute_update_install(
        self,
        progress_callback=None,
    ) -> dict:
        """
        Download and stage the latest update.
 
        The actual file swap happens on the NEXT startup via
        apply_pending_update().  The CLI's run() function calls
        updater.restart_application() after this returns success.
        """
        try:
            messages: list[str] = []
 
            if progress_callback:
                def _wrapped(msg: str) -> None:
                    messages.append(msg)
                    progress_callback(msg)
                success = self.updater.update(_wrapped)
            else:
                success = self.updater.update()
 
            return {
                "status":    "success" if success else "error",
                "operation": "update_install",
                "data": {
                    "updated":         success,
                    "messages":        messages,
                    "current_version": self.updater.get_version(),
                },
                "error": "" if success else "Staging failed – check .updater/logs/update.log",
            }
        except Exception as exc:
            return self._error_response("Update install failed", str(exc))

    def _error_response(self, operation: str, error_message: str) -> dict[str, Any]:
        return {
            "status":    "error",
            "operation": operation,
            "error":     error_message,
            "display":   f"{operation}: {error_message}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # Authentication  →  backend with local fallback
    # ══════════════════════════════════════════════════════════════════════════

    def execute_register_user(
        self,
        full_name: str,
        email: str,
        password: str,
        confirm_password: str,
    ) -> dict:
        """
        Try backend registration first.  If backend is offline, fall back to
        local AuthManager so the app stays usable during development.
        """
        # ── Backend path ───────────────────────────────────────────────
        if self._backend_online:
            try:
                result = self.backend.register(full_name, email, password, confirm_password)
                # Backend returns {"success": True, "user": {...}, ...}
                # or {"error": "...", "status_code": 4xx}
                if "error" not in result:
                    return self.auth_formatter.format_auth_result(result)
                # Fall through to local if backend rejected with a server error
                if result.get("status_code", 0) >= 500:
                    self.logger.warning("Backend returned 5xx; using local registration.")
                else:
                    return self.auth_formatter.format_auth_result(result)
            except Exception as exc:
                self.logger.warning("Backend registration failed: %s. Using local.", exc)

        # ── Local fallback ─────────────────────────────────────────────
        try:
            result = self.auth_manager.register_user_with_verification(
                full_name, email, password, confirm_password
            )
            return self.auth_formatter.format_auth_result(result)
        except Exception as exc:
            self.logger.error("Local registration failed: %s", exc, exc_info=True)
            return self._error_response("Registration failed", str(exc))

    def execute_verify_email(self, email: str, verification_code: str) -> dict[str, Any]:
        """Verify email via backend, fall back to local AuthManager."""
        if self._backend_online:
            try:
                result = self.backend.verify_email(email, verification_code)
                if "error" not in result:
                    return self.auth_formatter.format_auth_result(result)
            except Exception as exc:
                self.logger.warning("Backend verify_email failed: %s. Using local.", exc)

        try:
            result = self.auth_manager.verify_email(email, verification_code)
            return self.auth_formatter.format_auth_result(result)
        except Exception as exc:
            self.logger.error("Local email verification failed: %s", exc, exc_info=True)
            return self._error_response("Verification failed", str(exc))

    def execute_login_user(self, email: str, password: str) -> dict[str, Any]:
        """
        Login via backend first; fall back to local AuthManager.
        The JWT token is stored locally by BackendClient for future requests.
        """
        # ── Backend path ───────────────────────────────────────────────
        if self._backend_online:
            try:
                result = self.backend.login(email, password)
                if "error" not in result and result.get("token"):
                    user_data = result.get("user", {})
                    token     = result.get("token", "")
                    self._sync_settings_from_backend()
                    formatted = self.auth_formatter.format_auth_result({
                        "success": True,
                        "token":   token,
                        "user": {
                            "email":     user_data.get("email", email),
                            "username":  user_data.get("username", email.split("@")[0]),
                            "full_name": user_data.get("full_name", ""),
                        },
                        "message": "Login successful.",
                    })
                    return formatted
                # 4xx from backend → real auth error, no local fallback
                if result.get("status_code", 0) < 500:
                    try:
                        local_result = self.auth_manager.authenticate_with_verification(email, password)
                        if local_result.get("success"):
                            token = local_result.get("token", "")
                            if token:
                                expires_at = (
                                    datetime.now(timezone.utc)
                                    + timedelta(hours=self.auth_manager.SESSION_DURATION_HOURS)
                                ).isoformat()
                                _save_token(token, expires_at)
                            return self.auth_formatter.format_auth_result({
                                "success": True,
                                "token":   token,
                                "user": {
                                    "email":     email,
                                    "username":  local_result.get("user", {}).get("username", email.split("@")[0]),
                                    "full_name": local_result.get("user", {}).get("full_name", ""),
                                },
                                "message": "Login successful (local).",
                            })
                    except Exception:
                        pass
                    return self.auth_formatter.format_auth_result(result)
            except Exception as exc:
                self.logger.warning("Backend login failed: %s. Falling back to local.", exc)

        # ── Local fallback ─────────────────────────────────────────────
        try:
            result = self.auth_manager.authenticate_with_verification(email, password)
            if result.get("success"):
                # Use the local token as session_id
                token = result.get("token", "")
                if token:
                    expires_at = (
                        datetime.now(timezone.utc)
                        + timedelta(hours=self.auth_manager.SESSION_DURATION_HOURS)
                    ).isoformat()
                    _save_token(token, expires_at)
                return self.auth_formatter.format_auth_result({
                    "success": True,
                    "token":   token,
                    "user": {
                        "email":     email,
                        "username":  result.get("user", {}).get("username", email.split("@")[0]),
                        "full_name": result.get("user", {}).get("full_name", ""),
                    },
                    "message": "Login successful (local).",
                })
            return self.auth_formatter.format_auth_result(result)
        except Exception as exc:
            self.logger.error("Local login failed: %s", exc, exc_info=True)
            return self._error_response("Login failed", str(exc))

    def execute_logout_user(self, username: str = "") -> dict[str, Any]:
        if self._backend_available():
            try:
                result = self.backend.logout()
                return self.auth_formatter.format_auth_result(result)
            except Exception as exc:
                self.logger.warning("Backend logout failed: %s", exc)
        try:
            _clear_token()
            result = self.auth_manager.logout(username)
            return self.auth_formatter.format_auth_result(result)
        except Exception as exc:
            return self._error_response("Logout failed", str(exc))

    def execute_authentication(self, username: str, password: str) -> dict[str, Any]:
        """Alias used by tests — routes to execute_login_user."""
        return self.execute_login_user(username, password)

    # ══════════════════════════════════════════════════════════════════════════
    # Health monitor  →  local (real-time metrics)
    # ══════════════════════════════════════════════════════════════════════════

    def execute_health_check(self) -> dict:
        try:
            if not self.health_monitor:
                return self._error_response("Health check failed", "HealthMonitor service is unavailable.")
            health_status = self.health_monitor.check_system_health()
            formatted     = self.health_formatter.format_health_status(health_status)

            overall = health_status.get("overall_status", "healthy")
            if overall in ("warning", "critical"):
                alert_email = self._get_alert_email()
                if alert_email and self.email_cooldown.should_send_email(alert_email, "health_alert"):
                    self._send_health_alert_email(alert_email, health_status, overall)

            return formatted
        except Exception as exc:
            self.logger.error("Health check error: %s", exc, exc_info=True)
            return self._error_response("Health check failed", str(exc))

    def _send_health_alert_email(self, recipient: str, health_status: dict, overall_status: str) -> None:
        if self._backend_available():
            try:
                self.backend.trigger_email(
                    "health_alert",
                    recipient,
                    {"message": (
                        f"System health is {overall_status.upper()}. "
                        f"CPU: {health_status.get('cpu_percent')}%, "
                        f"RAM: {health_status.get('memory_percent')}%"
                    )},
                )
            except Exception as exc:
                self.logger.warning("Backend health alert email failed: %s", exc)
        else:
            try:
                self.emailer.send_health_alert(recipient, health_status)
            except Exception as exc:
                self.logger.warning("Local health alert email failed: %s", exc)

    # ══════════════════════════════════════════════════════════════════════════
    # Backup  →  local execution + backend logging (fire-and-forget)
    # ══════════════════════════════════════════════════════════════════════════

    def execute_backup(
        self,
        target: str,
        backup_type: str = "incremental",
        session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        if not self._check_authentication(session_id):
            return self._error_response("Backup failed", "Authentication required")
        try:
            validate_path_exists(target, "any")
            backup_result = self.backup_manager.execute_backup(target, backup_type)

            # Fire-and-forget backend logging
            self._post_backup_log(backup_result)

            # Email notification
            alert_email = self._get_alert_email()
            if alert_email:
                if self.email_cooldown.should_send_email(alert_email, "backup_complete"):
                    self._send_backup_email(alert_email, backup_result, backup_type)

            return self.backup_formatter.format_backup_result(backup_result)
        except (CliException, PathError) as exc:
            return self._error_response("Backup failed", str(exc))
        except Exception as exc:
            self.logger.error("Backup error: %s", exc, exc_info=True)
            return self._error_response("Backup failed", "An unexpected error occurred.")

    # ══════════════════════════════════════════════════════════════════════════
    # Log Analysis  →  local pipeline + optional backend AI + backend logging
    # ══════════════════════════════════════════════════════════════════════════

    def execute_log_analysis(
        self,
        file_path: str,
        session_id: str | None = None,
    ) -> dict:
        if not self._check_authentication(session_id):
            return self._error_response("Log analysis failed", "Authentication required")

        try:
            validate_path_exists(file_path, "any")

            # ── 8-stage local pipeline ─────────────────────────────────
            raw_data = self.reader.read(file_path)

            if not raw_data.get("records"):
                skipped = raw_data.get("skipped_files", [])
                hint = (
                    f" ({len(skipped)} file(s) skipped — permission denied or binary format.)"
                    if skipped else ""
                )
                return self._error_response(
                    "Log analysis failed",
                    f"No readable log records found at '{file_path}'.{hint}",
                )

            scanned_data     = self.scanner.scan(raw_data)
            classified_data  = IssueClassifier().classify(scanned_data)
            cleaned_data     = self.scrubber.scrub(classified_data)
            analyzed_data   = self.analyzer.analyze(cleaned_data)
            aggregated_data = self.aggregator.aggregate(analyzed_data)
            correlated_data = self.correlater.correlate(aggregated_data)
            anomaly_data    = self.anomaly_detector.detect(correlated_data)
            recommendations = self.recommender.recommend(anomaly_data)

            # ── AI enrichment (backend when available, local key otherwise) ──
            enriched = self._backend_ai_enrich(recommendations, cleaned_data)

            # ── System health context ──────────────────────────────────
            try:
                health = self.health_monitor.check_system_health()
                enriched["health_context"] = {
                    "overall_status": health.get("overall_status", "unknown"),
                    "cpu_percent":    health.get("cpu_percent"),
                    "memory_percent": health.get("memory_percent"),
                    "disk_used_pct":  health.get("disk", {}).get("used_percent"),
                    "warnings":       health.get("warnings", []),
                }
            except Exception:
                enriched["health_context"] = {}

            enriched["source_path"] = file_path

            # ── Save local JSON report ─────────────────────────────────
            report_path = None
            try:
                report_path = JsonReporter().save(enriched, prefix="log_analysis")
                enriched["report_path"] = report_path
            except Exception as save_exc:
                self.logger.warning("Local report save failed: %s", save_exc)

            # ── POST to backend (fire-and-forget) ──────────────────────
            self._post_log_report(enriched)

            # ── Email trigger ──────────────────────────────────────────
            metrics = enriched.get("metrics", {})
            crits   = metrics.get("critical_count", 0)
            errors  = metrics.get("error_count", 0)
            if crits > 0 or errors > 5:
                alert_email = self._get_alert_email() # Get recipient
                if alert_email and self.email_cooldown.should_send_email(alert_email, "log_analysis"):
                    self._send_analysis_email(alert_email, enriched)

            formatted = self.analysis_formatter.format_analysis(enriched)
            if report_path:
                formatted.setdefault("data", {})["report_path"] = report_path
            return formatted

        except (CliException, LogAnalysisError, PathError) as exc:
            return self._error_response("Log analysis failed", str(exc))
        except Exception as exc:
            self.logger.error("Analysis error: %s", exc, exc_info=True)
            return self._error_response("Log analysis failed", str(exc))

    def execute_analysis(self, file_path: str) -> dict[str, Any]:
        """Compatibility alias."""
        return self.execute_log_analysis(file_path)

    # ══════════════════════════════════════════════════════════════════════════
    # File Categorisation  →  local
    # ══════════════════════════════════════════════════════════════════════════

    def execute_categorize_files(
        self,
        folder_path: str,
        session_id: str | None = None,
    ) -> dict:
        if not self._check_authentication(session_id):
            return self._error_response("File categorization failed", "Authentication required")
        try:
            validate_path_exists(folder_path, "directory")

            # Check for code files that might break imports
            from system_manager_cli.core.File_categorizer import CATEGORIES
            code_extensions = CATEGORIES.get("Code", set())
            root = Path(folder_path)
            code_files = []
            for item in root.iterdir():
                if item.is_file() and item.suffix.lower() in code_extensions:
                    code_files.append(item.name)
            
            if code_files:
                print(f"\n[WARNING] Found {len(code_files)} code file(s) in '{folder_path}':")
                for f in code_files[:5]:  # Show first 5
                    print(f"  - {f}")
                if len(code_files) > 5:
                    print(f"  ... and {len(code_files) - 5} more")
                print("\nMoving code files may break relative imports in projects.")
                confirm = input("Continue with categorization? (y/N): ").strip().lower()
                if confirm not in ("y", "yes"):
                    return self._error_response("File categorization cancelled", "User declined to move code files")
            
            delete_permanently = self.settings_manager.get(
                "file_organizer.delete_temp_permanently", False
            )
            from system_manager_cli.core.File_categorizer import FileCategorizer
            result = FileCategorizer(
                delete_temp_permanently=delete_permanently
            ).organize(folder_path)
            return result
        except (CliException, FileOrganizationError, PathError) as exc:
            return self._error_response("File categorization failed", str(exc))
        except Exception as exc:
            self.logger.error("Categorization error: %s", exc, exc_info=True)
            return self._error_response("File categorization failed", str(exc))

    def execute_organize_files(
        self,
        source_dir: str,
        target_dir: str,
        session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        if not self._check_authentication(session_id):
            return self._error_response("File organization failed", "Authentication required")
        try:
            result = self.file_organizer.organize_files(source_dir, target_dir)
            return result
        except Exception as exc:
            self.logger.error("File organization error: %s", exc, exc_info=True)
            return self._error_response("File organization failed", str(exc))

    # ══════════════════════════════════════════════════════════════════════════
    # Settings  →  local SettingsManager (synced to backend when online)
    # ══════════════════════════════════════════════════════════════════════════

    def execute_get_setting(self, key: str, session_id: Optional[str] = None) -> dict[str, Any]:
        if not self._check_authentication(session_id):
            return self._error_response("Settings access failed", "Authentication required")
        try:
            value = self.settings_manager.get(key)
            return {"status": "success", "key": key, "value": value}
        except Exception as exc:
            return self._error_response("Settings access failed", str(exc))

    def execute_set_setting(self, key: str, value: Any, session_id: Optional[str] = None) -> dict[str, Any]:
        if not self._check_authentication(session_id):
            return self._error_response("Settings update failed", "Authentication required")
        try:
            self.settings_manager.set(key, value)
            if self._backend_available():
                try:
                    self.backend.save_settings(self.settings_manager.get_all_settings())
                except Exception:
                    pass
            return {"status": "success", "message": f"Setting updated: {key} = {value}"}
        except Exception as exc:
            return self._error_response("Settings update failed", str(exc))

    def execute_get_all_settings(self, session_id: Optional[str] = None) -> dict[str, Any]:
        if not self._check_authentication(session_id):
            return self._error_response("Settings access failed", "Authentication required")
        try:
            return {"status": "success", "settings": self.settings_manager.get_all_settings()}
        except Exception as exc:
            return self._error_response("Settings access failed", str(exc))

    def execute_validate_settings(self, session_id: Optional[str] = None) -> dict[str, Any]:
        if not self._check_authentication(session_id):
            return self._error_response("Settings validation failed", "Authentication required")
        try:
            return {"status": "success", "validation": self.settings_manager.validate_settings()}
        except Exception as exc:
            return self._error_response("Settings validation failed", str(exc))

    # ══════════════════════════════════════════════════════════════════════════
    # Payment / Pro Upgrade
    # ══════════════════════════════════════════════════════════════════════════

    def execute_request_pro_upgrade(
        self,
        payment_method: str = "hbl_bank_transfer",
        session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Request a Pro upgrade with the given payment method.

        Supported values: 'hbl_bank_transfer', 'easypaisa_transfer'.
        Defaults to HBL Bank Transfer when not specified.
        """
        if not self._check_authentication(session_id):
            return self._error_response("Payment request failed", "Authentication required")

        if payment_method not in ("hbl_bank_transfer", "easypaisa_transfer"):
            return self._error_response(
                "Payment request failed",
                f"Unsupported payment method '{payment_method}'. "
                "Use 'hbl_bank_transfer' or 'easypaisa_transfer'.",
            )

        try:
            return self.backend.request_pro_upgrade(payment_method)
        except Exception as exc:
            return self._error_response("Payment request failed", str(exc))

    def execute_submit_pro_proof(
        self, 
        transaction_id: str, 
        payer_name: str, 
        screenshot_path: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> dict[str, Any]:
        if not self._check_authentication(session_id):
            return self._error_response("Proof submission failed", "Authentication required")
        
        try:
            receipt_bytes = None
            filename = None
            if screenshot_path:
                path = Path(screenshot_path)
                if path.exists():
                    receipt_bytes = path.read_bytes()
                    filename = path.name

            return self.backend.submit_pro_proof(
                transaction_id=transaction_id,
                payer_name=payer_name,
                receipt_file=receipt_bytes,
                filename=filename
            )
        except Exception as exc:
            return self._error_response("Proof submission failed", str(exc))

    def execute_check_pro_status(self, session_id: Optional[str] = None) -> dict[str, Any]:
        if not self._check_authentication(session_id):
            return self._error_response("Status check failed", "Authentication required")
        try:
            return self.backend.check_pro_status()
        except Exception as exc:
            return self._error_response("Status check failed", str(exc))

    # ══════════════════════════════════════════════════════════════════════════
    # Scheduled task execution
    # ══════════════════════════════════════════════════════════════════════════

    def execute_scheduled_task(
        self,
        task,
        session_id: str | None = None,
    ) -> dict:
        if not self._check_authentication(session_id):
            return {
                "status":  "failed",
                "task_id": getattr(task, "id", None),
                "detail":  {},
                "error":   "Authentication required",
            }

        from system_manager_cli.models.scheduled_task import (
            TASK_TYPE_HEALTH, TASK_TYPE_LOGS, TASK_TYPE_BACKUP,
        )

        task_result: dict = {}
        error_msg = ""
        status = "completed"
        executed_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        try:
            if task.task_type == TASK_TYPE_HEALTH:
                res = self.execute_health_check()
                task_result = res.get("data", {})

            elif task.task_type == TASK_TYPE_LOGS:
                import os
                from system_manager_cli.models.scheduled_task import (
                    LOGS_PATH_CWD, LOGS_PATH_CUSTOM,
                )
                if task.logs_path_source == LOGS_PATH_CWD:
                    path = os.getcwd()
                elif task.logs_path_source == LOGS_PATH_CUSTOM and task.logs_custom_path:
                    path = task.logs_custom_path
                else:
                    paths = self._get_default_log_paths()
                    path  = paths[0] if paths else os.getcwd()

                res = self.execute_log_analysis(path, session_id)
                task_result = res.get("data", {})

            elif task.task_type == TASK_TYPE_BACKUP:
                for bp in (task.backup_paths or []):
                    res = self.execute_backup(bp, "scheduled", session_id)
                    task_result = res.get("data", {})

            else:
                error_msg = f"Unknown task type: {task.task_type}"
                status = "failed"

        except Exception as exc:
            error_msg = str(exc)
            status    = "failed"
            self.logger.error("Scheduled task #%s failed: %s", task.id, exc, exc_info=True)

        return {
            "status":  status,
            "task_id": task.id,
            "detail":  task_result,
            "error":   error_msg,
        }

    def execute_scheduled_backup_with_analysis(
        self, target: str, session_id: Optional[str] = None
    ) -> dict[str, Any]:
        if not self._check_authentication(session_id):
            return self._error_response("Scheduled backup failed", "Authentication required")
        try:
            backup_result = self.backup_manager.execute_backup(target, "scheduled")
            self._post_backup_log(backup_result)
            return self.backup_formatter.format_backup_result(backup_result)
        except CliException as exc:
            return self._error_response("Scheduled backup failed", str(exc))

    # ══════════════════════════════════════════════════════════════════════════
    # Private helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _backend_ai_enrich(
        self,
        pipeline_result: dict[str, Any],
        cleaned_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Try backend AI first.  Fall back to local AILogAnalyzer if backend is
        unavailable but ANTHROPIC_API_KEY is set locally.
        """
        if not self.settings_manager.get("analysis.ai_enabled", True):
            pipeline_result["ai_solutions"] = []
            pipeline_result["ai_available"] = False
            pipeline_result["ai_skipped_reason"] = "disabled"
            return pipeline_result

        # ── Backend AI (quota-gated) ───────────────────────────────────
        if self._backend_available():
            records = cleaned_data.get("records", [])
            top_errors = [
                r.get("clean_text") or r.get("clean_message", "")
                for r in records
                if r.get("level") in ("ERROR", "CRITICAL")
            ][:50]

            if top_errors:
                try:
                    tier_result = self.backend.check_ai_tier()
                    remaining = tier_result.get("remaining_free_requests")
                    if remaining is not None and int(remaining) <= 0:
                        pipeline_result["ai_solutions"] = []
                        pipeline_result["ai_available"] = False
                        pipeline_result["ai_skipped_reason"] = "quota_exhausted"
                        return pipeline_result
                except Exception as exc:
                    self.logger.warning("Backend AI tier check failed: %s", exc)

                try:
                    issue_list = [{"message": item} for item in top_errors]
                    ai_result = self.backend.suggest_ai({"issues": issue_list})
                    if ai_result.get("status_code") == 404 or ai_result.get("error"):
                        ai_result = self.backend.analyze_logs("\n".join(top_errors))
                    analysis_text = ai_result.get("analysis", "")
                    if ai_result.get("success") is not False and analysis_text:
                        pipeline_result["ai_solutions"] = [{
                            "issue_type":        "log_errors",
                            "severity":          "high",
                            "error_summary":     analysis_text[:500],
                            "likely_root_cause": "",
                            "actionable_fix":    analysis_text,
                            "priority":          "high",
                        }]
                        pipeline_result["ai_available"] = True
                        return pipeline_result
                    self.logger.warning("Backend AI returned: %s", ai_result.get("message"))
                except Exception as exc:
                    self.logger.warning("Backend AI enrichment failed: %s", exc)

        # ── Local AI fallback (ANTHROPIC_API_KEY in .env) ──────────────
        import os
        if os.environ.get("ANTHROPIC_API_KEY"):
            try:
                from system_manager_cli.logs_analysis.Analysis.ai_analyzer import AILogAnalyzer
                return AILogAnalyzer().enrich(pipeline_result)
            except Exception as exc:
                self.logger.warning("Local AI enrichment failed: %s", exc)

        pipeline_result["ai_solutions"] = []
        pipeline_result["ai_available"] = False
        return pipeline_result

    def _post_backup_log(self, backup_result: dict[str, Any]) -> None:
        """Fire-and-forget: POST backup result to backend."""
        if not self._backend_available():
            return
        try:
            # FIX 4: use the correct BackendClient method name (log_backup)
            self.backend.log_backup(backup_result)
        except Exception as exc:
            self.logger.warning("Failed to post backup log to backend: %s", exc)

    def _post_log_report(self, enriched: dict[str, Any]) -> None:
        """Fire-and-forget: POST log report summary to backend."""
        if not self._backend_available():
            return
        try:
            # FIX 4: use the correct BackendClient method name (save_log_report)
            self.backend.save_log_report(enriched)
        except Exception as exc:
            self.logger.warning("Failed to post log report to backend: %s", exc)

    def _send_backup_email(
        self,
        recipient: str,
        backup_result: dict[str, Any],
        backup_type: str,
    ) -> None:
        """Send backup completion email via backend trigger or local Emailer."""
        if self._backend_available():
            try:
                self.backend.trigger_email(
                    "backup_complete",
                    recipient,
                    {
                        "backup_type": backup_type,
                        "success":     backup_result.get("success", False),
                        "file_count":  backup_result.get("file_count", 0),
                        "size_bytes":  backup_result.get("size_bytes", 0),
                    },
                )
                return
            except Exception:
                pass
        try:
            self.emailer.send_backup_complete(recipient, backup_result)
        except Exception:
            pass

    def _send_analysis_email(
        self,
        recipient: str,
        enriched: dict[str, Any],
    ) -> None:
        """Send analysis report email via backend trigger or local Emailer."""
        if self._backend_available():
            try:
                self.backend.trigger_email(
                    "log_analysis",
                    recipient,
                    {
                        "source_path": enriched.get("source_path", ""),
                        "error_count": enriched.get("metrics", {}).get("error_count", 0),
                    },
                )
                return
            except Exception:
                pass
        try:
            self.emailer.send_log_analysis(recipient, enriched)
        except Exception:
            pass

    def _sync_settings_from_backend(self) -> None:
        """Pull settings from backend and merge into local SettingsManager."""
        if not self._backend_available():
            return
        try:
            result = self.backend.get_settings()
            if result.get("success") and result.get("settings"):
                backend_settings = result["settings"]
                for key, val in backend_settings.items():
                    if isinstance(val, dict):
                        for sub_key, sub_val in val.items():
                            self.settings_manager.set(f"{key}.{sub_key}", sub_val)
                    else:
                        self.settings_manager.set(key, val)
        except Exception as exc:
            self.logger.warning("Could not sync settings from backend: %s", exc)

    def _get_default_log_paths(self) -> list[str]:
        import os
        import platform
        candidates: list[str] = []
        if platform.system().lower().startswith("win"):
            candidates.extend([r"C:\Windows\Logs", r"C:\Windows\System32\winevt\Logs"])
        else:
            candidates.extend(["/var/log", "/tmp"])
        candidates.append(os.getcwd())
        return [path for path in candidates if Path(path).exists()]