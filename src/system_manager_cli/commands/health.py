"""
commands/health.py — Direct CLI handler for: sysmanager health

Usage
─────
    sysmanager health                    # One-shot health check, then exit
    sysmanager health --watch            # Auto-refresh every --interval seconds
    sysmanager health --interval 5       # Custom refresh rate
    sysmanager health --json             # Machine-readable JSON output
    sysmanager health --quiet            # Suppress decorative lines
    sysmanager health --verbose          # Include all path / directory checks

Exit codes
──────────
    0   healthy
    1   warning
    2   critical
    3   error / exception
"""

from __future__ import annotations

import json
import sys
import time
from argparse import Namespace
from typing import Any


# ── UI helpers (graceful degradation) ─────────────────────────────────────────

def _try_theme():
    try:
        from system_manager_cli.ulits.theme import T, colorize
        from system_manager_cli.ulits.screen import (
            box_top, box_bottom, box_row, section,
            command_bar, term_width, progress_bar,
        )
        return T, colorize, box_top, box_bottom, box_row, section, command_bar, term_width, progress_bar
    except ImportError:
        class _T:
            RESET = BOLD = DIM = PRIMARY = SUCCESS = WARNING = ERROR = ""
            HEADER = WHITE = DIM_TEXT = ""
        T = _T()
        def colorize(t, *_): return t
        def box_top(w=0, color=""): return "=" * (w or 60)
        def box_bottom(w=0, color=""): return "=" * (w or 60)
        def box_row(t, w=0, padding=2, color=""): return f"  {t}"
        def section(label="", w=0, color=""): return "── " + label + " ──"
        def command_bar(hints=None): print("─" * 60)
        def term_width(): return 60
        def progress_bar(v, mx=100, w=20, label="", unit="%", **kw):
            pct = int(v / mx * 100) if mx else 0
            return f"{label} {pct}{unit}"
        return T, colorize, box_top, box_bottom, box_row, section, command_bar, term_width, progress_bar


def _err(msg: str) -> None:
    print(f"  [ERROR] {msg}", file=sys.stderr)


# ── Formatting helpers ─────────────────────────────────────────────────────────

def _pct_color(pct: float | None, T, colorize) -> str:
    if pct is None:
        return colorize("n/a", T.DIM)
    if pct >= 90:
        return colorize(f"{pct:.1f}%", T.ERROR)
    if pct >= 75:
        return colorize(f"{pct:.1f}%", T.WARNING)
    return colorize(f"{pct:.1f}%", T.SUCCESS)


def _status_icon(status: str, T, colorize) -> str:
    return {
        "healthy":  colorize("● healthy",  T.SUCCESS),
        "warning":  colorize("⚠ warning",  T.WARNING),
        "critical": colorize("✖ critical", T.ERROR),
    }.get(status, colorize(status, T.DIM))


def _fmt_bytes(n: int | None) -> str:
    if n is None:
        return "n/a"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.0f} PB"


# ── Renderers ─────────────────────────────────────────────────────────────────

def _render_human(data: dict[str, Any], args: Namespace) -> None:
    (T, colorize, box_top, box_bottom, box_row,
     section, command_bar, term_width, progress_bar) = _try_theme()

    w = min(term_width() - 2, 66)
    quiet   = getattr(args, "quiet", False)
    verbose = getattr(args, "verbose", False)
    watch   = getattr(args, "watch", False)

    overall = data.get("overall_status", "unknown")
    status_s = _status_icon(overall, T, colorize)

    if not quiet:
        print()
        print(colorize(box_top(w), T.PRIMARY))
        hdr = f"  HEALTH MONITOR  {colorize('│', T.DIM)}  {status_s}"
        print(
            colorize("║", T.PRIMARY)
            + f"  {colorize('HEALTH MONITOR', T.BOLD + T.WHITE)}"
            + f"  {colorize('│', T.DIM)}  {status_s}"
            + " " * max(0, w - 36)
            + "  "
            + colorize("║", T.PRIMARY)
        )
        print(colorize(box_bottom(w), T.PRIMARY))

    # CPU
    cpu = data.get("cpu_percent")
    print()
    print(colorize("  ── CPU ──────────────────────────────────────────", T.DIM))
    bar = progress_bar(cpu or 0, 100, 28, unit="%")
    pct_s = _pct_color(cpu, T, colorize)
    print(f"  {bar}   ({pct_s})")

    # Memory
    ram = data.get("memory_percent")
    print()
    print(colorize("  ── MEMORY ──────────────────────────────────────", T.DIM))
    bar = progress_bar(ram or 0, 100, 28, unit="%")
    pct_s = _pct_color(ram, T, colorize)
    print(f"  {bar}   ({pct_s})")

    # Disk
    disk = data.get("disk", {})
    disk_pct  = disk.get("used_percent")
    free_bytes = disk.get("free_bytes", 0)
    print()
    print(colorize("  ── DISK ────────────────────────────────────────", T.DIM))
    bar = progress_bar(disk_pct or 0, 100, 28, unit="%")
    pct_s = _pct_color(disk_pct, T, colorize)
    free_s = colorize(_fmt_bytes(free_bytes) + " free", T.SUCCESS)
    print(f"  {bar}   ({pct_s})   {free_s}")

    # Warnings
    warnings = data.get("warnings", [])
    if warnings:
        print()
        print(colorize("  ── WARNINGS ────────────────────────────────────", T.DIM))
        for w_msg in warnings:
            print(f"  {colorize('⚠', T.WARNING)}  {colorize(w_msg, T.WARNING)}")

    # Verbose: directory checks
    if verbose:
        paths = data.get("paths", {})
        if paths:
            print()
            print(colorize("  ── DIRECTORIES ─────────────────────────────────", T.DIM))
            labels = {
                "data_dir":    "Data dir   ",
                "logs_dir":    "Logs dir   ",
                "reports_dir": "Reports    ",
                "backup_dir":  "Backup     ",
            }
            for key, label in labels.items():
                ok = paths.get(key, False)
                sym = colorize("✔", T.SUCCESS) if ok else colorize("✖", T.ERROR)
                print(f"  {sym}  {colorize(label, T.DIM)}")

    print()
    if watch:
        print(colorize("  Ctrl+C to stop watching.", T.DIM))


def _render_json(data: dict[str, Any]) -> None:
    out = {
        "overall_status": data.get("overall_status", "unknown"),
        "cpu_percent":    data.get("cpu_percent"),
        "memory_percent": data.get("memory_percent"),
        "disk": {
            "used_percent": data.get("disk", {}).get("used_percent"),
            "free_bytes":   data.get("disk", {}).get("free_bytes"),
        },
        "warnings":       data.get("warnings", []),
        "config_valid":   data.get("config_valid", False),
    }
    print(json.dumps(out, indent=2))


# ── Exit code helper ───────────────────────────────────────────────────────────

def _exit_code(data: dict[str, Any]) -> int:
    status = data.get("overall_status", "unknown")
    return {"healthy": 0, "warning": 1, "critical": 2}.get(status, 3)


# ── Public entry point ─────────────────────────────────────────────────────────

def run(app, args: Namespace) -> int:
    """
    Execute the health command.

    Args:
        app:  SystemManagerApp instance.
        args: Parsed argparse Namespace from cli_parser.build_parser().

    Returns:
        Integer exit code.
    """
    use_json = getattr(args, "json", False)
    watch    = getattr(args, "watch", False)
    interval = max(1, getattr(args, "interval", 3))

    try:
        if watch:
            while True:
                result = app.execute_health_check()
                if result.get("status") != "success":
                    _err(f"Health check failed: {result.get('error', 'unknown')}")
                    return 3

                health_data = result.get("data", {})

                if use_json:
                    _render_json(health_data)
                else:
                    _render_human(health_data, args)

                time.sleep(interval)
        else:
            result = app.execute_health_check()
            if result.get("status") != "success":
                _err(f"Health check failed: {result.get('error', 'unknown')}")
                return 3

            health_data = result.get("data", {})

            if use_json:
                _render_json(health_data)
            else:
                _render_human(health_data, args)

            return _exit_code(health_data)

    except KeyboardInterrupt:
        print()  # clean newline after Ctrl+C
        return 0
    except Exception as exc:
        _err(f"Unexpected error in health command: {exc}")
        if getattr(args, "verbose", False):
            import traceback
            traceback.print_exc()
        return 3
