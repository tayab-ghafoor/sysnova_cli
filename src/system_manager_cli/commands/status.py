"""
commands/status.py — Direct CLI handler for: sysmanager status

Displays a compact one-screen system snapshot:
  • CPU / RAM / Disk progress bars
  • Network I/O
  • Recent backup activity
  • Recent log analysis result
  • Next scheduled task
  • Backend connection & background job counts

Usage
─────
    sysmanager status           # Human-readable snapshot
    sysmanager status --json    # Machine-readable JSON

Exit codes
──────────
    0   healthy
    1   warning
    2   critical
    3   error
"""

from __future__ import annotations

import json
import sys
from argparse import Namespace
from datetime import datetime, timezone
from typing import Any


# ── UI helpers ────────────────────────────────────────────────────────────────

def _try_theme():
    try:
        from system_manager_cli.ulits.theme import T, colorize
        from system_manager_cli.ulits.screen import (
            box_top, box_bottom, box_row, section,
            term_width, progress_bar,
        )
        return T, colorize, box_top, box_bottom, box_row, section, term_width, progress_bar
    except ImportError:
        class _T:
            RESET = BOLD = DIM = PRIMARY = SUCCESS = WARNING = ERROR = ""
            HEADER = WHITE = ACCENT = ""
        T = _T()
        def colorize(t, *_): return t
        def box_top(w=0, color=""): return "=" * (w or 60)
        def box_bottom(w=0, color=""): return "=" * (w or 60)
        def box_row(t, w=0, padding=2, color=""): return f"  {t}"
        def section(label="", w=0, color=""): return f"── {label} ──"
        def term_width(): return 60
        def progress_bar(v, mx=100, w=20, label="", unit="%", **kw):
            pct = int(v / mx * 100) if mx else 0
            return f"{label} {pct}{unit}"
        return T, colorize, box_top, box_bottom, box_row, section, term_width, progress_bar


def _err(msg: str) -> None:
    print(f"  [ERROR] {msg}", file=sys.stderr)


# ── Data collectors ───────────────────────────────────────────────────────────

def _get_health(app) -> dict[str, Any]:
    try:
        result = app.execute_health_check()
        if result.get("status") == "success":
            return result.get("data", {})
    except Exception:
        pass
    return {}


def _get_network() -> dict[str, Any]:
    try:
        import psutil
        import time as _t
        s1 = psutil.net_io_counters()
        _t.sleep(0.2)
        s2 = psutil.net_io_counters()
        up   = (s2.bytes_sent - s1.bytes_sent) / 0.2 / (1024 * 1024)
        down = (s2.bytes_recv - s1.bytes_recv) / 0.2 / (1024 * 1024)
        return {"up": round(up, 2), "down": round(down, 2), "ok": True}
    except Exception:
        return {"ok": False}


def _get_recent_backup() -> dict[str, Any]:
    """Return the most recent backup record from local SQLite history."""
    try:
        from system_manager_cli.core.backup_orchestrator import load_backup_history
        history = load_backup_history(limit=1)
        if history:
            return history[0]
    except Exception:
        pass
    return {}


def _get_next_task() -> dict[str, Any]:
    """Return the next due scheduled task."""
    try:
        from system_manager_cli.core.task_scheduler import TaskScheduler
        scheduler = TaskScheduler()
        tasks = [t for t in scheduler.get_all_tasks() if t.status == "ACTIVE" and t.next_run]
        if not tasks:
            return {}
        tasks.sort(key=lambda t: t.next_run or "")
        task = tasks[0]
        return {"display_type": task.display_type(), "next_run": task.next_run, "run_time": task.run_time}
    except Exception:
        return {}


def _get_user_profile() -> dict[str, Any]:
    """Return user profile from backend if available."""
    try:
        from system_manager_cli.core.backend_client import BackendClient
        backend = BackendClient()
        if backend.ping():
            profile = backend.get_profile()
            usage = backend.get_usage_stats()
            return {
                "is_pro": profile.get("is_pro", False),
                "plan": profile.get("plan", "free"),
                "usage_count": usage.get("usage_count", 0),
                "usage_limit": usage.get("usage_limit", 3),
                "ok": True
            }
    except Exception:
        pass
    return {"ok": False}


def _get_active_jobs() -> int:
    """Count running background monitor jobs."""
    try:
        import json as _json
        from pathlib import Path
        from system_manager_cli.config.config import Config
        reg = Path(Config.DATA_DIR) / "background_jobs.json"
        if not reg.exists():
            return 0
        data = _json.loads(reg.read_text(encoding="utf-8"))
        return sum(1 for j in data.get("jobs", []) if j.get("status") == "running")
    except Exception:
        return 0


def _get_pending_alerts() -> int:
    try:
        import json as _json
        from pathlib import Path
        from system_manager_cli.config.config import Config
        reg = Path(Config.DATA_DIR) / "background_jobs.json"
        if not reg.exists():
            return 0
        data = _json.loads(reg.read_text(encoding="utf-8"))
        return sum(j.get("pending_alerts", 0) for j in data.get("jobs", []))
    except Exception:
        return 0


# ── Time helpers ──────────────────────────────────────────────────────────────

def _time_ago(iso: str | None) -> str:
    if not iso:
        return "never"
    try:
        dt  = datetime.fromisoformat(iso)
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        diff = now - dt
        secs = diff.total_seconds()
        if secs < 60:
            return "just now"
        if secs < 3600:
            return f"{int(secs // 60)}m ago"
        if secs < 86400:
            return f"{int(secs // 3600)}h ago"
        return f"{int(secs // 86400)}d ago"
    except ValueError:
        return iso[:16]


def _next_run_label(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt  = datetime.fromisoformat(iso)
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        diff = (dt - now).total_seconds()
        if diff < 0:
            return "overdue"
        if diff < 60:
            return f"in {int(diff)}s"
        if diff < 3600:
            return f"in {int(diff // 60)}m"
        if diff < 86400:
            h = int(diff // 3600)
            return f"in {h}h"
        return dt.strftime("%d %b %H:%M")
    except ValueError:
        return iso[:16]


# ── Human render ──────────────────────────────────────────────────────────────

def _render_human(
    health:  dict[str, Any],
    network: dict[str, Any],
    backup:  dict[str, Any],
    task:    dict[str, Any],
    user_profile: dict[str, Any],
    jobs:    int,
    alerts:  int,
    backend: bool,
    args:    Namespace,
) -> None:
    (T, colorize, box_top, box_bottom, box_row,
     section, term_width, progress_bar) = _try_theme()

    quiet = getattr(args, "quiet", False)
    w     = min(term_width() - 2, 68)

    overall = health.get("overall_status", "unknown")
    overall_color = {
        "healthy":  T.SUCCESS,
        "warning":  T.WARNING,
        "critical": T.ERROR,
    }.get(overall, T.DIM)

    # ── Header ─────────────────────────────────────────────────────────
    ts = datetime.now().strftime("%H:%M:%S")

    if not quiet:
        print()
        print(colorize(box_top(w), T.PRIMARY))
        inner = (
            f"  {colorize('⚡ SysNova', T.HEADER)}"
            f"  {colorize('│', T.DIM)}"
            f"  {colorize(ts, T.DIM)}"
            f"  {colorize('│', T.DIM)}"
            f"  {colorize(overall.upper(), overall_color + T.BOLD)}"
        )
        # Pad inner to width
        import re
        plain = re.sub(r'\033\[[0-9;]*m', '', inner)
        pad   = max(0, w - len(plain))
        print(colorize("║", T.PRIMARY) + inner + " " * pad + "  " + colorize("║", T.PRIMARY))
        print(colorize(box_bottom(w), T.PRIMARY))

    # ── SYSTEM metrics ──────────────────────────────────────────────────
    print()
    print(colorize("  ── SYSTEM ─────────────────────────────────────────────", T.DIM))

    cpu  = health.get("cpu_percent")
    ram  = health.get("memory_percent")
    disk = health.get("disk", {}).get("used_percent")

    # Inline CPU + RAM side-by-side
    bar_w = 18
    cpu_bar  = progress_bar(cpu  or 0, 100, bar_w, label="CPU",  unit="%")
    ram_bar  = progress_bar(ram  or 0, 100, bar_w, label="RAM",  unit="%")
    disk_bar = progress_bar(disk or 0, 100, bar_w, label="Disk", unit="%")

    print(f"  {cpu_bar}")
    print(f"  {ram_bar}")
    print(f"  {disk_bar}")

    if network.get("ok"):
        up_c   = T.WARNING if network["up"]   > 10 else T.SUCCESS
        down_c = T.WARNING if network["down"] > 10 else T.SUCCESS
        up_label = colorize(f"{network['up']:.2f} MB/s", up_c)
        down_label = colorize(f"{network['down']:.2f} MB/s", down_c)
        print(
            f"  {colorize('Net ', T.DIM)}  "
            f"↑ {up_label}"
            f"   ↓ {down_label}"
        )

    # ── RECENT ACTIVITY ─────────────────────────────────────────────────
    print()
    print(colorize("  ── RECENT ACTIVITY ──────────────────────────────────────", T.DIM))

    # Backup
    if backup:
        b_ok   = backup.get("success", False)
        b_sym  = colorize("✔", T.SUCCESS) if b_ok else colorize("✖", T.ERROR)
        b_when = _time_ago(backup.get("started_at") or backup.get("completed_at"))
        b_dest = (backup.get("destination") or backup.get("destination_path") or "")[:32]
        b_files = backup.get("file_count", "?")
        print(f"  {b_sym}  {colorize('Backup', T.DIM):<10} {b_when:<12}  {b_dest}  ({b_files} files)")
    else:
        print(f"  {colorize('–', T.DIM)}  {colorize('Backup', T.DIM):<10} {colorize('no history', T.DIM)}")

    # Next scheduled task
    if task:
        next_r = _next_run_label(task.get("next_run"))
        ttype  = task.get("display_type", "Task")
        rt     = task.get("run_time", "")
        print(f"  {colorize('⏰', '')}  {colorize('Next task', T.DIM):<10} {next_r:<12}  {ttype} at {rt}")
    else:
        print(f"  {colorize('–', T.DIM)}  {colorize('Next task', T.DIM):<10} {colorize('none scheduled', T.DIM)}")

    # ── STATUS ROW ──────────────────────────────────────────────────────
    print()
    print(colorize("  ── STATUS ───────────────────────────────────────────────", T.DIM))

    be_label = colorize("● Connected", T.SUCCESS) if backend else colorize("◉ Offline", T.WARNING)
    jobs_c   = colorize(str(jobs),   T.SUCCESS if jobs   else T.DIM)
    alerts_c = colorize(str(alerts), T.ERROR   if alerts else T.DIM)

    print(
        f"  BACKEND {be_label}"
        f"    JOBS {jobs_c} running"
        f"    ALERTS {alerts_c} pending"
    )

    if user_profile.get("ok"):
        plan = user_profile.get("plan", "free")
        is_pro = user_profile.get("is_pro", False)
        usage = user_profile.get("usage_count", 0)
        limit = user_profile.get("usage_limit", 3)
        plan_color = T.SUCCESS if is_pro else T.DIM
        usage_color = T.WARNING if usage >= limit else T.SUCCESS
        print(
            f"  USER   {colorize(plan.upper(), plan_color)}"
            f"    AI USAGE {colorize(str(usage), usage_color)}/{limit} used"
        )

    # Health warnings
    for w_msg in health.get("warnings", []):
        print(f"  {colorize('⚠', T.WARNING)}  {colorize(w_msg, T.WARNING)}")

    print()


def _render_json(
    health: dict[str, Any],
    network: dict[str, Any],
    backup: dict[str, Any],
    task: dict[str, Any],
    user_profile: dict[str, Any],
    jobs: int,
    alerts: int,
    backend: bool,
) -> None:
    out = {
        "overall_status": health.get("overall_status", "unknown"),
        "cpu_percent":    health.get("cpu_percent"),
        "memory_percent": health.get("memory_percent"),
        "disk": {
            "used_percent": health.get("disk", {}).get("used_percent"),
            "free_bytes":   health.get("disk", {}).get("free_bytes"),
        },
        "network": {
            "upload_mbps":   network.get("up"),
            "download_mbps": network.get("down"),
        } if network.get("ok") else None,
        "last_backup":   backup or None,
        "next_task":     task or None,
        "user_profile":  user_profile if user_profile.get("ok") else None,
        "background_jobs_running": jobs,
        "pending_alerts": alerts,
        "backend_connected": backend,
        "warnings": health.get("warnings", []),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    print(json.dumps(out, indent=2, default=str))


# ── Exit code ─────────────────────────────────────────────────────────────────

def _exit_code(health: dict[str, Any]) -> int:
    status = health.get("overall_status", "unknown")
    return {"healthy": 0, "warning": 1, "critical": 2}.get(status, 3)


# ── Public entry point ─────────────────────────────────────────────────────────

def run(app, args: Namespace) -> int:
    """
    Execute the status command.

    Args:
        app:  SystemManagerApp instance.
        args: Parsed argparse Namespace.

    Returns:
        Integer exit code.
    """
    use_json = getattr(args, "json", False)

    try:
        # Collect all data (non-fatal on individual failures)
        health  = _get_health(app)
        network = _get_network()
        backup  = _get_recent_backup()
        task    = _get_next_task()
        user_profile = _get_user_profile()
        jobs    = _get_active_jobs()
        alerts  = _get_pending_alerts()

        # Backend connectivity
        try:
            backend = app.backend.ping()
        except Exception:
            backend = False

        if use_json:
            _render_json(health, network, backup, task, user_profile, jobs, alerts, backend)
        else:
            _render_human(health, network, backup, task, user_profile, jobs, alerts, backend, args)

        return _exit_code(health)

    except KeyboardInterrupt:
        print()
        return 0
    except Exception as exc:
        _err(f"Status check failed: {exc}")
        if getattr(args, "verbose", False):
            import traceback
            traceback.print_exc()
        return 3
