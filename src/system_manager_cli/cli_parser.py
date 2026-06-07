"""
cli_parser.py — argparse-based command interface for SysNova.

Supports two modes:
  1. Interactive TUI  — python main.py  (no arguments)
  2. Direct CLI       — sysmanager <command> [options]

Commands
────────
  health    System health monitor
  analyze   Analyze log files
  backup    Backup files or directories
  organize  Categorize files in a folder
  schedule  Manage scheduled tasks (list / add / run / remove / enable / disable)
  status    Quick system overview (one screen)
  update    Check or install software updates
  login     Authenticate interactively
  logout    Clear session token

Usage examples
──────────────
  sysmanager health
  sysmanager health --watch --interval 5
  sysmanager analyze /var/log --email admin@example.com
  sysmanager backup /src --dest /backups --zip --cloud gdrive
  sysmanager backup --list
  sysmanager organize /Downloads --dry-run
  sysmanager schedule list
  sysmanager schedule run 3
  sysmanager status
  sysmanager status --json
  sysmanager update --check
  sysmanager update --install --yes
  sysmanager update --install --force

Fix notes
─────────
  - Added --force and -y/--yes to the update subcommand so that
    update.py's getattr(args, "force"/"yes") are actually settable.
  - Removed overly-restrictive choices from backup --cloud; now any
    provider string is accepted (gdrive, gdrive2, onedrive, dropbox,
    s3, b2, sftp, rclone, …).
  - Added --verbose to every subparser that uses getattr(args,"verbose").
  - Made analyze --output consistent with --json (both drive JSON output;
    the command handler now checks both).
  - Added --json to schedule run / remove / enable / disable for
    machine-readable confirmation output.
"""

from __future__ import annotations

import argparse
import textwrap
import sys
import os

APP_NAME    = os.path.basename(sys.executable) if getattr(sys, 'frozen', False) else "sysmanager"
APP_VERSION = "1.0.0"
APP_DESC    = "SysNova — Intelligent System Management Platform"


# ─────────────────────────────────────────────────────────────────────────────
# Shared parent for flags that every subparser exposes
# ─────────────────────────────────────────────────────────────────────────────

def _shared_parent() -> argparse.ArgumentParser:
    """
    Return a parent parser that carries the flags common to all subcommands.

    Using add_parser(parents=[...]) avoids copy-pasting --verbose / --quiet
    into every subparser while keeping them reachable as args.verbose etc.
    conflict_handler='resolve' silences the duplicate --help warning.
    """
    p = argparse.ArgumentParser(add_help=False, conflict_handler="resolve")
    p.add_argument(
        "-v", "--verbose", action="store_true", default=False,
        help="Verbose / debug output",
    )
    p.add_argument(
        "-q", "--quiet", action="store_true", default=False,
        help="Suppress non-essential output",
    )
    p.add_argument(
        "--no-color", action="store_true", default=False,
        help="Disable ANSI colours (also honoured via NO_COLOR env var)",
    )
    return p


# ─────────────────────────────────────────────────────────────────────────────
# Builder
# ─────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    """
    Build and return the root ArgumentParser.

    The parser uses RawDescriptionHelpFormatter so the epilog example block
    is displayed verbatim.
    """
    shared = _shared_parent()

    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description=APP_DESC,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[shared],
        epilog=textwrap.dedent("""\
            Examples:
              sysmanager health                          Quick health check
              sysmanager health --watch                  Live refresh (Ctrl+C to stop)
              sysmanager health --watch --interval 5     Custom refresh rate
              sysmanager analyze /var/log                Analyze a log directory
              sysmanager analyze . --no-ai               Skip AI enrichment
              sysmanager analyze /logs --email a@b.com   Email the report
              sysmanager backup /project --zip           Create zipped backup
              sysmanager backup --list                   List recent backups
              sysmanager backup /src --cloud gdrive      Backup + upload to Drive
              sysmanager organize /Downloads             Categorize files
              sysmanager organize /Downloads --dry-run   Preview without changes
              sysmanager schedule list                   List scheduled tasks
              sysmanager schedule add                    Interactively add a task
              sysmanager schedule run 3                  Run task #3 immediately
              sysmanager status                          Quick system overview
              sysmanager update --check                  Check for a newer release
              sysmanager update --install                Download and install update
              sysmanager update --install --yes          Install without prompting
              sysmanager login                           Interactive login
              sysmanager logout                          Clear session

            Run 'sysmanager <command> --help' for command-specific options.
        """),
    )

    # ── Global flags ─────────────────────────────────────────────────────────
    parser.add_argument(
        "--version", action="version",
        version=f"%(prog)s {APP_VERSION}",
    )
    parser.add_argument(
        "--json", action="store_true", default=False,
        help="Output machine-readable JSON (where supported)",
    )

    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # ── health ───────────────────────────────────────────────────────────────
    p_health = sub.add_parser(
        "health",
        parents=[shared],
        help="Show system health (CPU / RAM / Disk / Network)",
        description=(
            "Display real-time system resource usage.\n\n"
            "Use --watch for a live auto-refreshing view."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_health.add_argument(
        "--watch", action="store_true", default=False,
        help="Auto-refresh every INTERVAL seconds (default 3)",
    )
    p_health.add_argument(
        "--interval", type=int, default=3, metavar="SEC",
        help="Refresh interval in seconds when --watch is set (default: 3)",
    )
    p_health.add_argument(
        "--json", action="store_true", default=False,
        help="Output as JSON and exit (ignores --watch)",
    )

    # ── analyze ──────────────────────────────────────────────────────────────
    p_analyze = sub.add_parser(
        "analyze",
        parents=[shared],
        help="Analyze log files and generate a report",
        description=(
            "Run the log analysis pipeline on a file or directory.\n\n"
            "Both --output json and --json produce the same JSON output."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_analyze.add_argument(
        "path", nargs="?", default="",
        help="Log file or directory to analyze (default: current directory)",
    )
    p_analyze.add_argument(
        "--no-ai", action="store_true", default=False,
        help="Skip AI enrichment (faster, no API calls)",
    )
    p_analyze.add_argument(
        "--email", metavar="ADDRESS", default="",
        help="E-mail the report to this address after analysis",
    )
    p_analyze.add_argument(
        "--output", choices=["text", "json"], default="text",
        metavar="{text,json}",
        help="Report format: text (default) or json — equivalent to --json",
    )
    p_analyze.add_argument(
        "--json", action="store_true", default=False,
        help="Shorthand for --output json",
    )

    # ── backup ───────────────────────────────────────────────────────────────
    p_backup = sub.add_parser(
        "backup",
        parents=[shared],
        help="Back up files or directories",
        description=(
            "Create a local (and optionally cloud) backup.\n\n"
            "Supported cloud providers: gdrive, gdrive2, onedrive, "
            "dropbox, s3, b2, sftp, rclone"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_backup.add_argument(
        "source", nargs="*",
        help="Source path(s) to back up",
    )
    p_backup.add_argument(
        "--dest", metavar="PATH", default="",
        help="Destination directory for the backup",
    )
    p_backup.add_argument(
        "--zip", action="store_true", default=False,
        help="Compress the backup into a ZIP archive",
    )
    p_backup.add_argument(
        "--cloud",
        metavar="PROVIDER",
        default="",
        help=(
            "Upload to a cloud provider after backup. "
            "Supported: gdrive, gdrive2, onedrive, dropbox, s3, b2, sftp, rclone"
        ),
    )
    p_backup.add_argument(
        "--list", action="store_true", default=False,
        help="List recent backup history and exit",
    )
    p_backup.add_argument(
        "--json", action="store_true", default=False,
        help="Output machine-readable JSON",
    )
    p_backup.add_argument(
        "--type",
        choices=["full", "incremental", "differential"],
        default="incremental",
        dest="backup_type",
        help="Backup type (default: incremental)",
    )
    p_backup.add_argument(
        "-y", "--yes", action="store_true", default=False,
        help="Skip confirmation prompts",
    )

    # ── organize ─────────────────────────────────────────────────────────────
    p_org = sub.add_parser(
        "organize",
        parents=[shared],
        help="Categorize and organize files in a folder",
        description=(
            "Sort files into category sub-folders; optionally clean temp files."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_org.add_argument(
        "path",
        help="Folder to organize",
    )
    p_org.add_argument(
        "--dry-run", action="store_true", default=False,
        help="Preview what would be moved without making changes",
    )
    p_org.add_argument(
        "--delete-temp", action="store_true", default=False,
        help="Permanently delete temp files (instead of quarantine)",
    )
    p_org.add_argument(
        "--json", action="store_true", default=False,
        help="Output machine-readable JSON",
    )

    # ── schedule ─────────────────────────────────────────────────────────────
    p_sched = sub.add_parser(
        "schedule",
        parents=[shared],
        help="Manage scheduled tasks",
        description=(
            "List, add, run, enable, disable, or remove scheduled automation tasks.\n\n"
            "Subcommands:\n"
            "  list      Show all scheduled tasks\n"
            "  add       Interactively create a new task\n"
            "  run       Execute a task immediately\n"
            "  remove    Delete a scheduled task\n"
            "  enable    Re-enable a disabled task\n"
            "  disable   Pause a task without deleting it"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sc_sub = p_sched.add_subparsers(dest="schedule_cmd", metavar="<subcommand>")

    sc_list = sc_sub.add_parser(
        "list",
        parents=[shared],
        help="Show all scheduled tasks",
    )
    sc_list.add_argument(
        "--json", action="store_true", default=False,
        help="Output machine-readable JSON",
    )

    sc_sub.add_parser(
        "add",
        parents=[shared],
        help="Interactively create a new task",
    )

    sc_run = sc_sub.add_parser(
        "run",
        parents=[shared],
        help="Execute a task immediately by its numeric ID",
    )
    sc_run.add_argument("task_id", type=int, help="Numeric task ID (from schedule list)")
    sc_run.add_argument(
        "--json", action="store_true", default=False,
        help="Output machine-readable JSON",
    )

    sc_del = sc_sub.add_parser(
        "remove",
        parents=[shared],
        help="Delete a scheduled task",
    )
    sc_del.add_argument("task_id", type=int, help="Numeric task ID (from schedule list)")
    sc_del.add_argument(
        "-y", "--yes", action="store_true", default=False,
        help="Skip confirmation prompt",
    )
    sc_del.add_argument(
        "--json", action="store_true", default=False,
        help="Output machine-readable JSON",
    )

    sc_ena = sc_sub.add_parser(
        "enable",
        parents=[shared],
        help="Re-enable a disabled task",
    )
    sc_ena.add_argument("task_id", type=int, help="Numeric task ID (from schedule list)")
    sc_ena.add_argument(
        "--json", action="store_true", default=False,
        help="Output machine-readable JSON",
    )

    sc_dis = sc_sub.add_parser(
        "disable",
        parents=[shared],
        help="Pause a task without deleting it",
    )
    sc_dis.add_argument("task_id", type=int, help="Numeric task ID (from schedule list)")
    sc_dis.add_argument(
        "--json", action="store_true", default=False,
        help="Output machine-readable JSON",
    )

    # ── status ───────────────────────────────────────────────────────────────
    p_status = sub.add_parser(
        "status",
        parents=[shared],
        help="Quick system overview (health + backup + tasks — one screen)",
        description=(
            "Display a compact snapshot of system health, last backup, "
            "and scheduled task count."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_status.add_argument(
        "--json", action="store_true", default=False,
        help="Output as JSON",
    )

    # ── update ───────────────────────────────────────────────────────────────
    p_update = sub.add_parser(
        "update",
        parents=[shared],
        help="Check or install software updates",
        description=(
            "Check the configured release source and optionally install an "
            "available update.\n\n"
            "Without a flag the command defaults to --check."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    update_action = p_update.add_mutually_exclusive_group()
    update_action.add_argument(
        "--check", action="store_true", default=False,
        help="Only check whether a newer release is available (default)",
    )
    update_action.add_argument(
        "--install", action="store_true", default=False,
        help="Download and install the latest available release",
    )
    update_action.add_argument(
        "--status", action="store_true", default=False,
        dest="update_status",
        help="Show local updater status (current version, pending updates, etc.)",
    )
    p_update.add_argument(
        "--force", action="store_true", default=False,
        help="Force re-download even when already up to date",
    )
    p_update.add_argument(
        "-y", "--yes", action="store_true", default=False,
        help="Skip confirmation prompt when installing",
    )
    p_update.add_argument(
        "--json", action="store_true", default=False,
        help="Output as JSON",
    )

    # ── login ─────────────────────────────────────────────────────────────────
    sub.add_parser(
        "login",
        parents=[shared],
        help="Authenticate with the backend",
        description="Interactively log in and store the session token.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # ── logout ────────────────────────────────────────────────────────────────
    sub.add_parser(
        "logout",
        parents=[shared],
        help="Clear the stored session token",
        description="Log out and delete the locally cached JWT.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    return parser


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: parse from a list of strings (useful for testing)
# ─────────────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """
    Parse *argv* (or sys.argv[1:] if None) and return the Namespace.

    Does NOT call sys.exit — callers handle SystemExit from --version / --help.
    """
    return build_parser().parse_args(argv)