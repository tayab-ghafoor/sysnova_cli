"""Health Monitor CLI menu — Phase 2 redesign.

New features:
  • Progress bars for CPU / RAM / Disk
  • Network usage
  • Auto-refresh toggle
  • Directory checks
  • [R] Refresh  [A] Auto-refresh  [0] Back
  
Backward compatible: run_health_menu(app) signature unchanged.
"""

from __future__ import annotations

import time
from typing import Any

# ── Phase-1 UI helpers ─────────────────────────────────────────────────────────
try:
    from system_manager_cli.ulits.theme import T, colorize
    from system_manager_cli.ulits.screen import (
        box_top, box_bottom, box_row, section,
        command_bar, term_width, progress_bar,
    )
    _HAS_THEME = True
except ImportError:
    _HAS_THEME = False
    class _T:
        RESET = BOLD = DIM = PRIMARY = SUCCESS = WARNING = ERROR = ""
        HEADER = WHITE = DIM_TEXT = ""
    T = _T()
    def colorize(text: str, *style_codes: str) -> str:
        return text
    def box_top(width: int = 0, color: str = "") -> str:
        return "=" * (width or 60)
    def box_bottom(width: int = 0, color: str = "") -> str:
        return "=" * (width or 60)
    def box_row(text: str, width: int = 0, padding: int = 2, color: str = "") -> str:
        return f"  {text}"
    def section(label: str = "", width: int = 0, color: str = "") -> str:
        return f"── {label} " + "─" * max(0, (width or 60) - len(label) - 4)
    def command_bar(hints=None) -> None:
        print("─" * 60)
    def term_width() -> int:
        return 60
    def progress_bar(
        value: float,
        maximum: float = 100,
        width: int = 20,
        label: str = "",
        unit: str = "%",
        *,
        threshold_warn: float = 75,
        threshold_crit: float = 90,
    ) -> str:
        return f"{label} {value}/{maximum}"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _bytes_to_gb(n: int) -> str:
    return f"{n / (1024 ** 3):.1f} GB"


def _bytes_to_mb(n: int) -> str:
    return f"{n / (1024 ** 2):.1f} MB"


def _get_network() -> dict:
    try:
        import psutil
        import time as _t
        s1 = psutil.net_io_counters()
        _t.sleep(0.4)
        s2 = psutil.net_io_counters()
        up   = (s2.bytes_sent - s1.bytes_sent) / 0.4 / (1024 * 1024)
        down = (s2.bytes_recv - s1.bytes_recv) / 0.4 / (1024 * 1024)
        return {"up": up, "down": down, "ok": True}
    except Exception:
        return {"ok": False}


def _pct_icon(pct: float | None) -> str:
    if pct is None:
        return "⚪"
    if pct >= 90:
        return colorize("🔴", "")
    if pct >= 75:
        return colorize("🟡", "")
    return colorize("🟢", "")


def _fmt_pct(pct: float | None) -> str:
    if pct is None:
        return colorize("n/a", T.DIM)
    color = T.ERROR if pct >= 90 else T.WARNING if pct >= 75 else T.SUCCESS
    return colorize(f"{pct:.1f}%", color + T.BOLD)


# ─────────────────────────────────────────────────────────────────────────────
# Renderers
# ─────────────────────────────────────────────────────────────────────────────

def _render_health(data: dict[str, Any], auto_refresh: bool, refresh_sec: int) -> None:
    w = min(term_width() - 2, 66)

    # Header
    refresh_hint = (
        colorize(f"Auto-refresh: {refresh_sec}s", T.SUCCESS)
        if auto_refresh
        else colorize("Auto-refresh: OFF", T.DIM)
    )
    overall = data.get("overall_status", "unknown")
    overall_color = {
        "healthy":  T.SUCCESS,
        "warning":  T.WARNING,
        "critical": T.ERROR,
    }.get(overall, T.DIM)
    overall_s = colorize(overall.upper(), overall_color + T.BOLD)

    print()
    print(colorize(box_top(w), T.PRIMARY))
    hdr_text = f"  HEALTH MONITOR  {colorize('│', T.DIM)}  {overall_s}"
    pad = w - 4 - 16 - 3 - len(overall) - len(refresh_hint) + 20
    print(
        colorize("║", T.PRIMARY)
        + f"  {colorize('HEALTH MONITOR', T.BOLD + T.WHITE)}"
        + f"  {colorize('│', T.DIM)}  {overall_s}"
        + " " * max(0, w - 32 - len(overall))
        + f"  {refresh_hint}  "
        + colorize("║", T.PRIMARY)
    )
    print(colorize(box_bottom(w), T.PRIMARY))

    # CPU
    cpu = data.get("cpu_percent")
    print()
    print(colorize("  ── CPU ──────────────────────────────────────────", T.DIM))
    bar = progress_bar(cpu or 0, 100, 28, unit="%")
    print(f"  {_pct_icon(cpu)}  {bar}")
    try:
        import psutil
        la = psutil.getloadavg()
        print(f"      {colorize('Load avg', T.DIM)}  {la[0]:.2f}  {la[1]:.2f}  {la[2]:.2f}   (1m / 5m / 15m)")
        count = psutil.cpu_count()
        if count:
            print(f"      {colorize('Cores    ', T.DIM)}  {count}")
    except Exception:
        pass

    # Memory
    ram = data.get("memory_percent")
    print()
    print(colorize("  ── MEMORY ──────────────────────────────────────", T.DIM))
    bar = progress_bar(ram or 0, 100, 28, unit="%")
    print(f"  {_pct_icon(ram)}  {bar}")
    try:
        import psutil
        vm = psutil.virtual_memory()
        used_gb  = vm.used  / (1024 ** 3)
        total_gb = vm.total / (1024 ** 3)
        avail_gb = vm.available / (1024 ** 3)
        print(
            f"      {colorize('Used     ', T.DIM)}  "
            f"{colorize(f'{used_gb:.1f} GB', T.DIM)} / {total_gb:.1f} GB"
            f"   {colorize('Available', T.DIM)}: {colorize(f'{avail_gb:.1f} GB', T.SUCCESS)}"
        )
    except Exception:
        pass

    # Disk
    disk = data.get("disk", {})
    disk_pct = disk.get("used_percent")
    print()
    print(colorize("  ── DISK ────────────────────────────────────────", T.DIM))
    bar = progress_bar(disk_pct or 0, 100, 28, unit="%")
    print(f"  {_pct_icon(disk_pct)}  {bar}")
    free_bytes = disk.get("free_bytes", 0)
    if free_bytes:
        print(f"      {colorize('Free     ', T.DIM)}  {colorize(_bytes_to_gb(free_bytes), T.SUCCESS)}")

    # Additional disks (psutil)
    try:
        import psutil
        parts = psutil.disk_partitions(all=False)
        for part in parts[:3]:
            try:
                usage = psutil.disk_usage(part.mountpoint)
                bar2  = progress_bar(usage.percent, 100, 20, unit="%")
                mp    = colorize(part.mountpoint[:16].ljust(16), T.DIM)
                print(f"      {mp}  {bar2}")
            except Exception:
                pass
    except Exception:
        pass

    # Network
    print()
    print(colorize("  ── NETWORK ─────────────────────────────────────", T.DIM))
    net = _get_network()
    if net.get("ok"):
        up_color   = T.WARNING if net["up"] > 10   else T.SUCCESS
        down_color = T.WARNING if net["down"] > 10 else T.SUCCESS
        up_val = f"{net['up']:.2f} MB/s"
        down_val = f"{net['down']:.2f} MB/s"
        up_text = colorize(up_val, up_color)
        down_text = colorize(down_val, down_color)
        print(
            f"      {colorize('↑ Upload  ', T.DIM)}  {up_text}"
            f"    {colorize('↓ Download', T.DIM)}  {down_text}"
        )
        
    else:
        print(f"      {colorize('(psutil unavailable)', T.DIM)}")

    # Directory checks
    paths = data.get("paths", {})
    if paths:
        print()
        print(colorize("  ── DIRECTORIES ─────────────────────────────────", T.DIM))
        labels = {
            "data_dir":    "Data dir   ",
            "logs_dir":    "Logs dir   ",
            "reports_dir": "Reports    ",
            "backup_dir":  "Backup dir ",
        }
        parts_row = []
        for key, label in labels.items():
            ok = paths.get(key, False)
            sym = colorize("✔", T.SUCCESS) if ok else colorize("✖", T.ERROR)
            parts_row.append(f"  {sym}  {colorize(label, T.DIM)}")
        print("  " + "  ".join(parts_row))

    # Warnings
    warnings = data.get("warnings", [])
    if warnings:
        print()
        print(colorize("  ── WARNINGS ────────────────────────────────────", T.DIM))
        for w_msg in warnings:
            print(f"  {colorize('⚠', T.WARNING)}  {colorize(w_msg, T.WARNING)}")

    print()
    command_bar(["[R] Refresh", "[A] Auto-refresh toggle", "[0] Back"])


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_health_menu(app: Any) -> None:
    """Display system health.  Called by CLIManager and main.py."""
    auto_refresh = False
    refresh_sec  = 3

    while True:
        try:
            result = app.execute_health_check()
        except Exception as exc:
            print(f"\n  {colorize('✖', T.ERROR)}  Health check error: {exc}")
            input(f"\n  {colorize('Press Enter to continue...', T.DIM)}")
            return

        data = result.get("data", {})
        # Merge network metrics if available
        try:
            import psutil
            net_io = psutil.net_io_counters()
            data["_net_io"] = net_io
        except Exception:
            pass

        _render_health(data, auto_refresh, refresh_sec)

        if auto_refresh:
            # Non-blocking check: if user types something within refresh_sec, handle it
            print(f"\n  {colorize(f'Auto-refreshing in {refresh_sec}s — press key to interact...', T.DIM)}", end="", flush=True)
            # Use a simple sleep + check approach (works cross-platform)
            for _ in range(refresh_sec * 4):
                time.sleep(0.25)
            print()
            choice = ""
        else:
            choice = input(f"  {colorize('>', T.PRIMARY)} ").strip().lower()

        if choice in ("0", "b", "back", "q", "quit", "exit"):
            break
        elif choice in ("r", "refresh", ""):
            continue   # re-render
        elif choice in ("a", "auto"):
            auto_refresh = not auto_refresh
        # any other key → refresh