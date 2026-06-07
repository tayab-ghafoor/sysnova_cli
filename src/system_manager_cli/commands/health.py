"""
commands/health.py — Direct CLI handler for: sysmanager health

Usage
─────
    sysmanager health                    One-shot health check, then exit
    sysmanager health --watch            Auto-refresh every --interval seconds
    sysmanager health --interval 5       Custom refresh rate (default: 3 s)
    sysmanager health --json             Machine-readable JSON output, then exit
    sysmanager health --quiet            Suppress decorative chrome
    sysmanager health --verbose          Include directory checks + network I/O

Exit codes
──────────
    0   healthy
    1   warning
    2   critical
    3   error / exception
"""

from __future__ import annotations

import json
import os
import sys
import time
from argparse import Namespace
from datetime import datetime
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


# ── Screen helpers ─────────────────────────────────────────────────────────────

def _clear_screen() -> None:
    """Clear the terminal screen in a cross-platform way."""
    if os.name == "nt":
        os.system("cls")
    else:
        # ANSI escape: clear screen + move cursor to top-left.
        # Faster than a subprocess and preserves terminal scrollback.
        print("\033[2J\033[H", end="", flush=True)


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
    }.get(status, colorize(f"? {status}", T.DIM))


def _fmt_bytes(n: int | None) -> str:
    if n is None:
        return "n/a"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.0f} PB"


def _fmt_bytes_per_sec(n: int | None) -> str:
    """Format a bytes-per-second rate as a human string."""
    if n is None:
        return "n/a"
    return f"{_fmt_bytes(n)}/s"


# ── Optional metrics: network I/O, temperature ───────────────────────────────

def _get_network_io() -> dict[str, Any]:
    """Return best-effort network send/recv rates (bytes/sec) since last call."""
    try:
        import psutil
        counters = psutil.net_io_counters()
        now = time.monotonic()
        prev = getattr(_get_network_io, "_prev", None)
        _get_network_io._prev = (now, counters)  # type: ignore[attr-defined]

        if prev is None:
            return {"bytes_sent_rate": None, "bytes_recv_rate": None}

        prev_time, prev_counters = prev
        dt = now - prev_time
        if dt <= 0:
            return {"bytes_sent_rate": None, "bytes_recv_rate": None}

        return {
            "bytes_sent_rate": (counters.bytes_sent - prev_counters.bytes_sent) / dt,
            "bytes_recv_rate": (counters.bytes_recv - prev_counters.bytes_recv) / dt,
        }
    except Exception:
        return {"bytes_sent_rate": None, "bytes_recv_rate": None}


def _get_cpu_temp() -> float | None:
    """Return average CPU temperature in °C, or None if unavailable."""
    try:
        import psutil
        temps = psutil.sensors_temperatures()
        if not temps:
            return None
        # Try common sensor keys in priority order.
        for key in ("coretemp", "cpu_thermal", "k10temp", "acpitz"):
            entries = temps.get(key, [])
            if entries:
                vals = [e.current for e in entries if e.current]
                if vals:
                    return sum(vals) / len(vals)
        # Fall back to the first available sensor group.
        for entries in temps.values():
            vals = [e.current for e in entries if e.current]
            if vals:
                return sum(vals) / len(vals)
    except Exception:
        pass
    return None


def _get_process_count() -> int | None:
    """Return the total number of running processes."""
    try:
        import psutil
        return len(psutil.pids())
    except Exception:
        return None


# ── Renderers ─────────────────────────────────────────────────────────────────

def _render_human(data: dict[str, Any], args: Namespace, iteration: int = 0) -> None:
    (T, colorize, box_top, box_bottom, box_row,
     section, command_bar, term_width, progress_bar) = _try_theme()

    w       = min(term_width() - 2, 70)
    quiet   = getattr(args, "quiet",   False)
    verbose = getattr(args, "verbose", False)
    watch   = getattr(args, "watch",   False)

    overall  = data.get("overall_status", "unknown")
    status_s = _status_icon(overall, T, colorize)
    now_str  = datetime.now().strftime("%H:%M:%S")

    if not quiet:
        print()
        print(colorize(box_top(w), T.PRIMARY))
        hdr_inner = (
            f"  {colorize('HEALTH MONITOR', T.BOLD + T.WHITE)}"
            f"  {colorize('│', T.DIM)}  {status_s}"
            f"  {colorize('│', T.DIM)}  {colorize(now_str, T.DIM)}"
        )
        print(colorize("║", T.PRIMARY) + hdr_inner + colorize("║", T.PRIMARY))
        print(colorize(box_bottom(w), T.PRIMARY))

    # ── CPU ───────────────────────────────────────────────────────────────────
    cpu = data.get("cpu_percent")
    print()
    print(colorize("  ── CPU ──────────────────────────────────────────────", T.DIM))
    bar = progress_bar(cpu or 0, 100, 30, unit="%")
    print(f"  {bar}   ({_pct_color(cpu, T, colorize)})", end="")

    temp = _get_cpu_temp()
    if temp is not None:
        temp_color = T.ERROR if temp >= 90 else T.WARNING if temp >= 75 else T.DIM
        print(f"   {colorize(f'{temp:.0f} °C', temp_color)}", end="")
    print()

    procs = _get_process_count()
    if procs is not None:
        print(f"  {colorize('Processes :', T.DIM)}  {colorize(str(procs), T.BOLD)}")

    # ── Memory ────────────────────────────────────────────────────────────────
    ram = data.get("memory_percent")
    print()
    print(colorize("  ── MEMORY ───────────────────────────────────────────", T.DIM))
    bar = progress_bar(ram or 0, 100, 30, unit="%")
    print(f"  {bar}   ({_pct_color(ram, T, colorize)})")

    # ── Disk ──────────────────────────────────────────────────────────────────
    disk      = data.get("disk", {})
    disk_pct  = disk.get("used_percent")
    free_bytes = disk.get("free_bytes", 0)
    print()
    print(colorize("  ── DISK ─────────────────────────────────────────────", T.DIM))
    bar = progress_bar(disk_pct or 0, 100, 30, unit="%")
    free_s = colorize(_fmt_bytes(free_bytes) + " free", T.SUCCESS)
    print(f"  {bar}   ({_pct_color(disk_pct, T, colorize)})   {free_s}")

    # ── Network I/O (verbose or watch) ────────────────────────────────────────
    if verbose or watch:
        net = _get_network_io()
        sent_rate = net.get("bytes_sent_rate")
        recv_rate = net.get("bytes_recv_rate")
        if sent_rate is not None or recv_rate is not None:
            print()
            print(colorize("  ── NETWORK ──────────────────────────────────────────", T.DIM))
            if iteration == 0 and watch:
                print(f"  {colorize('(rates available from second refresh)', T.DIM)}")
            else:
                print(
                    f"  {colorize('↑ Send :', T.DIM)}  "
                    f"{colorize(_fmt_bytes_per_sec(sent_rate), T.PRIMARY)}"
                    f"   {colorize('↓ Recv :', T.DIM)}  "
                    f"{colorize(_fmt_bytes_per_sec(recv_rate), T.PRIMARY)}"
                )

    # ── Warnings ──────────────────────────────────────────────────────────────
    warnings = data.get("warnings", [])
    if warnings:
        print()
        print(colorize("  ── WARNINGS ─────────────────────────────────────────", T.DIM))
        for w_msg in warnings:
            print(f"  {colorize('⚠', T.WARNING)}  {colorize(w_msg, T.WARNING)}")

    # ── Verbose: directory checks ─────────────────────────────────────────────
    if verbose:
        paths = data.get("paths", {})
        if paths:
            print()
            print(colorize("  ── DIRECTORIES ──────────────────────────────────────", T.DIM))
            labels = {
                "data_dir":    "Data dir   ",
                "logs_dir":    "Logs dir   ",
                "reports_dir": "Reports    ",
                "backup_dir":  "Backup     ",
            }
            for key, label in labels.items():
                ok  = paths.get(key, False)
                sym = colorize("✔", T.SUCCESS) if ok else colorize("✖", T.ERROR)
                print(f"  {sym}  {colorize(label, T.DIM)}")

    print()
    if watch and not quiet:
        interval = max(1, getattr(args, "interval", 3))
        print(
            colorize(
                f"  Refreshing every {interval}s — Ctrl+C to stop.",
                T.DIM,
            )
        )


def _render_json(data: dict[str, Any]) -> None:
    net = _get_network_io()
    out = {
        "overall_status": data.get("overall_status", "unknown"),
        "cpu_percent":    data.get("cpu_percent"),
        "cpu_temp_c":     _get_cpu_temp(),
        "memory_percent": data.get("memory_percent"),
        "disk": {
            "used_percent": data.get("disk", {}).get("used_percent"),
            "free_bytes":   data.get("disk", {}).get("free_bytes"),
        },
        "network": {
            "bytes_sent_rate": net.get("bytes_sent_rate"),
            "bytes_recv_rate": net.get("bytes_recv_rate"),
        },
        "process_count": _get_process_count(),
        "warnings":      data.get("warnings", []),
        "config_valid":  data.get("config_valid", False),
        "timestamp":     datetime.now().isoformat(),
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
    use_json = getattr(args, "json",     False)
    watch    = getattr(args, "watch",    False)
    interval = max(1, getattr(args, "interval", 3))

    # JSON mode: one shot, no watch loop.
    if use_json:
        watch = False

    try:
        iteration = 0

        while True:
            # Clear screen on every iteration in watch mode (not first time to
            # avoid flickering while the first data call is in progress).
            if watch and iteration > 0:
                _clear_screen()

            result = app.execute_health_check()

            if result.get("status") != "success":
                _err(f"Health check failed: {result.get('error', 'unknown')}")
                return 3

            health_data = result.get("data", {})

            if use_json:
                _render_json(health_data)
                return _exit_code(health_data)

            _render_human(health_data, args, iteration=iteration)

            if not watch:
                return _exit_code(health_data)

            iteration += 1
            time.sleep(interval)

    except KeyboardInterrupt:
        print()   # clean newline after Ctrl+C
        return 0
    except Exception as exc:
        _err(f"Unexpected error in health command: {exc}")
        if getattr(args, "verbose", False):
            import traceback
            traceback.print_exc()
        return 3