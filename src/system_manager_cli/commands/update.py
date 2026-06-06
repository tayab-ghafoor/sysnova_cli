"""
CLI handler for: sysmanager update

Commands
--------
  sysmanager update --check      Check if a newer version is available.
  sysmanager update --install    Download and stage the latest update
                                 (prompts for confirmation unless -y).
  sysmanager update --status     Show current version, pending updates, etc.
  sysmanager update --force      Force re-download even when already up to date.

Global flags
------------
  --json        Machine-readable JSON output.
  -y / --yes    Skip confirmation prompt.
  -v / --verbose  Verbose logging.
"""

from __future__ import annotations

import json
import sys
import traceback
from argparse import Namespace
from typing import Any


# ---------------------------------------------------------------------------
# Private output helpers
# ---------------------------------------------------------------------------

def _err(msg: str) -> None:
    print(f"  [ERROR] {msg}", file=sys.stderr)


def _info(msg: str) -> None:
    print(f"  [INFO] {msg}")


def _ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def _render_json(data: Any) -> None:
    print(json.dumps(data, indent=2, default=str))


# ---------------------------------------------------------------------------
# Render helpers
# ---------------------------------------------------------------------------

def _render_status(data: dict) -> None:
    print()
    print("  ── Update Status ─────────────────────────────")
    print(f"  Current version  :  {data.get('current_version', 'unknown')}")
    print(f"  Update in progress: {data.get('update_in_progress', False)}")
    print(f"  Startup marked OK : {data.get('startup_success', False)}")
    print(f"  Pending update    : {data.get('pending_update', False)}")
    print(f"  Auto-update ON    : {data.get('auto_update_enabled', False)}")
    print(f"  Update URL        : {data.get('update_url', '')}")
    print(f"  Last check        : {data.get('last_check', 'Never')}")
    print()


def _render_check(data: dict) -> None:
    remote = data.get("remote") or {}
    print()
    if data.get("update_available"):
        _ok(
            f"Update available: {data.get('current_version')} → {remote.get('version')}"
        )
        if remote.get("download_url"):
            print(f"  Download URL : {remote['download_url']}")
        if remote.get("changelog_url"):
            print(f"  Changelog    : {remote['changelog_url']}")
        print("  Run: sysmanager update --install")
    else:
        _ok(f"Already up to date. Current version: {data.get('current_version')}")
        if remote.get("version"):
            print(f"  Latest remote version: {remote['version']}")
    print()


def _render_install(data: dict) -> None:
    for msg in data.get("messages", []):
        print(f"  {msg}")

    if data.get("updated"):
        _ok(f"Staged successfully. Version {data.get('current_version')} will be active after restart.")
        print("  Restarting now to apply the update …")
    else:
        _err("Staging failed. See .updater/logs/update.log for details.")
    print()


# ---------------------------------------------------------------------------
# Confirmation prompt
# ---------------------------------------------------------------------------

def _confirm(current: str, remote: str, auto_yes: bool, force: bool) -> bool:
    if auto_yes or force:
        return True
    print()
    print(f"  Update available: {current} → {remote}")
    try:
        answer = input("  Download and install? (y/N): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer in ("y", "yes")


# ---------------------------------------------------------------------------
# Progress callback
# ---------------------------------------------------------------------------

def _progress(msg: str) -> None:
    print(f"  {msg}")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run(app, args: Namespace) -> int:
    """
    Execute the ``update`` sub-command.

    Args:
        app:  A ``SystemManagerApp`` instance.
        args: Parsed ``argparse.Namespace`` from the CLI parser.

    Returns:
        POSIX exit code (0 = success, 1 = error, 3 = exception, 130 = Ctrl-C).
    """
    try:
        use_json = getattr(args, "json", False)
        verbose  = getattr(args, "verbose", False)
        auto_yes = getattr(args, "yes", False)
        force    = getattr(args, "force", False)

        # ── status ────────────────────────────────────────────────────
        if getattr(args, "status", False):
            result = app.execute_update_status()
            if use_json:
                _render_json(result)
            else:
                _render_status(result.get("data", {}))
            return 0 if result.get("status") == "success" else 1

        # ── install ───────────────────────────────────────────────────
        if getattr(args, "install", False) or force:
            # 1. Check first so we can show version numbers in the prompt
            check_result = app.execute_update_check()
            if check_result.get("status") != "success":
                _err("Could not reach the update server.")
                if use_json:
                    _render_json(check_result)
                return 1

            check_data       = check_result.get("data", {})
            current_version  = check_data.get("current_version", "unknown")
            remote_version   = (check_data.get("remote") or {}).get("version", "unknown")
            update_available = check_data.get("update_available", False)

            if not update_available and not force:
                _info("No update available – nothing to install.")
                if use_json:
                    _render_json(check_result)
                return 0

            if not _confirm(current_version, remote_version, auto_yes, force):
                _info("Update cancelled.")
                return 0

            # 2. Download + stage
            messages: list[str] = []

            def _tracked_progress(msg: str) -> None:
                messages.append(msg)
                _progress(msg)

            try:
                result = app.execute_update_install(
                    progress_callback=_tracked_progress
                )
            except TypeError:
                # Older app.py that doesn't accept progress_callback
                if verbose:
                    _info("Progress callback not supported – running silently.")
                result = app.execute_update_install()

            if use_json:
                _render_json(result)
            else:
                _render_install(result.get("data", {}))

            success = result.get("status") == "success"

            # 3. Restart to apply the update
            if success:
                if hasattr(app, "updater") and hasattr(app.updater, "restart_application"):
                    app.updater.restart_application()
                # restart_application() replaces the process; if we reach here
                # it means the restart itself failed – still report success.

            return 0 if success else 1

        # ── check (default) ───────────────────────────────────────────
        result = app.execute_update_check()
        if use_json:
            _render_json(result)
        else:
            _render_check(result.get("data", {}))
        return 0 if result.get("status") == "success" else 1

    except KeyboardInterrupt:
        print()
        _info("Interrupted.")
        return 130

    except Exception as exc:
        _err(f"Update command failed: {exc}")
        if getattr(args, "verbose", False):
            traceback.print_exc()
        return 3