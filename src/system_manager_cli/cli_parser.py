"""
cli_parser.py - argparse-based command interface for SysNova.

Supports two modes:
  1. Interactive TUI  — python main.py  (no arguments)
  2. Direct CLI       — sysmanager <command> [options]

Commands
────────
  health    System health monitor
  analyze   Analyze log files
  backup    Backup files or directories
  organize  Categorize files in a folder
  schedule  Manage scheduled tasks (list / add / run / remove)
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
"""

from __future__ import annotations

import argparse
import textwrap

APP_NAME    = "sysmanager"
APP_VERSION = "1.0.0"
APP_DESC    = "SysNova - Intelligent System Management Platform"


# ─────────────────────────────────────────────────────────────────────────────
# Builder
# ─────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    """
    Build and return the root ArgumentParser.

    The parser uses RawDescriptionHelpFormatter so the epilog example block
    is displayed verbatim.
    """
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description=APP_DESC,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              sysmanager health                    Quick health check
              sysmanager health --watch            Live refresh (Ctrl+C to stop)
              sysmanager analyze /var/log          Analyze a log directory
              sysmanager analyze . --no-ai         Skip AI enrichment
              sysmanager backup /project --zip     Create zipped backup
              sysmanager backup --list             List recent backups
              sysmanager organize /Downloads       Categorize files
              sysmanager schedule list             List scheduled tasks
              sysmanager status                    Quick system overview
              sysmanager update --check            Check for a newer release
              sysmanager login                     Interactive login
              sysmanager logout                    Clear session

            Run 'sysmanager <command> --help' for command-specific options.
        """),
    )

    # ── Global flags ────────────────────────────────────────────────────
    parser.add_argument(
        "--version", action="version",
        version=f"%(prog)s {APP_VERSION}",
    )
    parser.add_argument(
        "--no-color", action="store_true", default=False,
        help="Disable ANSI colors (also set NO_COLOR env var)",
    )
    parser.add_argument(
        "--json", action="store_true", default=False,
        help="Output machine-readable JSON (where supported)",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", default=False,
        help="Suppress non-essential output",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", default=False,
        help="Verbose / debug output",
    )

    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # ── health ──────────────────────────────────────────────────────────
    p_health = sub.add_parser(
        "health",
        help="Show system health (CPU / RAM / Disk / Network)",
        description="Display real-time system resource usage.",
    )
    p_health.add_argument(
        "--watch", action="store_true", default=False,
        help="Auto-refresh every INTERVAL seconds (default 3)",
    )
    p_health.add_argument(
        "--interval", type=int, default=3, metavar="SEC",
        help="Refresh interval in seconds when --watch is set (default 3)",
    )
    p_health.add_argument(
        "--json", action="store_true", default=False,
        help="Output as JSON",
    )

    # ── analyze ─────────────────────────────────────────────────────────
    p_analyze = sub.add_parser(
        "analyze",
        help="Analyze log files and generate a report",
        description="Run the 8-stage log analysis pipeline on a file or directory.",
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
        help="Report output format (default: text)",
    )
    p_analyze.add_argument(
        "--json", action="store_true", default=False,
        help="Output machine-readable JSON",
    )

    # ── backup ──────────────────────────────────────────────────────────
    p_backup = sub.add_parser(
        "backup",
        help="Back up files or directories",
        description="Create a local (and optionally cloud) backup.",
    )
    p_backup.add_argument(
        "source", nargs="*",
        help="Source paths to back up",
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
        "--cloud", choices=["gdrive", "rclone"], metavar="PROVIDER",
        default="",
        help="Cloud upload provider: gdrive or rclone",
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

    # ── organize ─────────────────────────────────────────────────────────
    p_org = sub.add_parser(
        "organize",
        help="Categorize and organize files in a folder",
        description="Sort files into category sub-folders; optionally clean temp files.",
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

    # ── schedule ─────────────────────────────────────────────────────────
    p_sched = sub.add_parser(
        "schedule",
        help="Manage scheduled tasks",
        description="List, add, run, or remove scheduled automation tasks.",
    )
    sc_sub = p_sched.add_subparsers(dest="schedule_cmd", metavar="<subcommand>")

    sc_list = sc_sub.add_parser("list", help="Show all scheduled tasks")
    sc_list.add_argument(
        "--json", action="store_true", default=False,
        help="Output machine-readable JSON",
    )

    sc_sub.add_parser("add", help="Interactively create a new task")

    sc_run = sc_sub.add_parser("run",    help="Execute a task immediately")
    sc_run.add_argument("task_id", type=int, help="Numeric task ID")

    sc_del = sc_sub.add_parser("remove", help="Delete a scheduled task")
    sc_del.add_argument("task_id", type=int, help="Numeric task ID")

    sc_ena = sc_sub.add_parser("enable",  help="Enable a paused task")
    sc_ena.add_argument("task_id", type=int)

    sc_dis = sc_sub.add_parser("disable", help="Disable a task without deleting it")
    sc_dis.add_argument("task_id", type=int)

    # ── status ───────────────────────────────────────────────────────────
    p_status = sub.add_parser(
        "status",
        help="Quick system overview (one screen)",
        description="Display a compact snapshot of system health, last backup, and tasks.",
    )
    p_status.add_argument(
        "--json", action="store_true", default=False,
        help="Output as JSON",
    )

    # ── update ─────────────────────────────────────────────────────────
    p_update = sub.add_parser(
        "update",
        help="Check or install software updates",
        description="Check the configured release source and optionally install an available update.",
    )
    update_action = p_update.add_mutually_exclusive_group()
    update_action.add_argument(
        "--check", action="store_true", default=False,
        help="Only check whether a newer release is available",
    )
    update_action.add_argument(
        "--install", action="store_true", default=False,
        help="Download and install the latest available release",
    )
    update_action.add_argument(
        "--status", action="store_true", default=False,
        help="Show local updater status",
    )
    p_update.add_argument(
        "--json", action="store_true", default=False,
        help="Output as JSON",
    )

    # ── login ────────────────────────────────────────────────────────────
    sub.add_parser(
        "login",
        help="Authenticate with the backend",
        description="Interactively log in and store the session token.",
    )

    # ── logout ───────────────────────────────────────────────────────────
    sub.add_parser(
        "logout",
        help="Clear the stored session token",
        description="Log out and delete the locally cached JWT.",
    )

    return parser


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: parse from a list of strings (useful for testing)
# ─────────────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """
    Parse *argv* (or sys.argv[1:] if None) and return the Namespace.

    Does NOT call sys.exit — catches SystemExit from --version / --help and
    re-raises so callers can handle them cleanly.
    """
    return build_parser().parse_args(argv)
