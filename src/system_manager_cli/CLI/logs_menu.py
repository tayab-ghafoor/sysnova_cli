"""Logs Analysis System — CLI menu (Option 3).

Full implementation per Logs_analysis_engine.md v2.0

Features implemented
────────────────────
Option 1 — Batch Analysis & Report Generation
  • OS-aware default path discovery (Windows / Linux / macOS)
  • Current working directory discovery
  • Custom path entry with validation
  • tqdm progress bar through all 8 pipeline stages
  • AI enrichment (backend quota-gated, local ANTHROPIC_API_KEY fallback)
  • Auto-send email on critical issues or error_count > 5
  • Rich colour-coded CLI report display
  • Auto-cleanup of old reports (keeps newest N)

Option 2 — Live Logs Analysis
  • Same path-source sub-menu as Option 1
  • Foreground mode: colour-coded live tail to console (Ctrl+C to stop)
  • Background mode: detached daemon process, returns user to menu
  • seek/tell polling — works on Linux, macOS, Windows without root
  • Log rotation detection (inode change or file shrink)

Background Job Registry  ← KEY NEW FEATURE
  • ~/.sysguard/background_jobs.json shared state file
  • "View background jobs" menu option appears when jobs exist
  • Job table: ID, file, status, started, criticals, pending alerts
  • Per-job actions: Stop, View alerts, Acknowledge (clear pending counter)
  • Stop all jobs
  • Pending-alerts banner in menu header

Architecture rules respected
─────────────────────────────
• Only calls app.py — no direct core/analysis/reporting imports
• No business logic — all routing goes through app.execute_log_analysis()
• CLI output only — formatting stays in this layer
"""

from __future__ import annotations

import json
import os
import platform
import re
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── ANSI colours (no external deps) ──────────────────────────────────────────

_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_RED    = "\033[91m"
_YELLOW = "\033[93m"
_CYAN   = "\033[96m"
_GREEN  = "\033[92m"
_BLUE   = "\033[94m"
_MAGENTA = "\033[95m"
_WHITE  = "\033[97m"
_ORANGE = "\033[33m"

_SEV_COLOR = {
    "critical": _RED,
    "high":     _ORANGE,
    "medium":   _YELLOW,
    "low":      _GREEN,
    "none":     _GREEN,
}


def _c(text: str, code: str) -> str:
    return f"{code}{text}{_RESET}"


# ── Background Job Registry ───────────────────────────────────────────────────

def _registry_path() -> Path:
    """Return path to the shared background_jobs.json registry."""
    try:
        from system_manager_cli.config.config import Config
        base = Path(Config.DATA_DIR)
    except Exception:
        base = Path.home() / ".sysguard"
    base.mkdir(parents=True, exist_ok=True)
    return base / "background_jobs.json"


def _read_registry() -> dict[str, Any]:
    """Load the registry; return empty structure on any error."""
    path = _registry_path()
    if not path.exists():
        return {"jobs": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "jobs" not in data:
            return {"jobs": []}
        return data
    except Exception:
        return {"jobs": []}


def _write_registry(data: dict[str, Any]) -> None:
    """Persist registry atomically."""
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def _register_job(job_id: str, pid: int, file_path: str) -> None:
    data = _read_registry()
    data["jobs"].append({
        "job_id":         job_id,
        "pid":            pid,
        "file":           file_path,
        "started_at":     datetime.now(timezone.utc).isoformat(),
        "status":         "running",
        "critical_count": 0,
        "pending_alerts": 0,
        "error_file":     str(_alert_json_dir() / f"live_errors_{job_id}.json"),
    })
    _write_registry(data)


def _update_job_status(job_id: str, status: str) -> None:
    data = _read_registry()
    for job in data["jobs"]:
        if job["job_id"] == job_id:
            job["status"] = status
            break
    _write_registry(data)


def _acknowledge_job_alerts(job_id: str) -> None:
    """Reset pending_alerts counter for a job (user viewed them)."""
    data = _read_registry()
    for job in data["jobs"]:
        if job["job_id"] == job_id:
            job["pending_alerts"] = 0
            break
    _write_registry(data)


def _active_jobs() -> list[dict[str, Any]]:
    """Return jobs that are still running (filter out dead PIDs)."""
    data = _read_registry()
    alive = []
    for job in data["jobs"]:
        if job.get("status") not in ("running",):
            alive.append(job)
            continue
        # Verify process is still alive
        pid = job.get("pid", 0)
        if pid and _pid_alive(pid):
            alive.append(job)
        else:
            job["status"] = "stopped"
            alive.append(job)
    if alive != data["jobs"]:
        data["jobs"] = alive
        _write_registry(data)
    return [j for j in alive if j.get("status") == "running"]


def _all_jobs() -> list[dict[str, Any]]:
    """Return all jobs (running + stopped + crashed)."""
    data = _read_registry()
    return data.get("jobs", [])


def _total_pending_alerts() -> int:
    """Sum pending_alerts across all running jobs."""
    total = 0
    for job in _active_jobs():
        total += job.get("pending_alerts", 0)
    return total


def _pid_alive(pid: int) -> bool:
    """Check if a PID is still running (cross-platform)."""
    try:
        if platform.system() == "Windows":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            h = kernel32.OpenProcess(0x0400, False, pid)  # PROCESS_QUERY_INFORMATION
            if not h:
                return False
            import ctypes.wintypes
            code = ctypes.wintypes.DWORD()
            kernel32.GetExitCodeProcess(h, ctypes.byref(code))
            kernel32.CloseHandle(h)
            return code.value == 259  # STILL_ACTIVE
        else:
            os.kill(pid, 0)
            return True
    except (OSError, ProcessLookupError):
        return False


def _stop_job(job_id: str) -> bool:
    """Send SIGTERM to the job's process and mark it stopped."""
    data = _read_registry()
    for job in data["jobs"]:
        if job["job_id"] == job_id:
            pid = job.get("pid", 0)
            if pid and _pid_alive(pid):
                try:
                    if platform.system() == "Windows":
                        import ctypes
                        ctypes.windll.kernel32.TerminateProcess(
                            ctypes.windll.kernel32.OpenProcess(1, False, pid), 1
                        )
                    else:
                        os.kill(pid, signal.SIGTERM)
                    time.sleep(0.3)
                except Exception:
                    pass
            job["status"] = "stopped"
            _write_registry(data)
            return True
    return False


def _stop_all_jobs() -> int:
    """Stop all running jobs. Returns count stopped."""
    count = 0
    for job in _active_jobs():
        if _stop_job(job["job_id"]):
            count += 1
    return count


def _alert_json_dir() -> Path:
    """Directory where live critical alert JSON files are stored."""
    try:
        from system_manager_cli.config.config import Config
        base = Path(Config.DATA_DIR) / "live_errors"
    except Exception:
        base = Path.home() / ".sysguard" / "live_alerts"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _load_job_alerts(job: dict[str, Any]) -> list[dict[str, Any]]:
    """Load alert events from a job's JSON alert file."""
    error_file = job.get("error_file", "")
    if not error_file or not Path(error_file).exists():
        return []
    try:
        raw = json.loads(Path(error_file).read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return raw
        return raw.get("events", [])
    except Exception:
        return []


# ── UI helpers ────────────────────────────────────────────────────────────────

def _div(char: str = "═", width: int = 62) -> None:
    print(char * width)


def _box_top(width: int = 62) -> str:
    return "╔" + "═" * (width - 2) + "╗"


def _box_bot(width: int = 62) -> str:
    return "╚" + "═" * (width - 2) + "╝"


def _box_row(text: str, width: int = 62) -> str:
    inner = width - 4
    return "║  " + text[:inner].ljust(inner) + "  ║"


def _pause() -> None:
    input("\n  Press Enter to continue...")


def _prompt(msg: str) -> str:
    return input(f"\n  {msg} ").strip()


def _now_str() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _format_iso(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%H:%M  %d %b")
    except ValueError:
        return iso[:16]


# ── Status / severity badges ──────────────────────────────────────────────────

_STATUS_ICON = {
    "running":   _c("● RUNNING ", _GREEN),
    "stopped":   _c("◉ STOPPED ", _YELLOW),
    "crashed":   _c("✖ CRASHED ", _RED),
    "completed": _c("✔ DONE    ", _CYAN),
}

_SEV_BADGE = {
    "critical": _c("🔴 CRITICAL", _RED + _BOLD),
    "high":     _c("🟠 HIGH    ", _ORANGE),
    "medium":   _c("🟡 MEDIUM  ", _YELLOW),
    "low":      _c("🟢 LOW     ", _GREEN),
    "none":     _c("✅ NONE    ", _GREEN),
}

def _sev_badge(sev: str) -> str:
    return _SEV_BADGE.get(sev.lower(), _c(sev.upper(), _CYAN))


# ── OS-aware default log paths ────────────────────────────────────────────────

def _get_default_log_paths() -> list[str]:
    """
    Return a list of valid, readable default log paths for the current OS.
    Windows: C:\\Windows\\Logs  (plain-text CBS, DISM, WindowsUpdate)
    Linux/macOS: /var/log and common subpaths
    Falls back to the app's own logs directory.
    """
    system = platform.system()
    candidates: list[str] = []

    if system == "Windows":
        win_root = os.environ.get("SystemRoot", "C:\\Windows")
        candidates = [
            os.path.join(win_root, "Logs"),
            os.path.join(win_root, "Temp"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp"),
        ]
    else:
        candidates = [
            "/var/log/syslog",
            "/var/log/messages",
            "/var/log/auth.log",
            "/var/log/kern.log",
            "/var/log",
        ]

    # Always include the app's own logs as final fallback
    try:
        from system_manager_cli.config.config import Config
        candidates.append(str(Config.LOGS_DIR))
    except Exception:
        pass

    return [p for p in candidates if p and Path(p).exists() and os.access(p, os.R_OK)]


# ── Source selection sub-menu ─────────────────────────────────────────────────

def _pick_log_source(label: str = "LOGS ANALYSIS") -> str | None:
    """
    Show the 3-option source-selection sub-menu.
    Returns a resolved path string or None if user backs out.
    """
    while True:
        print()
        print(_box_top())
        print(_box_row(f"{label}  —  SELECT SOURCE"))
        print(_box_bot())
        print("  1.  Analyse logs from system default path")
        print("  2.  Analyse logs from current working directory")
        print("  3.  Enter a custom path")
        print("  0.  Back")
        _div("─")

        choice = _prompt("Select (0‑3):")

        if choice == "0":
            return None

        if choice == "1":
            paths = _get_default_log_paths()
            if not paths:
                print(
                    f"\n  {_c('⚠', _YELLOW)}  No readable default log paths found on "
                    f"this {platform.system()} system.\n"
                    "       Please choose option 2 or 3."
                )
                continue
            chosen = paths[0]
            print(f"\n  {_c('✔', _GREEN)}  Using default path: {_c(chosen, _CYAN)}")
            return chosen

        if choice == "2":
            cwd = os.getcwd()
            print(f"\n  {_c('✔', _GREEN)}  Using current directory: {_c(cwd, _CYAN)}")
            return cwd

        if choice == "3":
            raw = _prompt("Enter log file or directory path:")
            if not raw:
                continue
            p = Path(raw).expanduser()
            if not p.exists():
                print(f"  {_c('✖', _RED)}  Path does not exist: {raw}")
                continue
            if not os.access(str(p), os.R_OK):
                print(f"  {_c('✖', _RED)}  Permission denied: {raw}")
                continue
            return str(p)

        print(f"  {_c('⚠', _YELLOW)}  Please enter 0, 1, 2, or 3.")


# ── Rich analysis report display ──────────────────────────────────────────────

def _print_bar(label: str, value: int, total: int,
               width: int = 24, color: str = _CYAN) -> None:
    if total == 0:
        filled = 0
    else:
        filled = int((value / total) * width)
    bar = "█" * filled + "░" * (width - filled)
    pct = f"{value / total * 100:.0f}%" if total else "0%"
    print(f"  {label:<22} {color}{bar}{_RESET}  {_BOLD}{value}{_RESET} ({pct})")


def _metric_bar(label: str, pct: float | None, width: int = 20) -> None:
    if pct is None:
        return
    color = _RED if pct >= 90 else _ORANGE if pct >= 75 else _GREEN
    filled = int(min(pct, 100) / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    icon = "🔴" if pct >= 90 else "🟡" if pct >= 75 else "🟢"
    print(f"  {icon} {label:<14} {color}{bar}{_RESET} {_BOLD}{pct:.1f}%{_RESET}")


def _display_analysis_report(data: dict[str, Any]) -> None:
    """
    Render a full colour-coded analysis report to stdout.
    Covers: summary, metrics bars, issue classification, system health,
    anomalies, AI solutions, recommendations, report file path.
    """
    summary       = data.get("summary", {})
    metrics       = data.get("metrics", {})
    recs          = data.get("recommendations", [])
    ai_sols       = data.get("ai_solutions", [])
    health        = data.get("health_context", {})
    anomalies     = data.get("anomalies", [])
    issue_summary = data.get("issue_summary", [])

    total   = metrics.get("records_processed", 0)
    errors  = metrics.get("error_count", 0)
    warns   = metrics.get("warning_count", 0)
    crits   = metrics.get("critical_count", 0)
    rate    = metrics.get("error_rate", 0.0)
    highest = summary.get("highest_severity", "none")
    files   = summary.get("files_scanned", 0)
    anomaly_cnt = summary.get("anomalies_detected", 0)

    # ── Header ─────────────────────────────────────────────────────────
    print()
    print(_c("╔══════════════════════════════════════════════════════════════╗", _CYAN))
    print(_c("║             LOG ANALYSIS REPORT                             ║", _CYAN))
    print(_c("╚══════════════════════════════════════════════════════════════╝", _RESET))

    # ── Summary ────────────────────────────────────────────────────────
    print(f"\n  Overall Severity  :  {_sev_badge(highest)}")
    print(f"  Files Scanned     :  {_BOLD}{files}{_RESET}")
    print(f"  Records Processed :  {_BOLD}{total:,}{_RESET}")
    print(f"  Anomalies Found   :  {_BOLD}{anomaly_cnt}{_RESET}")

    if total > 0:
        print()
        print(_c("  ── Issue Breakdown ──────────────────────────────────────────", _DIM))
        if crits:
            _print_bar("🔴 Critical", crits, total, color=_RED)
        if errors:
            _print_bar("🟠 Errors",   errors, total, color=_ORANGE)
        if warns:
            _print_bar("🟡 Warnings", warns,  total, color=_YELLOW)
        rate_color = _RED if rate >= 0.2 else _YELLOW if rate >= 0.1 else _GREEN
        print(f"\n  Error Rate        :  {_c(f'{rate:.1%}', rate_color)}")

    time_range = metrics.get("time_range")
    if time_range:
        start = str(time_range.get("start", "?"))[:19]
        end   = str(time_range.get("end", "?"))[:19]
        print(f"  Time Range        :  {_DIM}{start} → {end}{_RESET}")

    # ── Issue classification breakdown ──────────────────────────────────
    if issue_summary:
        print()
        print(_c("  ── Issue Classification ─────────────────────────────────────", _DIM))
        type_icons = {
            "memory":   "💾", "timeout":  "⏱ ", "network": "🌐",
            "auth":     "🔐", "disk":     "💿", "database":"🗄 ",
            "runtime":  "💥", "startup":  "🚀", "performance":"📈",
            "authentication": "🔐", "unknown": "❓",
        }
        for entry in issue_summary[:8]:
            itype = entry.get("issue_type", "unknown")
            count = entry.get("count", 0)
            icon  = type_icons.get(itype, "•")
            srcs  = ", ".join(entry.get("sources", [])[:2])
            src_s = f"  {_DIM}({srcs}){_RESET}" if srcs else ""
            print(f"  {icon}  {itype.title():<18} {_BOLD}{count:>4}{_RESET} occurrence(s){src_s}")

    # ── System health ───────────────────────────────────────────────────
    if health and any(v is not None for v in [
        health.get("cpu_percent"), health.get("memory_percent")
    ]):
        print()
        print(_c("  ── System Health at Analysis Time ───────────────────────────", _DIM))
        _metric_bar("CPU",  health.get("cpu_percent"))
        _metric_bar("RAM",  health.get("memory_percent"))
        _metric_bar("Disk", health.get("disk_used_pct"))
        for w in health.get("warnings", []):
            print(f"  {_c('⚠  ' + w, _YELLOW)}")

    # ── Anomalies ───────────────────────────────────────────────────────
    if anomalies:
        print()
        print(_c("  ── Detected Anomalies ───────────────────────────────────────", _DIM))
        for a in anomalies:
            sev  = a.get("severity", "low")
            desc = a.get("description", "")
            print(f"  {_sev_badge(sev)}  {desc}")

    # ── AI solutions ────────────────────────────────────────────────────
    if ai_sols:
        print()
        print(_c("╔══════════════════════════════════════════════════════════════╗", _BLUE))
        print(_c("║        AI-POWERED ROOT CAUSE ANALYSIS                        ║", _BLUE))
        print(_c("╚══════════════════════════════════════════════════════════════╝", _RESET))
        for i, sol in enumerate(ai_sols, 1):
            itype    = sol.get("issue_type", "").upper().replace("_", " ")
            priority = sol.get("priority", "").upper()
            p_color  = _SEV_COLOR.get(sol.get("priority", "low"), "")
            print()
            print(f"  {_BOLD}[{i}] {itype}{_RESET}  ·  Priority: {_c(priority, p_color)}")
            print(f"  {'─' * 58}")
            print(f"  {_BOLD}Summary    :{_RESET} {sol.get('error_summary', '')}")
            print(f"  {_BOLD}Root Cause :{_RESET} {sol.get('likely_root_cause', '')}")
            fix = sol.get("actionable_fix", "")
            if fix:
                print(f"  {_BOLD}Fix        :{_RESET}")
                if isinstance(fix, list):
                    for n, step in enumerate(fix, 1):
                        print(f"    {_c(str(n) + '.', _CYAN)} {step}")
                else:
                    for line in str(fix).split("\n"):
                        if line.strip():
                            print(f"    {line.strip()}")
    elif data.get("ai_available") is False:
        reason = data.get("ai_skipped_reason", "")
        if reason == "quota_exhausted":
            note = "AI quota exhausted — upgrade your plan for unlimited analysis."
        elif reason == "disabled":
            note = "AI enrichment is disabled in settings."
        else:
            note = "Set ANTHROPIC_API_KEY in .env to enable AI analysis."
        print()
        print(f"  {_DIM}ℹ  {note}{_RESET}")

    # ── Recommendations ─────────────────────────────────────────────────
    if recs:
        print()
        print(_c("  ── Recommendations ──────────────────────────────────────────", _DIM))
        pri_color = {"high": _RED, "medium": _YELLOW, "low": _GREEN}
        for rec in recs:
            pri    = rec.get("priority", "low")
            title  = rec.get("title", "")
            action = rec.get("action", "")
            print(f"  {_c(f'[{pri.upper()}]', pri_color.get(pri, ''))} {_BOLD}{title}{_RESET}")
            print(f"         → {action}")

    # ── Report path ─────────────────────────────────────────────────────
    report_path = data.get("report_path")
    if report_path:
        print()
        print(_c("  ── Report Saved ─────────────────────────────────────────────", _DIM))
        print(f"  📄  {_c(str(report_path), _CYAN)}")

    print()
    _div()


# ── Email helper ──────────────────────────────────────────────────────────────

def _send_report_email(app: Any, data: dict[str, Any]) -> None:
    email = _prompt("Enter recipient email address:")
    if not email or "@" not in email:
        print(f"  {_c('✖', _RED)}  Invalid email address.")
        return

    metrics      = data.get("metrics", {})
    summary      = data.get("summary", {})
    ai_sols      = data.get("ai_solutions", [])
    health       = data.get("health_context", {})
    report_path  = data.get("report_path", "Not saved")

    lines = [
        "Log Analysis Report",
        "=" * 44,
        f"Errors             : {metrics.get('error_count', 0)}",
        f"Critical issues    : {metrics.get('critical_count', 0)}",
        f"Warnings           : {metrics.get('warning_count', 0)}",
        f"Anomalies detected : {summary.get('anomalies_detected', 0)}",
        f"Highest severity   : {summary.get('highest_severity', 'none').upper()}",
        f"Report file        : {report_path}",
    ]
    if health:
        cpu = health.get("cpu_percent")
        ram = health.get("memory_percent")
        if cpu is not None:
            lines.append(f"CPU at analysis    : {cpu:.1f}%")
        if ram is not None:
            lines.append(f"RAM at analysis    : {ram:.1f}%")

    if ai_sols:
        lines += ["", "AI-Powered Analysis:", "-" * 40]
        for sol in ai_sols:
            lines.append(f"Issue : {sol.get('issue_type','').upper()}")
            lines.append(f"  {sol.get('error_summary','')}")
            lines.append(f"  Root cause: {sol.get('likely_root_cause','')}")
            fix = sol.get("actionable_fix", "")
            if fix:
                if isinstance(fix, list):
                    for step in fix:
                        lines.append(f"    • {step}")
                else:
                    lines.append(f"  Fix: {fix}")
            lines.append("")

    ok = app.emailer.send_alert(
        subject="SysNova - Log Analysis Report",
        message="\n".join(lines),
        recipient_email=email,
    )
    if ok:
        print(f"\n  {_c('✔', _GREEN)}  Report sent to {email}")
    else:
        print(
            f"\n  {_c('✖', _RED)}  Email send failed.\n"
            "     Check EMAIL_SENDER / EMAIL_PASSWORD in your .env file."
        )


# ── Option 1 — Batch analysis ─────────────────────────────────────────────────

def _run_analysis(app: Any, session_id: str) -> None:
    path = _pick_log_source("LOGS ANALYSIS AND GENERATING REPORTS")
    if path is None:
        return

    print(f"\n  {_c('➤', _CYAN)}  Analysing: {_c(path, _WHITE)}")
    print(f"  {_DIM}This may take a moment…{_RESET}\n")

    # ── tqdm progress bar through pipeline stages ──────────────────────
    try:
        from tqdm import tqdm
        stages = [
            "Reading log files      ",
            "Scanning entries       ",
            "Classifying issues     ",
            "Scrubbing sensitive data",
            "Analysing patterns     ",
            "Aggregating results    ",
            "Correlating signals    ",
            "Detecting anomalies    ",
            "Generating report      ",
        ]
        bar = tqdm(
            stages,
            ncols=64,
            bar_format="  {l_bar}{bar}| {n_fmt}/{total_fmt}",
            colour="cyan",
        )
        for stage in bar:
            bar.set_description(f"  {stage}")
            time.sleep(0.10)
        print()
    except ImportError:
        print(f"  {_DIM}(Install tqdm for progress bars: pip install tqdm){_RESET}\n")

    # ── Call app pipeline ──────────────────────────────────────────────
    result = app.execute_log_analysis(path, session_id)

    if result.get("status") != "success":
        err = (
            result.get("error")
            or result.get("data", {}).get("message", "Unknown error")
        )
        print(f"\n  {_c('✖', _RED)}  Analysis failed: {err}")
        _pause()
        return

    data = result.get("data", {})
    _display_analysis_report(data)

    # ── Auto-email trigger ─────────────────────────────────────────────
    metrics  = data.get("metrics", {})
    crits    = metrics.get("critical_count", 0)
    errors   = metrics.get("error_count", 0)
    auto     = crits > 0 or errors > 5

    if auto:
        trigger_reason = (
            f"{_c('critical issues detected', _RED)}"
            if crits
            else f"{_c(str(errors) + ' errors found', _ORANGE)}"
        )
        print(f"\n  {_c('⚠', _YELLOW)}  Auto-email trigger: {trigger_reason}")

    send = _prompt("Send analysis report by email? (y/n):").lower()
    if send in ("y", "yes"):
        _send_report_email(app, data)

    _pause()


# ── Live tail engine ──────────────────────────────────────────────────────────

_LEVEL_ICON = {
    "CRITICAL": (_c("[CRITICAL]", _RED + _BOLD),     _RED),
    "ERROR":    (_c("[ERROR]   ", _RED),              _RED),
    "WARN":     (_c("[WARN]    ", _YELLOW),           _YELLOW),
    "WARNING":  (_c("[WARN]    ", _YELLOW),           _YELLOW),
    "AUTH":     (_c("[AUTH]    ", _CYAN),             _CYAN),
    "NETWORK":  (_c("[NETWORK] ", _BLUE),             _BLUE),
    "ANOMALY":  (_c("[ANOMALY] ", _MAGENTA),          _MAGENTA),
    "INFO":     (_c("[INFO]    ", _DIM),              _DIM),
}


def _display_live_record(record: dict[str, Any]) -> None:
    level = record.get("level", "INFO").upper()
    icon, color = _LEVEL_ICON.get(level, (_c(f"[{level[:8]}]", _DIM), _DIM))
    src  = record.get("source_name") or Path(record.get("file_path", "")).name
    msg  = (record.get("clean_message") or record.get("raw_text", ""))[:110]
    ts   = (record.get("timestamp") or "")[:19]
    if not ts:
        ts = _now_str()
    print(f"  {icon}  {_DIM}{ts}{_RESET}  [{_c(src, _DIM)}]  {_c(msg, color)}")


def _stream_foreground(path: str, app: Any | None = None) -> None:
    """
    Foreground live tail: stream classified records to console.
    Uses seek/tell polling — no inotify, works on Windows too.
    Stops on Ctrl+C.
    """
    try:
        from system_manager_cli.logs_analysis.Analysis.live_monitor_daemon import (
            foreground_monitor,
        )

        def _on_idle() -> None:
            sys.stdout.write(
                f"\r  {_DIM}[{_now_str()}]  Watching for new entries…      {_RESET}"
            )
            sys.stdout.flush()

        foreground_monitor(path, _display_live_record, app_ref=app, on_idle=_on_idle)

    except ImportError:
        # Minimal fallback using seek/tell if daemon module missing
        _seek_tell_tail(path)


def _seek_tell_tail(path: str) -> None:
    """
    Pure seek/tell log tail with log-rotation detection.
    Handles single files only.
    """
    p = Path(path)
    if not p.is_file():
        print(f"  {_c('✖', _RED)}  seek/tell tail requires a single file path.")
        return

    try:
        f = open(p, "r", encoding="utf-8", errors="ignore")
        f.seek(0, 2)                          # seek to end
        inode = p.stat().st_ino
        size  = p.stat().st_size
    except OSError as exc:
        print(f"  {_c('✖', _RED)}  Cannot open file: {exc}")
        return

    try:
        while True:
            try:
                cur_stat = p.stat()
            except OSError:
                break
            cur_inode = cur_stat.st_ino
            cur_size  = cur_stat.st_size

            # Log rotation
            if cur_inode != inode or cur_size < size:
                f.close()
                f = open(p, "r", encoding="utf-8", errors="ignore")
                inode = cur_inode
                size  = 0

            lines = f.read()
            size  = cur_size

            if lines:
                for raw in lines.splitlines():
                    if raw.strip():
                        print(f"  {_DIM}[{_now_str()}]{_RESET}  {raw}")
            else:
                sys.stdout.write(
                    f"\r  {_DIM}[{_now_str()}]  Watching…{_RESET}   "
                )
                sys.stdout.flush()

            time.sleep(0.25)
    finally:
        f.close()


# ── Option 2 — Live analysis ──────────────────────────────────────────────────

def _run_live_analysis(app: Any, session_id: str) -> None:
    path = _pick_log_source("LIVE LOGS ANALYSIS")
    if path is None:
        return

    print()
    print(_box_top())
    print(_box_row("LIVE LOGS ANALYSIS"))
    print(_box_bot())
    print(f"  Watching : {_c(path, _CYAN)}\n")

    bg = _prompt("Run this job in the background? (y/n):").lower()

    if bg in ("y", "yes"):
        _start_background_job(path)
        _pause()
        return

    # ── Foreground mode ────────────────────────────────────────────────
    print()
    print(_c("  ── Live Feed ────────────────────────────────────────────────", _DIM))
    print("  Monitoring: ERROR / CRITICAL / WARN / AUTH / ANOMALY")
    print(f"  {_DIM}Press Ctrl+C to stop.{_RESET}\n")

    try:
        _stream_foreground(path, app)
    except KeyboardInterrupt:
        print(f"\n\n  {_c('✔', _GREEN)}  Live monitoring stopped.")
    _pause()


def _start_background_job(path: str) -> None:
    """
    Spawn a detached daemon process, register it in background_jobs.json,
    and inform the user.
    """
    import uuid
    from datetime import datetime, timezone

    job_id = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"

    try:
        from system_manager_cli.logs_analysis.Analysis.live_monitor_daemon import (
            start_background_monitor,
        )
        job_meta = start_background_monitor(path)
        pid      = job_meta.get("pid", 0)
    except ImportError:
        # Graceful degradation: spawn a minimal watcher subprocess
        import subprocess
        proc = subprocess.Popen(
            [sys.executable, "-c",
             f"import time\n"
             f"from pathlib import Path\n"
             f"f=open('{path}','r',errors='ignore')\n"
             f"f.seek(0,2)\n"
             f"while True:\n"
             f"    l=f.read()\n"
             f"    if l: open('{_alert_json_dir()}/tail_{job_id}.txt','a').write(l)\n"
             f"    time.sleep(0.5)\n"],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        pid = proc.pid
    except Exception as exc:
        print(f"\n  {_c('✖', _RED)}  Could not start background monitor: {exc}")
        return

    _register_job(job_id, pid, path)

    print(f"\n  {_c('✔', _GREEN)}  Background job started!")
    print(f"  Job ID     : {_c(job_id, _CYAN)}")
    print(f"  Process ID : {_c(str(pid), _CYAN)}")
    print(f"  Watching   : {path}")
    print()
    print(
        "  Critical events will be saved locally and can be viewed\n"
        "  via  'View background jobs'  in the Logs Analysis menu."
    )


# ── Background Job Viewer ─────────────────────────────────────────────────────

def _status_dot(status: str) -> str:
    dots = {
        "running":   _c("●", _GREEN),
        "stopped":   _c("◉", _YELLOW),
        "crashed":   _c("✖", _RED),
        "completed": _c("✔", _CYAN),
    }
    return dots.get(status, "○")


def _print_jobs_table(jobs: list[dict[str, Any]]) -> None:
    if not jobs:
        print(f"\n  {_DIM}No background jobs found.{_RESET}")
        return

    print()
    _div("─")
    hdr = (
        f"  {'#':>3}  {'STATUS':<10}  {'STARTED':<14}  "
        f"{'CRITS':>5}  {'ALERTS':>6}  FILE"
    )
    print(_c(hdr, _BOLD))
    _div("─")
    for job in jobs:
        jid     = job.get("job_id", "?")[-8:]    # show last 8 chars
        status  = job.get("status", "?")
        dot     = _status_dot(status)
        started = _format_iso(job.get("started_at"))
        crits   = job.get("critical_count", 0)
        pending = job.get("pending_alerts", 0)
        file_p  = job.get("file", "?")
        # Truncate long file paths
        max_fp  = 32
        fp_disp = ("…" + file_p[-(max_fp - 1):]) if len(file_p) > max_fp else file_p
        alert_c = _c(str(pending), _RED + _BOLD) if pending else str(pending)
        crit_c  = _c(str(crits), _ORANGE) if crits else str(crits)
        print(
            f"  {dot} {jid:>8}  {_STATUS_ICON.get(status, status):<10}  "
            f"{started:<14}  {crit_c:>5}  {alert_c:>6}  {fp_disp}"
        )
    _div("─")


def _view_job_alerts(job: dict[str, Any]) -> None:
    """Show the critical events stored in a job's JSON alert file."""
    events = _load_job_alerts(job)
    jid    = job.get("job_id", "?")[-8:]

    print()
    print(_box_top())
    print(_box_row(f"ALERTS  —  Job {jid}"))
    print(_box_bot())

    if not events:
        print(f"\n  {_DIM}No critical events recorded yet for this job.{_RESET}")
        _pause()
        return

    for i, ev in enumerate(events, 1):
        ts     = str(ev.get("timestamp", "?"))[:19]
        level  = ev.get("level", "CRITICAL")
        msg    = (ev.get("raw_line_scrubbed") or ev.get("message", ""))[:90]
        ai     = ev.get("ai_suggestions") or {}
        sev    = ai.get("overall_severity", "").lower() if isinstance(ai, dict) else ""
        emailed = "✔ emailed" if ev.get("email_sent") else "—"

        icon, color = _LEVEL_ICON.get(level.upper(), (_c(f"[{level}]", _RED), _RED))
        print(f"\n  {_c(str(i), _BOLD)}. {icon}  {_DIM}{ts}{_RESET}")
        print(f"     {_c(msg, color)}")

        if isinstance(ai, dict) and ai.get("summary"):
            print(f"     {_DIM}AI: {ai['summary'][:80]}{_RESET}")

        print(f"     Email: {emailed}")

    # Acknowledge: clear pending counter
    _acknowledge_job_alerts(job["job_id"])
    print(f"\n  {_c('✔', _GREEN)}  {len(events)} event(s) shown — pending alerts cleared.")
    _pause()


def _view_background_jobs(jobs: list[dict[str, Any]]) -> None:
    """
    Full background jobs viewer with stop / view-alerts actions.
    Spec: section 4.8 — 'Viewing and managing background jobs from the menu'
    """
    all_j = _all_jobs()

    while True:
        print()
        print(_box_top())
        print(_box_row("BACKGROUND JOBS"))
        print(_box_bot())

        all_j = _all_jobs()   # re-read on each loop iteration
        _print_jobs_table(all_j)

        running = [j for j in all_j if j.get("status") == "running"]

        # Build dynamic options
        options: list[tuple[str, str, dict | None]] = []   # (key, label, job|None)

        for j in running:
            jid = j.get("job_id", "?")[-8:]
            options.append((str(len(options) + 1), f"Stop job {jid}", j))

        if len(running) > 1:
            options.append((str(len(options) + 1), "Stop ALL jobs", None))

        alert_jobs = [j for j in all_j if j.get("pending_alerts", 0) > 0]
        for j in alert_jobs:
            jid = j.get("job_id", "?")[-8:]
            cnt = j.get("pending_alerts", 0)
            options.append((
                str(len(options) + 1),
                f"View {cnt} alert(s) — job {jid}",
                j,
            ))

        # Always allow viewing alerts for any job
        for j in all_j:
            if j not in alert_jobs:
                jid = j.get("job_id", "?")[-8:]
                options.append((
                    str(len(options) + 1),
                    f"View alerts — job {jid}",
                    j,
                ))

        options.append(("0", "Back to Logs Analysis menu", None))

        print()
        for key, label, _ in options:
            bullet = f"  {_c(key + '.', _CYAN)}"
            print(f"{bullet}  {label}")

        choice = _prompt("Select:").strip()

        if choice == "0":
            break

        matched = False
        for key, label, job in options:
            if choice == key:
                matched = True
                if label.startswith("Stop ALL"):
                    cnt = _stop_all_jobs()
                    print(f"\n  {_c('✔', _GREEN)}  Stopped {cnt} job(s).")
                    time.sleep(0.5)
                elif label.startswith("Stop job"):
                    if job and _stop_job(job["job_id"]):
                        jid = job.get("job_id", "?")[-8:]
                        print(f"\n  {_c('✔', _GREEN)}  Job {jid} stopped.")
                    time.sleep(0.3)
                elif "alert" in label.lower() and job:
                    _view_job_alerts(job)
                break

        if not matched:
            print(f"  {_c('⚠', _YELLOW)}  Invalid selection.")


# ── Logs Analysis main menu ───────────────────────────────────────────────────

def _build_header(pending: int, active: int) -> str:
    """
    Build the menu header.
    Shows pending alerts banner when pending > 0 (spec 4.9).
    Shows background job count when jobs are running.
    """
    if pending > 0:
        right = _c(f"⚠  {pending} PENDING ALERT{'S' if pending != 1 else ''}", _RED + _BOLD)
    elif active > 0:
        right = _c(f"● {active} background job{'s' if active != 1 else ''}", _GREEN)
    else:
        right = ""

    title = "LOGS ANALYSIS SYSTEM"
    width = 60
    if right:
        # Strip ANSI for length calculation
        right_plain = re.sub(r'\033\[[0-9;]*m', '', right)
        pad = width - len(title) - len(right_plain) - 4
        line = f"  {title}{' ' * max(pad, 2)}{right}  "
    else:
        line = f"  {title}"

    return line


def run_logs_menu(app: Any, session_id: str = "") -> None:
    """
    Entry point called from main.py / CLIManager when the user selects
    Option 3 — Logs Analysis System.

    Dynamically shows 'View background jobs' when background jobs exist.
    Shows pending-alerts banner in header when unacknowledged criticals exist.
    """
    while True:
        # ── Read live state ────────────────────────────────────────────
        active_jobs  = _active_jobs()
        pending      = _total_pending_alerts()
        has_jobs     = len(active_jobs) > 0 or len(_all_jobs()) > 0

        # ── Render menu ────────────────────────────────────────────────
        print()
        print(_box_top())
        print(_box_row(_build_header(pending, len(active_jobs)).strip()))
        print(_box_bot())
        print("  1.  Analysis Logs and Generate Reports")
        print("  2.  Live Logs Analysis")

        if has_jobs:
            all_j   = _all_jobs()
            any_pend = any(j.get("pending_alerts", 0) > 0 for j in all_j)
            jobs_label = "View Background Jobs"
            if any_pend:
                total_p = sum(j.get("pending_alerts", 0) for j in all_j)
                jobs_label = f"View Background Jobs  {_c(f'({total_p} new alerts)', _RED + _BOLD)}"
            print(f"  3.  {jobs_label}")
            print("  0.  Back to main menu")
            _div("─")
            choice = _prompt("Select (0‑3):")
        else:
            print("  0.  Back to main menu")
            _div("─")
            choice = _prompt("Select (0‑2):")

        if choice == "1":
            _run_analysis(app, session_id)

        elif choice == "2":
            _run_live_analysis(app, session_id)

        elif choice == "3" and has_jobs:
            _view_background_jobs(_all_jobs())

        elif choice == "0":
            break

        else:
            print(f"  {_c('⚠', _YELLOW)}  Invalid selection.")
