"""
commands/backup.py — Direct CLI handler for: sysmanager backup

Usage
─────
    sysmanager backup /src/project              Incremental backup (prompts dest)
    sysmanager backup /src --dest /backups      Explicit destination
    sysmanager backup /src --zip                Compress before backup
    sysmanager backup /src --zip --cloud gdrive Zip + upload to Google Drive
    sysmanager backup /src --type full          Full backup
    sysmanager backup /src --yes                Skip confirmation prompt
    sysmanager backup --list                    List recent backup history
    sysmanager backup --list --json             History as JSON

Supported cloud providers
─────────────────────────
    gdrive    Google Drive (via built-in client)
    gdrive2   Google Drive (legacy alias)
    onedrive  Microsoft OneDrive
    dropbox   Dropbox
    s3        Amazon S3
    b2        Backblaze B2
    sftp      SFTP server
    rclone    Any rclone-configured remote

Exit codes
──────────
    0   success
    1   partial success (some warnings / non-fatal errors)
    2   validation error (bad path, no disk space, etc.)
    3   unexpected exception
"""

from __future__ import annotations

import json
import os
import sys
from argparse import Namespace


# ── Supported cloud provider map ──────────────────────────────────────────────

_CLOUD_MAP: dict[str, str] = {
    "gdrive":   "google_drive",
    "gdrive2":  "google_drive",
    "onedrive": "onedrive",
    "dropbox":  "dropbox",
    "s3":       "s3",
    "b2":       "backblaze_b2",
    "sftp":     "sftp",
    "rclone":   "rclone",
}

_CLOUD_NAMES: str = ", ".join(_CLOUD_MAP)


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


def _fmt_bytes(n: int | float | None) -> str:
    if n is None:
        return "n/a"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.0f} PB"


# ── Validate cloud provider arg ───────────────────────────────────────────────

def _resolve_cloud_key(cloud_arg: str) -> tuple[str | None, str | None]:
    """
    Translate a user-supplied --cloud value to an orchestrator provider key.

    Returns:
        (provider_key, None)            on success
        (None, error_message)           when the provider is unrecognised
    """
    if not cloud_arg:
        return None, None
    key = cloud_arg.strip().lower()
    mapped = _CLOUD_MAP.get(key, key)   # pass-through for unlisted providers
    return mapped, None


# ── List history ──────────────────────────────────────────────────────────────

def _list_history(app, args: Namespace) -> int:
    (T, colorize, box_top, box_bottom, box_row,
     section, term_width, confirm, Spinner) = _try_theme()

    use_json = getattr(args, "json",  False)
    quiet    = getattr(args, "quiet", False)

    history: list[dict] = []
    try:
        from system_manager_cli.core.backup_orchestrator import load_backup_history
        history = load_backup_history(limit=20)
    except ImportError:
        try:
            backups = app.backup_manager.list_backups()
            history = [{"backup_path": p, "success": True} for p in (backups or [])]
        except Exception:
            history = []
    except Exception as exc:
        _err(f"Could not load backup history: {exc}")

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

    use_json    = getattr(args, "json",        False)
    quiet       = getattr(args, "quiet",       False)
    verbose     = getattr(args, "verbose",     False)
    auto_yes    = getattr(args, "yes",         False)
    zip_data    = getattr(args, "zip",         False)
    cloud_arg   = getattr(args, "cloud",       "") or ""
    backup_type = getattr(args, "backup_type", "incremental") or "incremental"
    sources     = getattr(args, "source",      []) or []
    dest        = getattr(args, "dest",        "") or ""

    # ── Validate source path(s) ───────────────────────────────────────────────
    if not sources:
        _err("No source path(s) provided.")
        _err("Usage:  sysmanager backup <path> [--dest <dest>] [options]")
        return 2

    missing = [s for s in sources if not os.path.exists(s)]
    if missing:
        for p in missing:
            _err(f"Source path not found: {p}")
        return 2

    # ── Validate cloud provider ───────────────────────────────────────────────
    provider_key, cloud_err = _resolve_cloud_key(cloud_arg)
    if cloud_err:
        _err(cloud_err)
        _err(f"Supported providers: {_CLOUD_NAMES}")
        return 2

    # ── Resolve destination ───────────────────────────────────────────────────
    if not dest:
        try:
            from system_manager_cli.core.config_manager import load_config
            cfg = load_config()
            last = getattr(cfg, "last_destination_path", "") or ""
            if last and os.path.exists(last):
                dest = last
                if not quiet and not use_json:
                    print(
                        f"  {colorize('ℹ', T.DIM)}  "
                        f"Using last destination: {colorize(dest, T.PRIMARY)}"
                    )
        except Exception:
            pass

    if not dest:
        if use_json or quiet:
            _err("No destination provided. Use --dest <path>.")
            return 2
        dest = input("\n  Backup destination path: ").strip()

    dest = os.path.expanduser(dest.strip())
    if not dest:
        _err("No destination path specified.")
        return 2
    if not os.path.exists(dest):
        _err(f"Destination path does not exist: {dest}")
        return 2

    # ── Print operation summary ───────────────────────────────────────────────
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
        src_display = ", ".join(sources)
        print(f"  {colorize('Source(s)  :', T.DIM)}  {src_display}")
        print(f"  {colorize('Destination:', T.DIM)}  {dest}")
        print(f"  {colorize('Type       :', T.DIM)}  {backup_type}")
        if zip_data:
            print(f"  {colorize('Compression:', T.DIM)}  ZIP")
        if cloud_arg:
            print(f"  {colorize('Cloud      :', T.DIM)}  {cloud_arg}")
        print()

        # Confirm unless --yes
        if not auto_yes:
            try:
                ans = input(
                    f"  {colorize('Proceed with backup?', T.BOLD)} (y/N): "
                ).strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n  Cancelled.")
                return 0
            if ans not in ("y", "yes"):
                print("  Cancelled.")
                return 0

    # ── Try orchestrator path (preferred) ─────────────────────────────────────
    try:
        from system_manager_cli.core.backup_orchestrator import BackupOrchestrator
        orch = BackupOrchestrator()

        # Estimate size / warnings before committing.
        try:
            estimate = orch.estimate(sources, dest)
            if not quiet and not use_json:
                print(
                    f"  {colorize('ℹ', T.DIM)}  "
                    f"Estimated size: {estimate.size_display()}  "
                    f"({estimate.source_file_count} files)"
                )
                for w_msg in estimate.warnings:
                    print(f"  {colorize('⚠', T.WARNING)}  {w_msg}")
        except Exception:
            pass

        if not quiet and not use_json:
            print()

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
        pass   # Fall back to legacy path below.
    except Exception as exc:
        _err(f"Orchestrator error: {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 3

    # ── Legacy path via app.execute_backup (single source only) ───────────────
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