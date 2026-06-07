"""
commands/update.py — Direct CLI handler for: sysmanager update

Usage
─────
    sysmanager update               Check for a newer release (default)
    sysmanager update --check       Explicit check (same as no flag)
    sysmanager update --install     Download and install the latest release
    sysmanager update --install -y  Install without confirmation prompt
    sysmanager update --install --force   Re-download even if already up to date
    sysmanager update --status      Show local updater state

Global flags
────────────
    --json         Machine-readable JSON output
    -v / --verbose Verbose logging
    -q / --quiet   Suppress non-essential output

Exit codes
──────────
    0   success
    1   update check or install failed
    3   unexpected exception
  130   interrupted (Ctrl+C)
"""

from __future__ import annotations

import json
import sys
import traceback
from argparse import Namespace
from typing import Any


# ── Private output helpers ─────────────────────────────────────────────────────

def _err(msg: str) -> None:
    print(f"  [ERROR] {msg}", file=sys.stderr)


def _info(msg: str) -> None:
    print(f"  [INFO] {msg}")


def _ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def _render_json(data: Any) -> None:
    print(json.dumps(data, indent=2, default=str))


# ── Render helpers ─────────────────────────────────────────────────────────────

def _render_status(data: dict) -> None:
    print()
    print("  ── Update Status ─────────────────────────────────")
    print(f"  Current version   :  {data.get('current_version', 'unknown')}")
    print(f"  Update in progress:  {data.get('update_in_progress', False)}")
    print(f"  Startup marked OK :  {data.get('startup_success', False)}")
    print(f"  Pending update    :  {data.get('pending_update', False)}")
    print(f"  Auto-update ON    :  {data.get('auto_update_enabled', False)}")
    print(f"  Update URL        :  {data.get('update_url', '—')}")
    print(f"  Last check        :  {data.get('last_check', 'Never')}")
    print()


def _render_check(data: dict) -> None:
    remote = data.get("remote") or {}
    print()
    if data.get("update_available"):
        _ok(
            f"Update available: "
            f"{data.get('current_version')} → {remote.get('version')}"
        )
        if remote.get("download_url"):
            print(f"  Download URL  :  {remote['download_url']}")
        if remote.get("changelog_url"):
            print(f"  Changelog     :  {remote['changelog_url']}")
        print("  Run:  sysmanager update --install")
    else:
        _ok(f"Already up to date. Current version: {data.get('current_version', 'unknown')}")
        if remote.get("version"):
            print(f"  Latest remote :  {remote['version']}")
    print()


def _render_install(data: dict) -> None:
    for msg in data.get("messages", []):
        print(f"  {msg}")

    if data.get("updated"):
        _ok(
            f"Staged successfully. "
            f"Version {data.get('current_version')} will be active after restart."
        )
        print("  Restarting now to apply the update …")
    else:
        _err("Staging failed. See .updater/logs/update.log for details.")
    print()


# ── Confirmation prompt ────────────────────────────────────────────────────────

def _confirm_install(
    current: str,
    remote:  str,
    auto_yes: bool,
    force:    bool,
) -> bool:
    """
    Return True if the user (or flags) authorises the install.

    --yes or --force both skip the interactive prompt.
    """
    if auto_yes or force:
        return True
    print()
    print(f"  Update available:  {current}  →  {remote}")
    try:
        answer = input("  Download and install? (y/N): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer in ("y", "yes")


# ── Progress callback ──────────────────────────────────────────────────────────

def _progress(msg: str) -> None:
    print(f"  {msg}")


# ── Public entry point ─────────────────────────────────────────────────────────

def run(app, args: Namespace) -> int:
    """
    Execute the ``update`` sub-command.

    Args:
        app:  SystemManagerApp instance.
        args: Parsed argparse.Namespace from cli_parser.build_parser().

    Returns:
        POSIX exit code (0 = success, 1 = error, 3 = exception, 130 = Ctrl-C).
    """
    try:
        use_json = getattr(args, "json",          False)
        verbose  = getattr(args, "verbose",       False)
        auto_yes = getattr(args, "yes",           False)
        force    = getattr(args, "force",         False)
        # --status uses dest="update_status" to avoid clashing with the built-in
        # 'status' command; fall back to plain "status" for any older parser.
        want_status = (
            getattr(args, "update_status", False)
            or getattr(args, "status", False)
        )
        want_install = getattr(args, "install", False)

        # ── --status ─────────────────────────────────────────────────────────
        if want_status:
            result = app.execute_update_status()
            if use_json:
                _render_json(result)
            else:
                _render_status(result.get("data", {}))
            return 0 if result.get("status") == "success" else 1

        # ── --install (or --force without --check) ────────────────────────────
        if want_install or force:
            # 1. Check first so we have version numbers for the prompt.
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
                _info("No update available — nothing to install.")
                if use_json:
                    _render_json(check_result)
                return 0

            if not _confirm_install(current_version, remote_version, auto_yes, force):
                _info("Update cancelled.")
                return 0

            # 2. Download + stage.
            messages: list[str] = []

            def _tracked_progress(msg: str) -> None:
                messages.append(msg)
                _progress(msg)

            try:
                result = app.execute_update_install(
                    progress_callback=_tracked_progress
                )
            except TypeError:
                # Older app.py that doesn't accept progress_callback.
                if verbose:
                    _info("Progress callback not supported by this app version.")
                result = app.execute_update_install()

            if use_json:
                _render_json(result)
            else:
                _render_install(result.get("data", {}))

            success = result.get("status") == "success"

            # 3. Restart to apply the update (replaces the current process).
            if success:
                if hasattr(app, "updater") and hasattr(app.updater, "restart_application"):
                    app.updater.restart_application()
                # If restart_application() returns, it means the restart failed;
                # we still report success because staging was complete.

            return 0 if success else 1

        # ── --check (default behaviour) ───────────────────────────────────────
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