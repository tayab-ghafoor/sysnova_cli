"""
commands/organize.py — Direct CLI handler for: sysmanager organize

Usage
─────
    sysmanager organize /Downloads              Categorize + handle temp files
    sysmanager organize /Downloads --dry-run    Preview what would move (no changes)
    sysmanager organize /Downloads --delete-temp  Permanently delete temp files
    sysmanager organize /Downloads --json       Machine-readable result
    sysmanager organize /Downloads --verbose    Include skipped-file detail

Exit codes
──────────
    0   success, all files processed
    1   partial success (some files skipped)
    2   path error (not found / not a directory)
    3   unexpected error
"""

from __future__ import annotations

import json
import os
import sys
from argparse import Namespace
from pathlib import Path
from typing import Any


# ── UI helpers ────────────────────────────────────────────────────────────────

def _try_theme():
    try:
        from system_manager_cli.ulits.theme import T, colorize
        from system_manager_cli.ulits.screen import (
            box_top, box_bottom, box_row, section, term_width,
            command_bar, progress_bar,
        )
        from system_manager_cli.ulits.spinner import Spinner
        return T, colorize, box_top, box_bottom, box_row, section, term_width, command_bar, progress_bar, Spinner
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
        def command_bar(hints=None): print("─" * 60)
        def progress_bar(v, mx=100, w=20, label="", unit="%", **kw):
            pct = int(v / mx * 100) if mx else 0
            return f"{label} {pct}{unit}"

        class Spinner:
            def __init__(self, msg="", **kw):
                self._msg = msg
            def __enter__(self):
                print(f"  ⟳  {self._msg}...")
                return self
            def __exit__(self, *_):
                pass

        return T, colorize, box_top, box_bottom, box_row, section, term_width, command_bar, progress_bar, Spinner


def _err(msg: str) -> None:
    print(f"  [ERROR] {msg}", file=sys.stderr)


# ── Category icons ────────────────────────────────────────────────────────────

_CAT_ICONS: dict[str, str] = {
    "Documents":     "📄",
    "Images":        "🖼 ",
    "Videos":        "🎬",
    "Audio":         "🎵",
    "Archives":      "📦",
    "Code":          "💻",
    "Executables":   "⚙ ",
    "Fonts":         "🔤",
    "Data":          "📊",
    "Uncategorized": "📁",
    "_TempFiles":    "🗑 ",
}


# ── Dry-run: scan without moving ──────────────────────────────────────────────

def _dry_run_scan(folder: Path) -> dict[str, Any]:
    """
    Walk the folder (top-level only) and predict categorisation without
    making any changes.  Returns the same shape as FileCategorizer.organize().
    """
    try:
        from system_manager_cli.core.File_categorizer import (
            CATEGORIES, TEMP_EXTENSIONS, TEMP_NAME_PATTERNS, _OWN_FOLDERS,
        )
    except ImportError:
        return {
            "status": "error",
            "error": (
                "FileCategorizer module not importable — "
                "cannot run dry-run without it."
            ),
        }

    counts:  dict[str, int] = {}
    temp_count = 0
    skipped:   list[str]   = []

    try:
        items = sorted(folder.iterdir())
    except PermissionError as exc:
        return {"status": "error", "error": f"Permission denied: {exc}"}

    for item in items:
        if item.name.startswith("."):
            continue
        if item.name in _OWN_FOLDERS:
            continue
        if item.is_dir() or not item.is_file():
            continue

        suffix = item.suffix.lower()
        is_temp = suffix in TEMP_EXTENSIONS or any(
            p.search(item.name) for p in TEMP_NAME_PATTERNS
        )
        if is_temp:
            temp_count += 1
            continue

        category = "Uncategorized"
        for cat, exts in CATEGORIES.items():
            if suffix in exts:
                category = cat
                break
        counts[category] = counts.get(category, 0) + 1

    return {
        "status":             "preview",
        "folder":             str(folder),
        "category_counts":    counts,
        "temp_files_handled": temp_count,
        "temp_action":        "would be handled",
        "skipped":            skipped,
    }


# ── Human display ─────────────────────────────────────────────────────────────

def _render_human(
    data:       dict[str, Any],
    args:       Namespace,
    is_dry_run: bool = False,
) -> None:
    (T, colorize, box_top, box_bottom, box_row,
     section, term_width, command_bar, progress_bar, Spinner) = _try_theme()

    quiet   = getattr(args, "quiet",   False)
    verbose = getattr(args, "verbose", False)
    w       = min(term_width() - 2, 66)

    counts   = data.get("category_counts", {})
    temp_cnt = data.get("temp_files_handled", 0)
    temp_act = data.get("temp_action", "handled")
    skipped  = data.get("skipped", [])
    folder   = data.get("folder", "?")
    total    = sum(counts.values())

    if not quiet:
        label = (
            "FILE ORGANIZER  (DRY RUN — no changes made)"
            if is_dry_run
            else "FILE ORGANIZER"
        )
        print()
        print(colorize(box_top(w), T.PRIMARY))
        print(
            colorize("║", T.PRIMARY)
            + f"  {colorize(label, T.BOLD + T.WHITE)}"
            + " " * max(0, w - len(label) - 2)
            + "  "
            + colorize("║", T.PRIMARY)
        )
        print(colorize(box_bottom(w), T.PRIMARY))

    # ── Summary stats ─────────────────────────────────────────────────────────
    print()
    print(colorize("  ── Summary ─────────────────────────────────────────", T.DIM))
    print(f"  {colorize('Folder       :', T.DIM)}  {colorize(folder, T.WHITE)}")

    moved_label = "Would move" if is_dry_run else "Files moved"
    total_color = T.SUCCESS if total > 0 else T.DIM
    print(f"  {colorize(moved_label + ' :', T.DIM)}  {colorize(str(total), total_color + T.BOLD)}")

    temp_color = T.WARNING if temp_cnt > 0 else T.DIM
    print(f"  {colorize('Temp files   :', T.DIM)}  {colorize(str(temp_cnt), temp_color)}  ({temp_act})")

    skip_color = T.ERROR if skipped else T.DIM
    print(f"  {colorize('Skipped      :', T.DIM)}  {colorize(str(len(skipped)), skip_color)}")

    if is_dry_run:
        print(f"\n  {colorize('ℹ  DRY RUN: no files were moved or deleted.', T.WARNING)}")

    # ── Category breakdown ────────────────────────────────────────────────────
    if counts:
        print()
        print(colorize("  ── Category Breakdown ───────────────────────────────", T.DIM))
        max_count = max(counts.values()) if counts else 1

        try:
            from system_manager_cli.ulits.table import Table
            t = Table(
                headers=["Category", "Files"],
                col_align=["left", "right"],
                max_width=w,
            )
            for cat, cnt in sorted(counts.items(), key=lambda x: -x[1]):
                icon = _CAT_ICONS.get(cat, "📁")
                t.add_row([f"{icon}  {cat}", str(cnt)])
            t.print()
        except Exception:
            bar_w = 24
            for cat, cnt in sorted(counts.items(), key=lambda x: -x[1]):
                icon   = _CAT_ICONS.get(cat, "📁")
                filled = int((cnt / max_count) * bar_w)
                bar    = "█" * filled + "░" * (bar_w - filled)
                print(
                    f"  {icon}  {cat:<18} "
                    f"{colorize(bar, T.PRIMARY)}  "
                    f"{colorize(str(cnt), T.BOLD)}"
                )

    # ── Temp files note ───────────────────────────────────────────────────────
    if temp_cnt > 0:
        print()
        action_text = colorize(temp_act, T.WARNING if "delet" in temp_act else T.DIM)
        print(f"  🗑   {colorize(str(temp_cnt), T.BOLD)} temp file(s) {action_text}")

    # ── Skipped files (verbose shows all, non-verbose shows first 10) ─────────
    if skipped:
        print()
        print(colorize("  ── Skipped Files ────────────────────────────────────", T.DIM))
        display_limit = len(skipped) if verbose else 10
        for s in skipped[:display_limit]:
            print(f"  {colorize('⚠', T.WARNING)}  {s}")
        if len(skipped) > display_limit:
            print(
                f"  {colorize(f'  … and {len(skipped) - display_limit} more. Use --verbose to see all.', T.DIM)}"
            )

    print()


def _render_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, indent=2, default=str))


# ── Public entry point ─────────────────────────────────────────────────────────

def run(app, args: Namespace) -> int:
    """
    Execute the organize command.

    Args:
        app:  SystemManagerApp instance.
        args: Parsed argparse Namespace.

    Returns:
        Integer exit code.
    """
    (T, colorize, box_top, box_bottom, box_row,
     section, term_width, command_bar, progress_bar, Spinner) = _try_theme()

    use_json    = getattr(args, "json",        False)
    quiet       = getattr(args, "quiet",       False)
    verbose     = getattr(args, "verbose",     False)
    dry_run     = getattr(args, "dry_run",     False)
    delete_temp = getattr(args, "delete_temp", False)
    path_str    = getattr(args, "path",        "") or ""

    # ── Resolve path ──────────────────────────────────────────────────────────
    path_str = os.path.expanduser(path_str.strip()) if path_str else os.getcwd()
    folder   = Path(path_str)

    if not folder.exists():
        _err(f"Path does not exist: {path_str}")
        if not use_json:
            try:
                from system_manager_cli.ulits.screen import error_panel
                error_panel(
                    "PATH NOT FOUND",
                    f"The folder could not be found: {path_str}",
                    hints=[
                        "Check for typos in the path",
                        "Use an absolute path (e.g. /home/user/Downloads)",
                        "Run 'ls' to verify the path exists",
                    ],
                )
            except ImportError:
                pass
        return 2

    if not folder.is_dir():
        _err(f"Path is not a directory: {path_str}")
        return 2

    # ── Dry run ───────────────────────────────────────────────────────────────
    if dry_run:
        if not quiet and not use_json:
            print(
                f"\n  {colorize('➤', T.PRIMARY)}  "
                f"Scanning (dry run): {colorize(path_str, T.WHITE)}"
            )

        data = _dry_run_scan(folder)

        if data.get("status") == "error":
            _err(data.get("error", "Dry-run scan failed."))
            return 3

        if use_json:
            _render_json(data)
        else:
            _render_human(data, args, is_dry_run=True)

        return 0

    # ── Apply delete-temp setting if --delete-temp flag was passed ────────────
    original_delete_pref: bool | None = None
    if delete_temp:
        try:
            original_delete_pref = app.settings_manager.get(
                "file_organizer.delete_temp_permanently", False
            )
            app.settings_manager.set("file_organizer.delete_temp_permanently", True)
        except Exception:
            pass

    # ── Real run ──────────────────────────────────────────────────────────────
    if not quiet and not use_json:
        print(
            f"\n  {colorize('➤', T.PRIMARY)}  Organizing: {colorize(path_str, T.WHITE)}"
        )

    try:
        if not use_json and not quiet:
            with Spinner("Categorizing files"):
                result = app.execute_categorize_files(path_str)
        else:
            result = app.execute_categorize_files(path_str)
    except Exception as exc:
        _err(f"Organize error: {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 3
    finally:
        # Restore original delete-temp preference.
        if original_delete_pref is not None:
            try:
                app.settings_manager.set(
                    "file_organizer.delete_temp_permanently", original_delete_pref
                )
            except Exception:
                pass

    if result.get("status") not in ("success",):
        msg = result.get("error") or result.get("display", "Unknown error")
        _err(f"Organize failed: {msg}")
        return 3

    if use_json:
        _render_json(result)
    else:
        _render_human(result, args, is_dry_run=False)

    skipped = result.get("skipped", [])
    return 1 if skipped else 0