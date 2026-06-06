"""
backup_menu.py — CLI interaction layer for the Data Backup System (Option 4).

Handles all user prompts, validates input step-by-step, then delegates
the actual work to run_backup_flow() in backup_service.py.

Change vs original:
    - Removed _ask_delete_local() from the input-collection section.
      The question is now asked inside backup_service.run_backup_flow()
      AFTER a successful cloud upload, so there is no risk of asking
      "delete local?" before the upload has even happened.
    - Removed delete_local_after parameter from the run_backup_flow() call
      (the parameter no longer exists in backup_service.py).
"""

from __future__ import annotations
from typing import Any, Optional

from ..core.Validator import validate_paths, validate_single_path
from ..core.config_manager import load_config, update_destination, add_rclone_remote
from ..core.backup_service import run_backup_flow
from ..ulits.progress import (
    print_step, print_success, print_error, print_info, print_warning,
)
from ..ulits.logger import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _divider() -> None:
    print("=" * 62)


def _header() -> None:
    _divider()
    print("           DATA BACKUP SYSTEM")
    _divider()


def _prompt(message: str) -> str:
    return input(f"\n  {message} ").strip()


def _yes_no(question: str) -> bool:
    while True:
        ans = _prompt(f"{question} (y/n):").lower()
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print_error("Please enter 'y' or 'n'.")


# ─────────────────────────────────────────────
# Step 1 — Source paths
# ─────────────────────────────────────────────

def _collect_source_paths() -> list[str]:
    """Prompt until all provided paths are valid. Returns list of valid path strings."""
    print_step("INPUT SOURCE PATH")
    print("  Enter one file/folder path, or multiple paths separated by commas.")
    print("  Example:  D:\\project\\data   OR   D:\\file1.txt, D:\\file2.txt\n")

    while True:
        raw = _prompt("Enter path(s):")
        if not raw:
            print_error("Input cannot be empty. Please enter at least one path.")
            continue

        results, all_valid = validate_paths(raw)

        for r in results:
            if r.exists:
                print_success(f"Path verified: {r.path}")
            else:
                print_error(f"Path does not exist: {r.path}")

        if all_valid:
            return [r.path for r in results]

        invalid = [r.path for r in results if not r.exists]
        print_warning(f"\n  Invalid path(s): {', '.join(invalid)}")
        print("  Please re-enter all path(s) with correct values.")


# ─────────────────────────────────────────────
# Step 2 — Destination path
# ─────────────────────────────────────────────

def _collect_destination_path(config) -> str:
    """
    Prompt for destination path.
    First run: required.
    Subsequent runs: press Enter to reuse saved path.
    """
    print_step("INPUT BACKUP DESTINATION PATH")

    first_run = not config.last_destination_path

    if first_run:
        prompt_text = "Enter Backup Destination Path:"
    else:
        print_info(f"Previously used: {config.last_destination_path}")
        prompt_text = "Enter Backup Destination Path (press Enter to reuse):"

    while True:
        raw = _prompt(prompt_text)

        if not raw and not first_run:
            destination = config.last_destination_path
            print_info(f"Using saved destination: {destination}")
        elif raw:
            destination = raw
        else:
            print_error("Destination path is required on first use.")
            continue

        result = validate_single_path(destination)
        if result.exists:
            print_success(f"Destination path verified: {destination}")
            update_destination(config, destination)
            return destination

        print_error(f"Path does not exist: {destination}")
        print("  Please enter a valid destination path.")


# ─────────────────────────────────────────────
# Step 3 — Zip
# ─────────────────────────────────────────────

def _ask_zip() -> bool:
    print_step("ZIP BACKUP DATA")
    return _yes_no("Do you want to zip the backup data?")


# ─────────────────────────────────────────────
# Step 4 — Cloud backup
# ─────────────────────────────────────────────

def _ask_cloud_backup() -> bool:
    print_step("BACKUP DATA TO CLOUD STORAGE")
    return _yes_no("Do you want to upload the backup to cloud storage?")


# ─────────────────────────────────────────────
# Step 5 — Cloud method
# ─────────────────────────────────────────────

def _select_cloud_method(config):
    """
    Ask user to select Google Drive API or Rclone.
    Returns (method, remote_name, storage_name).
    """
    print_step("SELECT METHOD FOR CLOUD BACKUP")
    print("  1. Google Drive API")
    print("  2. Rclone")

    while True:
        choice = _prompt("Select method (1 or 2):")
        if choice == "1":
            return "gdrive", None, None
        if choice == "2":
            return _collect_rclone_remote(config)
        print_error("Please enter 1 or 2.")


def _collect_rclone_remote(config):
    """Prompt for rclone remote name, verify against saved remotes."""
    print_step("RCLONE REMOTE SELECTION")

    if config.rclone_remotes:
        print("  Configured remotes:")
        print(config.list_remotes_display())
    else:
        print_warning(
            "No remotes configured yet.\n"
            "  Run 'rclone config' in your terminal first, then enter the remote name below."
        )

    while True:
        raw = _prompt("Enter remote/storage name:")
        if not raw:
            print_error("Remote name cannot be empty.")
            continue

        matched = config.find_remote(raw)
        if matched:
            print_success(f"Remote verified: {matched.remote_name} ({matched.storage_name})")
            return "rclone", matched.remote_name, matched.storage_name

        print_error(f"'{raw}' is not in saved remotes.")
        if config.rclone_remotes:
            print("  Saved remotes:")
            print(config.list_remotes_display())

        register = _yes_no("  Would you like to register this as a new remote?")
        if register:
            storage_name = _prompt("Enter a display name (e.g. 'Google Drive'):")
            add_rclone_remote(config, storage_name=storage_name, remote_name=raw)
            print_success(f"Remote '{raw}' saved.")
            return "rclone", raw, storage_name

        print("  Please enter a correct remote name.")


# ─────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────

def run_backup_menu(app: Any = None, session_id: Optional[str] = None) -> None:
    """
    Entry point called from main.py / CLIManager when the user selects Option 4.

    Collects all inputs interactively, then calls run_backup_flow().
    The "delete local backup?" question is no longer asked here — it is
    asked inside run_backup_flow() AFTER the upload has succeeded.
    """
    _header()
    config = load_config()

    # ── Collect inputs ──────────────────────────────────────────────────
    source_paths     = _collect_source_paths()
    destination_path = _collect_destination_path(config)
    zip_data         = _ask_zip()
    cloud_backup     = _ask_cloud_backup()

    cloud_method    = None
    rclone_remote   = None
    rclone_storage  = None

    if cloud_backup:
        cloud_method, rclone_remote, rclone_storage = _select_cloud_method(config)
        # NOTE: We do NOT ask about local deletion here.
        # run_backup_flow() will ask AFTER a successful upload.

    # ── Run the backup ──────────────────────────────────────────────────
    result = run_backup_flow(
        source_paths=source_paths,
        destination_path=destination_path,
        zip_data=zip_data,
        cloud_backup=cloud_backup,
        cloud_method=cloud_method,
        rclone_remote_name=rclone_remote,
        rclone_storage_name=rclone_storage,
        config=config,
    )

    # ── Show summary ────────────────────────────────────────────────────
    print()
    print(result.summary())

    _prompt("Press any key to continue…")