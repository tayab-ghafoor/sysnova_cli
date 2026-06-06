"""
commands/backup.py — Direct CLI handler for: sysmanager backup

Usage
─────
    sysmanager backup /src/project              # Incremental backup, prompt dest
    sysmanager backup /src --dest /backups      # Explicit destination
    sysmanager backup /src --zip                # Compress before backup
    sysmanager backup /src --zip --cloud gdrive # Zip + upload to Google Drive
    sysmanager backup /src --type full          # Full backup
    sysmanager backup --list                    # List recent backup history
    sysmanager backup --list --json             # History as JSON

Exit codes
──────────
    0   success
    1   partial success (some warnings)
    2   validation error (bad path, no space, etc.)
    3   unexpected error
"""

from __future__ import annotations

import json
import os
import sys
from argparse import Namespace


# ── UI helpers ────────────────────────────────────────────────────────────────

def _try_theme():
    try:
        from system_manager_cli.ulits.theme import T, colorize
        from system_manager_cli.ulits.screen import (
            box_top, box_bottom, box_row, section, term_width, confirm,
        )
        from system_manager_cli.ulits.spinner import Spinner
        return T, colorize, box_top, box_bottom, box_row, section, term_width, confirm, Spinner
    except ImportError:
        class _T:
            RESET = BOLD = DIM = PRIMARY = SUCCESS = WARNING = ERROR = ""
            HEADER = WHITE = ""
        T = _T()
        def colorize(t, *_): return t
        def box_top(w=0, color=""): return "=" * (w or 60)
        def box_bottom(w=0, color=""): return "=" * (w or 60)
        def box_row(t, w=0, padding=2, color=""): return f"  {t}"
        def section(label="", w=0, color=""): return f"── {label} ──"
        def term_width(): return 60
        def confirm(q, detail="", **kw):
            ans = input(f"  {q} (y/n): ").strip().lower()
            return ans in ("y", "yes")

        class Spinner:
            def __init__(self, msg="", **kw):
                self._msg = msg
            def __enter__(self):
                print(f"  ⟳  {self._msg}...")
                return self
            def __exit__(self, *_):
                pass

        return T, colorize, box_top, box_bottom, box_row, section, term_width, confirm, Spinner


def _err(msg: str) -> None:
    print(f"  [ERROR] {msg}", file=sys.stderr)


def _fmt_bytes(n: int | None) -> str:
    if n is None:
        return "n/a"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.0f} PB"


# ── List history ──────────────────────────────────────────────────────────────

def _list_history(app, args: Namespace) -> int:
    (T, colorize, box_top, box_bottom, box_row,
     section, term_width, confirm, Spinner) = _try_theme()

    use_json = getattr(args, "json", False)
    quiet    = getattr(args, "quiet", False)

    try:
        from system_manager_cli.core.backup_orchestrator import load_backup_history
        history = load_backup_history(limit=20)
    except ImportError:
        # Fallback: ask backup_manager
        try:
            backups = app.backup_manager.list_backups()
            history = [{"backup_path": p, "success": True} for p in backups]
        except Exception:
            history = []

    if use_json:
        print(json.dumps(history, indent=2, default=str))
        return 0

    if not history:
        if not quiet:
            print("\n  No backup history found.")
        return 0

    w = min(term_width() - 2, 66)
    if not quiet:
        print()
        print(colorize(box_top(w), T.PRIMARY))
        print(
            colorize("║", T.PRIMARY)
            + f"  {colorize('RECENT BACKUPS', T.BOLD + T.WHITE)}"
            + " " * max(0, w - 18)
            + "  "
            + colorize("║", T.PRIMARY)
        )
        print(colorize(box_bottom(w), T.PRIMARY))

    try:
        from system_manager_cli.ulits.table import Table
        t = Table(
            headers=["#", "Date", "Size", "Type", "Cloud", "Status"],
            col_align=["right", "left", "right", "left", "left", "left"],
        )
        for i, rec in enumerate(history[:15], 1):
            started = str(rec.get("started_at", ""))[:16]
            size    = _fmt_bytes(rec.get("size_bytes"))
            btype   = rec.get("backup_type", "manual")
            cloud   = rec.get("cloud_provider") or "—"
            success = rec.get("success", False)
            status  = colorize("✔ OK", T.SUCCESS) if success else colorize("✖ FAILED", T.ERROR)
            t.add_row([str(i), started, size, btype, cloud, status])
        t.print()
    except Exception:
        for i, rec in enumerate(history[:15], 1):
            started = str(rec.get("started_at", ""))[:16]
            success = rec.get("success", False)
            sym = "✔" if success else "✖"
            print(f"  {i:>2}. {started}  {sym}  {rec.get('backup_type', 'manual')}")

    return 0


# ── Run backup ────────────────────────────────────────────────────────────────

def _run_backup(app, args: Namespace) -> int:
    (T, colorize, box_top, box_bottom, box_row,
     section, term_width, confirm, Spinner) = _try_theme()

    use_json    = getattr(args, "json", False)
    quiet       = getattr(args, "quiet", False)
    verbose     = getattr(args, "verbose", False)
    zip_data    = getattr(args, "zip", False)
    cloud       = getattr(args, "cloud", "") or ""
    backup_type = getattr(args, "backup_type", "incremental") or "incremental"
    sources     = getattr(args, "source", []) or []
    dest        = getattr(args, "dest", "") or ""

    # Must have at least one source
    if not sources:
        _err("No source path(s) provided. Usage: sysmanager backup <path> [--dest <dest>]")
        return 2

    # Validate sources
    invalid = [s for s in sources if not os.path.exists(s)]
    if invalid:
        for p in invalid:
            _err(f"Source path not found: {p}")
        return 2

    # Destination: prompt if not provided
    if not dest:
        try:
            from system_manager_cli.core.config_manager import load_config
            cfg = load_config()
            if cfg.last_destination_path and os.path.exists(cfg.last_destination_path):
                dest = cfg.last_destination_path
                if not quiet and not use_json:
                    print(f"  {colorize('ℹ', T.DIM)}  Using last destination: {colorize(dest, T.PRIMARY)}")
            else:
                dest = input("\n  Backup destination path: ").strip()
        except Exception:
            dest = input("\n  Backup destination path: ").strip()

    if not dest or not os.path.exists(dest):
        _err(f"Destination path does not exist: {dest}")
        return 2

    if not quiet and not use_json:
        w = min(term_width() - 2, 66)
        print()
        print(colorize(box_top(w), T.PRIMARY))
        print(
            colorize("║", T.PRIMARY)
            + f"  {colorize('DATA BACKUP', T.BOLD + T.WHITE)}"
            + " " * max(0, w - 14)
            + "  "
            + colorize("║", T.PRIMARY)
        )
        print(colorize(box_bottom(w), T.PRIMARY))
        print()
        print(f"  {colorize('Sources    :', T.DIM)}  {', '.join(sources)}")
        print(f"  {colorize('Destination:', T.DIM)}  {dest}")
        print(f"  {colorize('Type       :', T.DIM)}  {backup_type}")
        if zip_data:
            print(f"  {colorize('Compression:', T.DIM)}  ZIP")
        if cloud:
            print(f"  {colorize('Cloud      :', T.DIM)}  {cloud}")
        print()

    # Try orchestrator first (new path), fall back to backup_manager (legacy)
    try:
        from system_manager_cli.core.backup_orchestrator import BackupOrchestrator
        orch = BackupOrchestrator()

        # Estimate first
        try:
            estimate = orch.estimate(sources, dest)
            if not quiet and not use_json:
                print(f"  {colorize('ℹ', T.DIM)}  Estimated size: {estimate.size_display()}  "
                      f"({estimate.source_file_count} files)")
                for w_msg in estimate.warnings:
                    print(f"  {colorize('⚠', T.WARNING)}  {w_msg}")
        except Exception:
            pass

        # Map cloud arg
        provider_key = None
        if cloud:
            cloud_map = {
                "gdrive":  "google_drive",
                "gdrive2": "google_drive",
                "onedrive": "onedrive",
                "dropbox":  "dropbox",
                "s3":       "s3",
                "b2":       "backblaze_b2",
                "sftp":     "sftp",
            }
            provider_key = cloud_map.get(cloud.lower(), cloud.lower())

        result = orch.run(
            source_paths=sources,
            destination_path=dest,
            zip_data=zip_data,
            cloud_provider_key=provider_key,
        )

        if use_json:
            print(json.dumps(result.to_dict(), indent=2, default=str))
        else:
            if result.success:
                print(f"  {colorize('✔', T.SUCCESS)}  Backup completed successfully!")
                print(f"  {colorize('Files    :', T.DIM)}  {result.file_count}")
                print(f"  {colorize('Size     :', T.DIM)}  {_fmt_bytes(result.size_bytes)}")
                if result.cloud_uploaded:
                    print(f"  {colorize('Cloud    :', T.DIM)}  ✔ {result.cloud_provider}")
                print(f"  {colorize('Dest     :', T.DIM)}  {result.destination_path}")
            else:
                _err(result.error_message or "Backup failed.")
                return 1

        return 0 if result.success else 1

    except ImportError:
        # Legacy fallback: use app.execute_backup
        pass
    except Exception as exc:
        _err(f"Orchestrator error: {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 3

    # Legacy path via app.execute_backup (single source only)
    src = sources[0]
    try:
        if not quiet and not use_json:
            with Spinner(f"Creating {backup_type} backup"):
                result = app.execute_backup(src, backup_type)
        else:
            result = app.execute_backup(src, backup_type)
    except Exception as exc:
        _err(f"Backup error: {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 3

    if result.get("status") != "success":
        _err(result.get("error", "Backup failed."))
        return 1

    data = result.get("data", {})

    if use_json:
        print(json.dumps(data, indent=2, default=str))
    elif not quiet:
        print(f"  {colorize('✔', T.SUCCESS)}  Backup completed!")
        print(f"  {colorize('Files    :', T.DIM)}  {data.get('file_count', '?')}")
        print(f"  {colorize('Size     :', T.DIM)}  {_fmt_bytes(data.get('size_bytes'))}")
        print(f"  {colorize('Location :', T.DIM)}  {data.get('backup_path', '?')}")

    return 0


# ── Public entry point ─────────────────────────────────────────────────────────

def run(app, args: Namespace) -> int:
    """
    Execute the backup command.

    Args:
        app:  SystemManagerApp instance.
        args: Parsed argparse Namespace.

    Returns:
        Integer exit code.
    """
    try:
        if getattr(args, "list", False):
            return _list_history(app, args)
        return _run_backup(app, args)
    except KeyboardInterrupt:
        print("\n  Cancelled by user.")
        return 0
    except Exception as exc:
        _err(f"Unexpected error in backup command: {exc}")
        if getattr(args, "verbose", False):
            import traceback
            traceback.print_exc()
        return 3
