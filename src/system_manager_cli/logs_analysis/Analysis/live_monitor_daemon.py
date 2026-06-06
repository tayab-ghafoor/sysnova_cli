"""Background daemon for live log monitoring.

The daemon tails text log files, detects critical incidents, stores scrubbed
incident records in one JSON file per job, and sends best-effort alerts.
"""

from __future__ import annotations

import json
import multiprocessing
import re
import socket
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from system_manager_cli.Notifications.Emailer import Emailer
from system_manager_cli.config.config import Config
from system_manager_cli.core.backend_client import BackendClient, _load_token
from system_manager_cli.core.settings_manager import SettingsManager
from system_manager_cli.logs_analysis.Analysis.classifier import IssueClassifier
from system_manager_cli.logs_analysis.Analysis.scanner import LogScanner
from system_manager_cli.logs_analysis.Analysis.scrubber import LogScrubber


BINARY_EXTENSIONS = {
    ".evtx",
    ".evt",
    ".etl",
    ".bin",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".exe",
    ".dll",
    ".sys",
}
LOG_EXTENSIONS = {".log", ".txt", ".out", ".err", ".json"}
CRITICAL_PATTERN = re.compile(
    r"\b("
    r"kernel panic|panic:|out of memory|oom|filesystem full|disk full|"
    r"no space left|database (crash|down|unreachable)|service crash|"
    r"fatal|segmentation fault|sigsegv|data corruption|i/o error"
    r")\b",
    re.IGNORECASE,
)


def _data_dir() -> Path:
    try:
        Config.ensure_directories()
        return Path(Config.DATA_DIR)
    except Exception:
        return Path.home() / ".system_manager_cli"


def _alert_email() -> str:
    try:
        settings = SettingsManager()
        configured = settings.get("notifications.alert_email", "") or ""
        return configured.strip() or (Config.EMAIL_RECIPIENT or "").strip()
    except Exception:
        return (Config.EMAIL_RECIPIENT or "").strip()


def _run_daemon(job_id: str, path: str, interval: float) -> None:
    LiveLogDaemon(job_id=job_id, path=path, interval=interval).run()


def start_background_monitor(path: str, interval: float = 3.0) -> dict[str, Any]:
    """Start a non-daemon child process and return its job metadata."""
    job_id = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
    process = multiprocessing.Process(
        target=_run_daemon,
        args=(job_id, path, interval),
        name=f"live-log-monitor-{job_id}",
    )
    process.daemon = False
    process.start()
    error_file = _data_dir() / "live_errors" / f"live_errors_{job_id}.json"
    return {"job_id": job_id, "pid": process.pid, "error_file": str(error_file)}


class LiveLogDaemon:
    """Tail log files and alert on critical records."""

    def __init__(
        self,
        job_id: str,
        path: str,
        app_ref: Any | None = None,
        interval: float = 3.0,
        alert_cooldown_seconds: int = 60,
    ):
        self.job_id = job_id
        self.path = path
        self.interval = interval
        self.running = True
        self.app = app_ref
        self.backend = getattr(app_ref, "backend", None) or BackendClient()
        self.emailer = getattr(app_ref, "emailer", None) or Emailer()
        self.alert_email = _alert_email()
        self.error_file = _data_dir() / "live_errors" / f"live_errors_{job_id}.json"
        self.error_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_file = self.error_file.with_suffix(".log")
        self.alert_cooldown_seconds = alert_cooldown_seconds
        self._last_alert_time: dict[str, float] = {}
        self._positions: dict[str, int] = {}

    def run(self) -> None:
        """Run until the process is stopped."""
        try:
            self._main_loop()
        except KeyboardInterrupt:
            self.running = False
        except Exception:
            self._write_daemon_log(f"Daemon crashed:\n{traceback.format_exc()}")
        finally:
            self._cleanup()

    def _main_loop(self) -> None:
        scanner = LogScanner()
        classifier = IssueClassifier()
        scrubber = LogScrubber()

        while self.running:
            records = self._read_new_records()
            if records:
                scanned = scanner.scan({"records": records})
                classified = classifier.classify(scanned)
                cleaned = scrubber.scrub(classified)
                for record in cleaned.get("records", []):
                    if self.is_critical_record(record):
                        self.handle_critical(record)
            time.sleep(self.interval)

    def _collect_files(self) -> list[Path]:
        source = Path(self.path).expanduser()
        if source.is_file():
            return [source] if self._is_candidate(source) else []
        if not source.is_dir():
            return []
        try:
            return sorted(p for p in source.iterdir() if p.is_file() and self._is_candidate(p))
        except (OSError, PermissionError):
            return []

    def _read_new_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for file_path in self._collect_files():
            for line in self._read_new_lines(file_path):
                if line.strip():
                    records.append(
                        {
                            "file_path": str(file_path.resolve()),
                            "line_number": 0,
                            "raw_text": line.rstrip("\n"),
                        }
                    )
        return records

    def _read_new_lines(self, file_path: Path) -> list[str]:
        key = str(file_path.resolve())
        try:
            size = file_path.stat().st_size
        except OSError:
            return []

        last_pos = self._positions.get(key)
        if last_pos is None:
            self._positions[key] = size
            return []
        if size < last_pos:
            last_pos = 0
        if size == last_pos:
            self._positions[key] = size
            return []

        try:
            with file_path.open("r", encoding="utf-8", errors="ignore") as handle:
                handle.seek(last_pos)
                content = handle.read()
                self._positions[key] = handle.tell()
            return content.splitlines()
        except (OSError, PermissionError):
            return []

    @staticmethod
    def _is_candidate(path: Path) -> bool:
        ext = path.suffix.lower()
        if ext in BINARY_EXTENSIONS:
            return False
        return ext in LOG_EXTENSIONS or "log" in path.name.lower()

    @staticmethod
    def is_critical_record(record: dict[str, Any]) -> bool:
        level = str(record.get("level", "INFO")).upper()
        if level == "CRITICAL":
            return True
        text = " ".join(
            str(record.get(key, ""))
            for key in ("clean_message", "clean_text", "message")
        )
        return bool(CRITICAL_PATTERN.search(text))

    def handle_critical(self, record: dict[str, Any]) -> dict[str, Any] | None:
        pattern = self._incident_pattern(record)
        now = time.time()
        if now - self._last_alert_time.get(pattern, 0) < self.alert_cooldown_seconds:
            return None
        self._last_alert_time[pattern] = now

        suggestions = self._request_ai_suggestions(record)
        incident = {
            "job_id": self.job_id,
            "job_name": f"live-log-monitor-{self.job_id}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hostname": socket.gethostname(),
            "source": record.get("source_name") or Path(record.get("file_path", "")).name,
            "file_path": record.get("file_path"),
            "level": record.get("level", "CRITICAL"),
            "issue_type": record.get("issue_type", "unknown"),
            "pattern": pattern,
            "message": record.get("clean_message") or record.get("clean_text") or "",
            "ai_suggestions": suggestions,
        }
        self._append_incident(incident)
        self._send_alert(incident)
        return incident

    def _incident_pattern(self, record: dict[str, Any]) -> str:
        text = record.get("normalized_message") or record.get("clean_message") or ""
        text = re.sub(r"\s+", " ", str(text)).strip().lower()
        return text[:240] or "critical-log-event"

    def _append_incident(self, incident: dict[str, Any]) -> None:
        incidents: list[dict[str, Any]] = []
        if self.error_file.exists():
            try:
                loaded = json.loads(self.error_file.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    incidents = loaded
            except json.JSONDecodeError:
                incidents = []
        incidents.append(incident)
        self.error_file.write_text(json.dumps(incidents, indent=2, default=str), encoding="utf-8")

    def _request_ai_suggestions(self, record: dict[str, Any]) -> list[str]:
        if not _load_token():
            return []
        message = record.get("clean_text") or record.get("clean_message") or ""
        if not message:
            return []
        try:
            result = self.backend.suggest_ai([{"message": message, "level": record.get("level")}])
            suggestion = result.get("analysis") or result.get("suggestion") or result.get("message")
            if result.get("success") and suggestion:
                return [str(suggestion)]
        except Exception as exc:
            self._write_daemon_log(f"AI suggestion failed: {exc}")
        return []

    def _send_alert(self, incident: dict[str, Any]) -> None:
        if not self.alert_email:
            return
        subject = f"[CRITICAL] Live Log Alert - {incident['job_name']} - {incident['timestamp'][:19]}"
        body = self._alert_body(incident)

        if _load_token():
            try:
                result = self.backend.trigger_email(
                    "generic",
                    self.alert_email,
                    {"subject": subject, "body": body.replace("\n", "<br>")},
                )
                if result.get("success") is not False and not result.get("error"):
                    return
            except Exception as exc:
                self._write_daemon_log(f"Backend email failed: {exc}")

        try:
            self.emailer.send_alert(subject=subject, message=body, recipient_email=self.alert_email)
        except Exception as exc:
            self._write_daemon_log(f"Local email failed: {exc}")

    @staticmethod
    def _alert_body(incident: dict[str, Any]) -> str:
        lines = [
            "Critical live log alert",
            "=" * 32,
            f"Host: {incident.get('hostname', '')}",
            f"Job: {incident.get('job_name', '')}",
            f"Source: {incident.get('source', '')}",
            f"Timestamp: {incident.get('timestamp', '')}",
            f"Pattern: {incident.get('pattern', '')}",
            "",
            str(incident.get("message", "")),
        ]
        suggestions = incident.get("ai_suggestions") or []
        if suggestions:
            lines.extend(["", "AI suggestions:"])
            lines.extend(f"- {item}" for item in suggestions)
        return "\n".join(lines)

    def _write_daemon_log(self, message: str) -> None:
        try:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            with self.log_file.open("a", encoding="utf-8") as handle:
                handle.write(f"[{datetime.now(timezone.utc).isoformat()}] {message}\n")
        except Exception:
            pass

    def _cleanup(self) -> None:
        self.running = False


def foreground_monitor(
    path: str,
    on_record: Callable[[dict[str, Any]], None],
    app_ref: Any | None = None,
    on_idle: Callable[[], None] | None = None,
) -> None:
    """Run the same monitor logic in the foreground and stream records to a callback."""
    monitor = LiveLogDaemon(job_id=f"foreground_{uuid.uuid4().hex[:8]}", path=path, app_ref=app_ref)
    scanner = LogScanner()
    classifier = IssueClassifier()
    scrubber = LogScrubber()
    while True:
        records = monitor._read_new_records()
        if records:
            cleaned = scrubber.scrub(classifier.classify(scanner.scan({"records": records})))
            for record in cleaned.get("records", []):
                on_record(record)
                if monitor.is_critical_record(record):
                    monitor.handle_critical(record)
        elif on_idle is not None:
            on_idle()
        time.sleep(monitor.interval)
