"""
backend_client.py — HTTP client that talks to the Railway FastAPI backend.

All CLI→Backend communication flows through this module.
The CLI never calls AI, PostgreSQL, or email services directly.

FIX LOG
───────
- Added is_authenticated() method (was called in app.py but never existed)
- Added create_backup_log() alias (app.py called this; real method is log_backup())
- Added create_log_report() alias (app.py called this; real method is save_log_report())
- Made ping() return False (not raise) when the backend is unreachable
- Token file now stored under the project data dir to avoid ~ collisions in tests
- FIX #10: Token file is written with mode 0o600 (owner read/write only)
- FIX #12: Hardcoded token path to user home directory (no dynamic import)
- FIX #13: Cache token in memory to prevent file path inconsistencies
- FIX PAYMENT-1: Removed broken request_pro() which used third-party `requests`
                 and sent payment_method in JSON body instead of query param.
                 request_pro_upgrade() is now the single, correct method.
- FIX PAYMENT-2: Removed JazzCash from all payment method references — only
                 HBL Bank Transfer and Easypaisa are supported.
- FIX PAYMENT-3: Removed dead create_checkout_session() and get_subscription()
                 methods that referenced non-existent backend endpoints.
- FIX PAYMENT-4: submit_pro_proof() now uses urllib (consistent with the rest of
                 the client) and no longer imports third-party `requests`.
- FIX #14: Removed global logging.basicConfig(level=logging.DEBUG) to avoid flood.
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any
import urllib.request
import urllib.error
import urllib.parse

from ..ulits.logger import get_logger

logger = get_logger(__name__)

# ── Token storage ──────────────────────────────────────────────────────
def _token_file_path() -> Path:
    """Return the writable, per-user token file path."""
    try:
        from ..config.config import Config

        Config.ensure_directories()
        return Config.DATA_DIR / "auth_token.json"
    except Exception:
        return Path.home() / ".system_manager_cli_token.json"


TOKEN_FILE_PATH = _token_file_path()


def _save_token(token: str, expires_at: str) -> None:
    """
    Persist JWT token to disk with restrictive permissions (0o600).
    Uses an atomic write (temp file → rename) to prevent partial writes.
    """
    try:
        TOKEN_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"token": token, "expires_at": expires_at})

        tmp_path = TOKEN_FILE_PATH.with_suffix(".tmp")
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        fd = os.open(tmp_path, flags, stat.S_IRUSR | stat.S_IWUSR)
        with os.fdopen(fd, "w", encoding="utf-8") as token_file:
            token_file.write(payload)

        try:
            os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
        except OSError:
            logger.warning(
                "Could not set restrictive permissions on token file %s. "
                "Ensure the file system supports file permissions.",
                TOKEN_FILE_PATH,
            )

        tmp_path.replace(TOKEN_FILE_PATH)  # atomic rename

        try:
            os.chmod(TOKEN_FILE_PATH, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
        except OSError:
            pass

    except Exception as exc:
        logger.warning("Could not save token: %s", exc)


def _load_token() -> str | None:
    """Read token from disk (fallback when memory cache is empty)."""
    try:
        if not TOKEN_FILE_PATH.exists():
            return None
        data = json.loads(TOKEN_FILE_PATH.read_text(encoding="utf-8"))
        token = data.get("token") or None
        if token:
            logger.debug("Token loaded from disk (size %d)", len(token))
        return token
    except Exception:
        return None


def _clear_token() -> None:
    """Remove token file from disk."""
    try:
        if TOKEN_FILE_PATH.exists():
            TOKEN_FILE_PATH.unlink()
            logger.debug("Token file removed")
    except Exception:
        pass


# ── Core HTTP helper ───────────────────────────────────────────────────

class BackendClient:
    """Thin HTTP wrapper around the FastAPI backend."""

    def __init__(self, base_url: str | None = None):
        """
        Initialize BackendClient with explicit backend URL.
        
        Args:
            base_url: Explicit backend URL override (for testing)
        
        Environment Variables (required for production):
            BACKEND_URL: Full URL to FastAPI backend (e.g., https://backend.railway.app)
        """
        # Priority: 1) parameter, 2) env var, 3) config file
        self.base_url = (
            base_url
            or os.environ.get("BACKEND_URL", "").strip()
            or self._load_from_config()
        )
        
        # Validate and normalize
        if self.base_url:
            self.base_url = self.base_url.rstrip("/")
            if not self.base_url.startswith(("http://", "https://")):
                logger.error(
                    "Invalid BACKEND_URL format: %s. Must start with http:// or https://",
                    self.base_url,
                )
                self.base_url = ""
        
        if not self.base_url:
            logger.warning(
                "Backend URL not configured. Set BACKEND_URL environment variable "
                "or configure in AppConfig. Backend features will be unavailable."
            )
        
        self._cached_token: str | None = None   # cache token in memory

    def _load_from_config(self) -> str | None:
        """Load backend URL from application config as fallback."""
        try:
            from ..config.app_config import AppConfig
            from ..config.config import Config
            
            # Try AppConfig first
            app_config = AppConfig()
            url = app_config.get("backend_url")
            if url:
                return url.strip()
            
            # Fall back to Config class
            url = Config.BACKEND_URL
            if url:
                return url.strip()
        except Exception as exc:
            logger.debug("Could not load backend URL from config: %s", exc)
        
        return None

    def _request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        token: str | None = None,
        timeout: int = 10,
    ) -> dict[str, Any]:
        if not self.base_url:
            return {"error": "Backend URL is not configured.", "success": False}

        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}

        auth_token = token or self._cached_token or _load_token()
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
            logger.debug("Request %s %s includes Authorization header", method, path)
        else:
            logger.warning("Request %s %s has NO Authorization header", method, path)

        data = json.dumps(body).encode("utf-8") if body else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode("utf-8"))
            except Exception:
                detail = {"detail": str(exc)}
            logger.warning("Backend %s %s -> %d: %s", method, path, exc.code, detail)
            return {
                "error":       detail.get("detail", str(exc)),
                "status_code": exc.code,
                "success":     False,
            }
        except urllib.error.URLError as exc:
            logger.debug("Backend unreachable at %s: %s", self.base_url, exc)
            return {"error": f"Backend unreachable: {exc.reason}", "success": False}
        except Exception as exc:
            logger.debug("Backend request error: %s", exc)
            return {"error": str(exc), "success": False}

    def _multipart_request(
        self,
        path: str,
        fields: dict[str, str],
        file_field: str,
        file_bytes: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
        timeout: int = 30,
    ) -> dict[str, Any]:
        """
        Send a multipart/form-data POST request using only the standard library.
        Used for file uploads (e.g. payment receipt screenshots).
        """
        if not self.base_url:
            return {"error": "Backend URL is not configured.", "success": False}

        url = f"{self.base_url}{path}"
        boundary = "----BackendClientBoundary" + os.urandom(8).hex()

        body_parts: list[bytes] = []

        # Text fields
        for field_name, field_value in fields.items():
            body_parts.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{field_name}"\r\n'
                f"\r\n"
                f"{field_value}\r\n".encode("utf-8")
            )

        # File field
        body_parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n"
            f"\r\n".encode("utf-8")
        )
        body_parts.append(file_bytes)
        body_parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))

        body = b"".join(body_parts)

        auth_token = self._cached_token or _load_token()
        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        }
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode("utf-8"))
            except Exception:
                detail = {"detail": str(exc)}
            logger.warning("Backend multipart POST %s -> %d: %s", path, exc.code, detail)
            return {
                "error":       detail.get("detail", str(exc)),
                "status_code": exc.code,
                "success":     False,
            }
        except urllib.error.URLError as exc:
            logger.debug("Backend unreachable at %s: %s", self.base_url, exc)
            return {"error": f"Backend unreachable: {exc.reason}", "success": False}
        except Exception as exc:
            logger.debug("Multipart request error: %s", exc)
            return {"error": str(exc), "success": False}

    # ── Connectivity ────────────────────────────────────────────────────

    def ping(self) -> bool:
        """Return True if the backend responds to /health."""
        if not self.base_url:
            return False
        try:
            result = self._request("GET", "/health", timeout=5)
            return result.get("status") == "healthy"
        except Exception:
            return False

    def is_authenticated(self) -> bool:
        """Return True when a cached token exists or a disk token is present."""
        return bool(self._cached_token or _load_token())

    def get_token(self) -> str | None:
        """Return the currently cached token (or fall back to disk)."""
        token = self._cached_token or _load_token()
        if token:
            logger.debug("get_token() returning valid token")
        else:
            logger.debug("get_token() returning None")
        return token

    # ── Auth endpoints ──────────────────────────────────────────────────

    def register(
        self,
        full_name: str,
        email: str,
        password: str,
        confirm_password: str,
    ) -> dict:
        return self._request("POST", "/api/v1/auth/register", {
            "full_name":        full_name,
            "email":            email,
            "password":         password,
            "confirm_password": confirm_password,
        })

    def verify_email(self, email: str, code: str) -> dict:
        return self._request("POST", "/api/v1/auth/verify-email", {
            "email": email,
            "code":  code,
        })

    def login(self, email: str, password: str) -> dict:
        result = self._request("POST", "/api/v1/auth/login", {
            "email": email, "password": password,
        })
        token = result.get("token") or result.get("access_token")
        if token:
            result["token"] = token
            result.setdefault("success", True)
            result.setdefault("user", {
                "email":     email,
                "username":  email.split("@")[0],
                "full_name": "",
            })
            _save_token(token, result.get("expires_at", ""))
            self._cached_token = token
            logger.info("Login successful, token cached")
        else:
            logger.warning("Login response did not contain a token")
        return result

    def logout(self) -> dict:
        token = self.get_token()
        result = self._request("POST", "/api/v1/auth/logout", token=token)
        _clear_token()
        self._cached_token = None
        return result

    def resend_verification(self, email: str) -> dict:
        return self._request("POST", "/api/v1/auth/resend-verification", {"email": email})

    def forgot_password(self, email: str) -> dict:
        return self._request("POST", "/api/v1/auth/forgot-password", {"email": email})

    def reset_password(self, email: str, code: str, new_password: str) -> dict:
        return self._request("POST", "/api/v1/auth/reset-password", {
            "email": email, "code": code, "new_password": new_password,
        })

    # ── User / profile ──────────────────────────────────────────────────

    def get_profile(self) -> dict:
        return self._request("GET", "/api/v1/user/profile", token=self.get_token())

    def get_usage(self) -> dict:
        return self._request("GET", "/api/v1/user/usage", token=self.get_token())

    def get_usage_stats(self) -> dict:
        """Compatibility alias used by CLI status/settings views."""
        return self.get_usage()

    # ── AI Analysis ─────────────────────────────────────────────────────

    def analyze_logs(self, logs: str) -> dict:
        """Send sanitized log content to backend for AI analysis."""
        result = self._request(
            "POST", "/api/v1/ai/analyze",
            body={"logs": logs[:50_000]},
            token=self.get_token(),
        )
        if "error" not in result:
            result.setdefault("success", True)
        return result

    def check_ai_tier(self) -> dict:
        """Return backend AI tier/quota details."""
        result = self._request("POST", "/api/v1/ai/check-tier", token=self.get_token())
        if "error" not in result:
            result.setdefault("success", True)
        return result

    def suggest_ai(self, issues: list[dict] | dict) -> dict:
        """Request AI suggestions for a scrubbed issue list."""
        body = issues if isinstance(issues, dict) else {"issues": issues}
        result = self._request(
            "POST", "/api/v1/ai/suggest",
            body=body,
            token=self.get_token(),
        )
        if "error" not in result:
            result.setdefault("success", True)
        return result

    # ── Backup logs ─────────────────────────────────────────────────────

    def log_backup(self, backup_data: dict) -> dict:
        """POST a backup event to the backend for persistence."""
        return self._request(
            "POST", "/api/v1/backups/",
            body=backup_data,
            token=self.get_token(),
        )

    def create_backup_log(self, backup_data: dict) -> dict:
        """Compatibility alias for log_backup()."""
        return self.log_backup(backup_data)

    def get_backups(self) -> dict:
        return self._request("GET", "/api/v1/backups/", token=self.get_token())

    # ── Log reports ─────────────────────────────────────────────────────

    def save_log_report(self, report: dict) -> dict:
        """POST a log analysis report to the backend for persistence."""
        metrics = report.get("metrics", {})
        summary = report.get("summary", {})
        payload = {
            "source_path":        report.get("source_path", ""),
            "files_scanned":      summary.get("files_scanned", metrics.get("files_scanned", 0)),
            "records_processed":  summary.get(
                "records_processed", metrics.get("records_processed", 0)
            ),
            "error_count":        metrics.get("error_count", 0),
            "warning_count":      metrics.get("warning_count", 0),
            "critical_count":     metrics.get("critical_count", 0),
            "anomalies_detected": summary.get("anomalies_detected", 0),
            "highest_severity":   summary.get("highest_severity", "none"),
            "error_rate":         metrics.get("error_rate", 0.0),
            "anomalies":          report.get("anomalies"),
            "recommendations":    report.get("recommendations"),
            "ai_solutions":       report.get("ai_solutions"),
            "report_file_path":   report.get("report_path"),
        }
        return self._request(
            "POST", "/api/v1/logs/",
            body=payload,
            token=self.get_token(),
        )

    def create_log_report(self, report: dict) -> dict:
        """Compatibility alias for save_log_report()."""
        return self.save_log_report(report)

    def get_log_reports(self) -> dict:
        return self._request("GET", "/api/v1/logs/", token=self.get_token())

    # ── Scheduled tasks ─────────────────────────────────────────────────

    def create_task(self, task: dict) -> dict:
        return self._request("POST", "/api/v1/tasks/", body=task, token=self.get_token())

    def list_tasks(self) -> dict:
        return self._request("GET", "/api/v1/tasks/", token=self.get_token())

    def update_task(self, task_id: int, updates: dict) -> dict:
        return self._request(
            "PATCH", f"/api/v1/tasks/{task_id}", body=updates, token=self.get_token()
        )

    def delete_task(self, task_id: int) -> dict:
        return self._request("DELETE", f"/api/v1/tasks/{task_id}", token=self.get_token())

    # ── Settings ────────────────────────────────────────────────────────

    def get_settings(self) -> dict:
        return self._request("GET", "/api/v1/settings/", token=self.get_token())

    def save_settings(self, settings: dict) -> dict:
        return self._request(
            "PUT", "/api/v1/settings/",
            body={"settings": settings},
            token=self.get_token(),
        )

    # ── Email triggers ──────────────────────────────────────────────────

    def trigger_email(self, email_type: str, recipient: str, payload: dict) -> dict:
        return self._request(
            "POST", "/api/v1/emails/trigger",
            body={"email_type": email_type, "recipient": recipient, "payload": payload},
            token=self.get_token(),
        )

    # ── Payment / Pro upgrade ───────────────────────────────────────────

    def request_pro_upgrade(self, payment_method: str = "hbl_bank_transfer") -> dict:
        """
        Request a Pro upgrade with the specified payment method.

        Supported values: 'hbl_bank_transfer', 'easypaisa_transfer'

        The backend expects payment_method as a URL query parameter (not a JSON body).
        Returns bank/transfer account details, a unique reference code, and
        step-by-step instructions.
        """
        if payment_method not in ("hbl_bank_transfer", "easypaisa_transfer"):
            logger.warning(
                "Unsupported payment method '%s'. Defaulting to hbl_bank_transfer.",
                payment_method,
            )
            payment_method = "hbl_bank_transfer"

        logger.debug("Requesting Pro upgrade with method: %s", payment_method)
        encoded = urllib.parse.quote(payment_method)
        return self._request(
            "POST",
            f"/api/v1/payment/pro/request?payment_method={encoded}",
            token=self.get_token(),
        )

    def get_pro_proof_requirements(self) -> dict:
        """
        Fetch the fields and instructions required to submit payment proof for
        the current pending order.
        """
        return self._request(
            "GET",
            "/api/v1/payment/pro/proof-requirements",
            token=self.get_token(),
        )

    def check_pro_status(self) -> dict:
        """
        Check the current user's Pro subscription status.

        Returns one of: 'active', 'pending_verification', 'awaiting_proof',
        'declined', or 'none'.
        """
        return self._request(
            "GET",
            "/api/v1/payment/pro/status",
            token=self.get_token(),
        )

    def submit_pro_proof(
        self,
        transaction_id: str,
        payer_name: str,
        receipt_file: bytes | None = None,
        filename: str | None = None,
        phone_number: str | None = None,
    ) -> dict:
        """
        Submit payment proof — Transaction ID, payer name, optional phone number,
        and a receipt screenshot.

        Uses multipart/form-data via the standard library (no third-party dependencies).
        The screenshot must be a PNG, JPG, or WEBP image ≤ 5 MB.
        """
        if not receipt_file or not filename:
            # No file — send as plain form fields via a simple POST
            # (backend requires the screenshot field; this path returns an informative error)
            logger.warning("submit_pro_proof called without a receipt file — backend will reject")
            fields: dict[str, str] = {
                "transaction_id": transaction_id,
                "payer_name":     payer_name,
            }
            if phone_number:
                fields["phone_number"] = phone_number
            return self._request(
                "POST",
                "/api/v1/payment/pro/submit-proof",
                body=fields,
                token=self.get_token(),
            )

        # Determine MIME type from filename extension for the Content-Type header
        ext = (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()
        mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
        content_type = mime_map.get(ext, "image/jpeg")

        fields = {"transaction_id": transaction_id, "payer_name": payer_name}
        if phone_number:
            fields["phone_number"] = phone_number

        return self._multipart_request(
            path="/api/v1/payment/pro/submit-proof",
            fields=fields,
            file_field="screenshot",
            file_bytes=receipt_file,
            filename=filename,
            content_type=content_type,
            timeout=30,
        )
