#!/usr/bin/env python3
"""SysNova - Application entry point."""

from __future__ import annotations

import getpass
import sys
import traceback
from pathlib import Path
from datetime import datetime
from system_manager_cli.ulits.theme import T, colorize
from system_manager_cli.phase3_features import setup_readline, read_input_with_history, PHASE3_ENABLED

# For arrow key interception on Windows
try:
    import msvcrt
except ImportError:
    msvcrt = None

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# main.py  (at the top, after sys.path setup, before any app imports)

import logging

def _configure_stdio() -> None:
    """Prevent UnicodeEncodeError on Windows consoles with legacy code pages."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(errors="replace")
            except Exception:
                pass


_configure_stdio()


# ============================================================================
# Apply any pending update BEFORE importing SystemManagerApp so new code loads
# ============================================================================
def _apply_pending_update_before_init() -> bool:
    """Apply any staged update before the app loads, then restart."""
    try:
        from system_manager_cli.config.config import Config
        from system_manager_cli.updater.auto_updater import AutoUpdater

        Config.ensure_directories()
        updater = AutoUpdater(state_path=Config.DATA_DIR / "updater")
        if updater.apply_pending_update():
            updater.restart_application()
            return True   # restart failed; caller decides what to do
    except Exception as exc:
        logging.getLogger(__name__).error(
            "Pending update application failed: %s", exc, exc_info=True
        )
    return False


_apply_pending_update_before_init()

# Only NOW import the rest of the app:
from system_manager_cli.app import SystemManagerApp

def _bootstrap() -> "SystemManagerApp":  # noqa: F821
    """Initialise the app; exit cleanly on fatal errors."""
    try:
        # Suppress INFO logs on startup to keep the UI clean for the user
        logging.getLogger("system_manager_cli").setLevel(logging.WARNING)

        # Validate backend configuration early
        from system_manager_cli.config.config import Config
        is_valid, msg = Config.validate_backend_url()
        if not is_valid:
            print(f"\n  [WARNING] {msg}", file=sys.stderr)
        
        return SystemManagerApp()
    except Exception as exc:
        print(f"\n  [ERROR] Fatal startup error: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise SystemExit(1) from exc

# ============================================================================
# UI helpers
# ============================================================================
def _draw_status_bar(username: str, app: SystemManagerApp):
    """Render a professional top status bar."""
    ts = datetime.now().strftime("%H:%M:%S")
    status = colorize("● Live", T.SUCCESS) if getattr(app, "_backend_online", False) else colorize("○ Offline", T.WARNING)
    header = f"  ⚡ SysNova  │  {username.lower()}  │  v1.0  │  {ts}  │  {status}"
    
    print(colorize("\n  ╔" + "═" * 66 + "╗", T.PRIMARY))
    print(colorize("  ║", T.PRIMARY) + header + " " * (66 - 52) + colorize("║", T.PRIMARY))
    print(colorize("  ╚" + "═" * 66 + "╝", T.PRIMARY))

def _div(char="=", width=52):
    print(colorize("  " + char * width, T.PRIMARY))

def _header(title: str):
    print(colorize("\n  ── " + title + " ──────────────────────────────────────────", T.BOLD + T.PRIMARY))

def _prompt(msg: str) -> str:
    if PHASE3_ENABLED:
        return read_input_with_history(colorize(f"  {msg} ", T.BOLD + T.PRIMARY))
    return input(f"  {msg} ").strip()

def _pause():
    input(colorize("\n  Press [Enter] to continue...", T.DIM))

def _clear_line():
    if sys.platform == 'win32':
        import os
        os.system('cls')
    else:
        print("\033[2K\033[1G", end='')


# ============================================================================
# LOGIN / REGISTER / VERIFY
# ============================================================================
def _get_password(label: str = "Enter Password:") -> str:
    """Ask whether to show password while typing, then read it.
    
    FIX #12: Uses SmartInput with is_sensitive=True to prevent password
    from being added to readline history when user chooses to show password.
    """
    from system_manager_cli.ulits.smart_input import smart_prompt
    
    show = _prompt("Show password while typing? (y/n):").lower()
    if show in ("y", "yes"):
        # Password visible while typing → use SmartInput with is_sensitive=True
        # to prevent readline history capture
        return smart_prompt(label, is_sensitive=True)
    else:
        # getpass.getpass() doesn't echo; history is not a concern here
        return getpass.getpass(f"  {label} ")


def _login(app) -> tuple[bool, str, str]:
    """
    Returns (success, session_id, username).
    """
    _header("LOGIN")
    email = ""
    while True:
        email = _prompt("Enter Email Address:")
        if not email:
            return False, "", ""
        if "@" in email and "." in email:
            break
        print("  [WARN] Please enter a valid email address.")

    password = _get_password()
    if not password:
        return False, "", ""

    print("\n  Checking credentials...", flush=True)
    result = app.execute_login_user(email, password)
    data   = result.get("data", {})

    if result.get("status") == "success":
        user     = data.get("user", {})
        username = user.get("full_name") or user.get("username") or email.split("@")[0]
        token    = data.get("token", "session_ok")
        print(f"\n  [OK] Welcome back, {username}!")
        return True, token, username
    else:
        msg = data.get("message") or data.get("error") or result.get("error", "Login failed.")
        print(f"\n  [ERROR] {msg}")
        print("  Forgot your password? Use option 4 from the main menu.")
        return False, "", ""


def _register(app) -> bool:
    _header("REGISTER")

    full_name = _prompt("Enter Full Name:")
    if not full_name:
        return False

    email = ""
    while True:
        email = _prompt("Enter Email Address:")
        if not email:
            return False
        if "@" in email and "." in email:
            break
        print("  [WARN] Please enter a valid email address.")

    password         = _get_password()
    confirm_password = _get_password("Confirm Password:")

    result = app.execute_register_user(full_name, email, password, confirm_password)
    data   = result.get("data", {})
    msg    = data.get("message") or data.get("error") or result.get("error", "")

    if result.get("status") == "success":
        print(f"\n  [OK] {msg}")

        # Development-only fallback: production never prints verification codes.
        verification_code = data.get("verification_code")
        if verification_code:
            print()
            print("  Development verification code:")
            print(f"  {verification_code}")

        _pause()
        return True
    else:
        print(f"\n  [ERROR] {msg}")
        _pause()
        return False


def _verify_email(app) -> bool:
    _header("VERIFY EMAIL")

    email = ""
    while True:
        email = _prompt("Enter Email Address:")
        if not email:
            return False
        if "@" in email and "." in email:
            break
        print("  [WARN] Please enter a valid email address.")

    code = _prompt("Enter Verification Code:")
    if not code:
        return False

    result = app.execute_verify_email(email, code)
    data   = result.get("data", {})
    msg    = data.get("message") or data.get("error") or result.get("error", "")

    if result.get("status") == "success":
        print(f"\n  [OK] {msg}")
    else:
        print(f"\n  [ERROR] {msg}")
        resend = _prompt("Resend verification code? (y/N):").strip().lower()
        if resend in ("y", "yes"):
            result2 = app.execute_resend_verification_code(email)
            data2 = result2.get("data", {})
            msg2 = data2.get("message") or data2.get("error") or result2.get("error", "")
            if result2.get("status") == "success":
                print(f"\n  [OK] {msg2}")
            else:
                print(f"\n  [ERROR] {msg2}")
    _pause()
    return result.get("status") == "success"


def _forgot_password(app) -> None:
    _header("FORGOT PASSWORD")

    email = ""
    while True:
        email = _prompt("Enter Email Address:")
        if not email:
            return
        if "@" in email and "." in email:
            break
        print("  [WARN] Please enter a valid email address.")

    result = app.execute_forgot_password(email)
    data   = result.get("data", {})
    msg    = data.get("message") or data.get("error") or result.get("error", "")

    if result.get("status") == "success":
        print(f"\n  [OK] {msg}")
        _pause()
        _header("RESET PASSWORD")

        while True:
            reset_code = _prompt("Enter Reset Code (sent to email):")
            if not reset_code:
                print("  [WARN] Reset code is required.")
                continue
            if len(reset_code.strip()) < 4:
                print("  [WARN] Reset code is too short.")
                continue
            break

        while True:
            new_password = _get_password("Enter New Password:")
            if not new_password:
                print("  [WARN] Password is required.")
                continue
            if len(new_password) < 6:
                print("  [WARN] Password must be at least 6 characters long.")
                continue
            break

        while True:
            confirm_password = _get_password("Confirm New Password:")
            if not confirm_password:
                print("  [WARN] Password confirmation is required.")
                continue
            if confirm_password != new_password:
                print("  [ERROR] Passwords do not match. Please try again.")
                continue
            break

        reset_result = app.execute_reset_password(
            email,
            reset_code,
            new_password,
            confirm_password,
        )
        reset_data = reset_result.get("data", {})
        reset_msg = (
            reset_data.get("message")
            or reset_data.get("error")
            or reset_result.get("error", "")
        )
        if reset_result.get("status") == "success":
            print(f"\n  [OK] {reset_msg}")
            print("\n  Your password has been reset. Please login with the new password.")
        else:
            print(f"\n  [ERROR] {reset_msg}")
    else:
        print(f"\n  [ERROR] {msg}")
    _pause()


def _resend_verification(app) -> None:
    _header("RESEND VERIFICATION")

    email = ""
    while True:
        email = _prompt("Enter Email Address:")
        if not email:
            return
        if "@" in email and "." in email:
            break
        print("  [WARN] Please enter a valid email address.")

    result = app.execute_resend_verification_code(email)
    data   = result.get("data", {})
    msg    = data.get("message") or data.get("error") or result.get("error", "")

    if result.get("status") == "success":
        print(f"\n  [OK] {msg}")
    else:
        print(f"\n  [ERROR] {msg}")
    _pause()


def run_login_screen(app) -> tuple[str, str]:
    """
    Show Login / Register / Exit loop.
    Returns (session_id, username) when authenticated.
    """
    while True:
        _clear_line()
        print(colorize("\n  ╔══════════════════════════════════════════════════╗", T.PRIMARY))
        print(colorize("  ║               S Y S N O V A                      ║", T.BOLD + T.WHITE))
        print(colorize("  ║      Intelligent Management Platform             ║", T.DIM))
        print(colorize("  ╚══════════════════════════════════════════════════╝", T.PRIMARY))
        
        print(f"\n  {colorize('[1]', T.PRIMARY)} Login")
        print(f"  {colorize('[2]', T.PRIMARY)} Register")
        print(f"  {colorize('[3]', T.PRIMARY)} Verify Email")
        print(f"  {colorize('[4]', T.PRIMARY)} Forgot Password")
        print(f"  {colorize('[5]', T.PRIMARY)} Resend Verification")
        print(f"  {colorize('[0]', T.DIM)} Exit")

        if PHASE3_ENABLED:
            choice = read_input_with_history("\n  Select (0-5): ")
        else:
            choice = input("\n  Select (0-5): ").strip()

        if choice == "1":
            ok, session_id, username = _login(app)
            if ok:
                return session_id, username
        elif choice == "2":
            _register(app)
        elif choice == "3":
            _verify_email(app)
        elif choice == "4":
            _forgot_password(app)
        elif choice == "5":
            _resend_verification(app)
        elif choice == "0":
            print("\n  Goodbye!\n")
            raise SystemExit(0)
        else:
            print("  [WARN] Please enter 0, 1, 2, 3, 4, or 5.")


# ============================================================================
# MAIN MENU
# ============================================================================

def _print_main_menu(username: str, app: SystemManagerApp):
    _clear_line()
    _draw_status_bar(username, app)
    
    print(f"\n  {colorize('SYSTEM', T.DIM)}")
    print(f"   {colorize('[1]', T.PRIMARY)}    Health Monitor")
    print(f"   {colorize('[2]', T.PRIMARY)}    File Organizer")
    
    print(f"\n  {colorize('ANALYSIS', T.DIM)}")
    print(f"   {colorize('[3]', T.PRIMARY)}    Logs Analysis")
    
    print(f"\n  {colorize('DATA & AUTOMATION', T.DIM)}")
    print(f"   {colorize('[4]', T.PRIMARY)}    Data Backup")
    print(f"   {colorize('[5]', T.PRIMARY)}    Schedule Tasks")
    
    print(f"\n  {colorize('ACCOUNT', T.DIM)}")
    print(f"   {colorize('[6]', T.PRIMARY)}  ⚙  Settings")
    print(f"   {colorize('[7]', T.PRIMARY)}    Logout")
    print(f"   {colorize('[0]', T.DIM)}  ✖  Exit")
    
    print(colorize("\n  " + "─" * 68, T.DIM))
    print(colorize("   Type number or command  │  [Tab] Complete  │  [↑↓] History", T.DIM))


def _handle_main_menu_input(choice: str, app, session_id: str, username: str) -> tuple[bool, str, str]:
    """
    Handle main menu input (numbers and shortcuts).
    Returns (continue_loop, session_id, username).
    """
    choice_lower = choice.lower().strip()
    
    # Map shortcuts and numbers to actions
    actions = {
        '1': ('health', None),
        'h': ('health', None),
        '2': ('file', None),
        'f': ('file', None),
        '3': ('logs', None),
        'l': ('logs', None),
        '4': ('backup', None),
        'b': ('backup', None),
        '5': ('schedule', None),
        's': ('schedule', None),
        '6': ('settings', None),
        'c': ('settings', None),
        'cfg': ('settings', None),
        '7': ('logout', None),
        '0': ('exit', None),
        'q': ('exit', None),
        'exit': ('exit', None),
        'quit': ('exit', None),
        '?': ('help', None),
        'help': ('help', None),
    }
    
    action, _ = actions.get(choice_lower, ('invalid', None))
    
    if action == 'health':
        run_health_monitor(app)
        return True, session_id, username
    elif action == 'file':
        run_file_categorization(app, session_id)
        return True, session_id, username
    elif action == 'logs':
        run_logs_analysis(app, session_id)
        return True, session_id, username
    elif action == 'backup':
        run_backup(app)
        return True, session_id, username
    elif action == 'schedule':
        run_schedule_tasks(app, session_id)
        return True, session_id, username
    elif action == 'settings':
        run_settings(app)
        return True, session_id, username
    elif action == 'logout':
        print(f"\n  [OK] Logged out. See you next time, {username}!")
        return False, session_id, username  # Signal to re-login
    elif action == 'exit':
        print(f"\n  Goodbye, {username}!\n")
        raise SystemExit(0)
    elif action == 'help':
        _show_menu_help()
        return True, session_id, username
    elif action == 'invalid':
        print(f"  [WARN] Invalid choice '{choice}'. Use 1-7, shortcut (h/b/l/s/c/f), or ? for help.")
        return True, session_id, username
    
    return True, session_id, username


def _show_menu_help():
    """Show help for menu shortcuts."""
    _clear_line()
    _div()
    print("  MENU SHORTCUTS - QUICK REFERENCE")
    _div()
    print()
    print("  Number Selection:")
    print("    1 or h     Health Monitor")
    print("    2 or f     File Categorization")
    print("    3 or l     Logs Analysis")
    print("    4 or b     Backup System")
    print("    5 or s     Schedule Tasks")
    print("    6 or c     Settings / Config")
    print("    7          Logout")
    print("    0 or q     Exit / Quit")
    print()
    print("  Other Commands:")
    print("    ?          Show this help")
    print("    help       Show this help")
    print("    status     Quick system status")
    print()
    _div()
    _pause()


# ============================================================================
# OPTION 1 - HEALTH MONITOR
# ============================================================================

def run_health_monitor(app):
    from system_manager_cli.CLI.health_menu import run_health_menu
    run_health_menu(app)


# ============================================================================
# OPTION 2 - FILE CATEGORIZATION
# ============================================================================

def run_file_categorization(app, session_id: str):
    from system_manager_cli.CLI.file_organizer_menu import run_file_organizer_menu
    run_file_organizer_menu(app, session_id)


# ============================================================================
# OPTION 3 - LOGS ANALYSIS
# ============================================================================

def run_logs_analysis(app, session_id: str):
    from system_manager_cli.CLI.logs_menu import run_logs_menu
    run_logs_menu(app, session_id)


# ============================================================================
# OPTION 4 - DATA BACKUP
# ============================================================================

def run_backup(app):
    from system_manager_cli.CLI.backup_menu import run_backup_menu
    run_backup_menu()


# ============================================================================
# OPTION 5 - SCHEDULE TASKS
# ============================================================================

def run_schedule_tasks(app, session_id: str):
    from system_manager_cli.CLI.schedule_menu import run_schedule_menu
    run_schedule_menu(app, session_id)


# ============================================================================
# OPTION 6 - SETTINGS
# ============================================================================

def run_settings(app):
    from system_manager_cli.CLI.settings_menu import run_settings_menu
    run_settings_menu(app)


# ============================================================================
# COMMAND LINE INTERFACE ROUTING
# ============================================================================

def _handle_command(app, args) -> None:
    """Route CLI commands to their non-interactive handlers."""
    if getattr(args, "no_color", False):
        import os
        os.environ["NO_COLOR"] = "1"

    command = args.command
    exit_code = 0

    try:
        if command == "health":
            from system_manager_cli.commands.health import run
            exit_code = run(app, args)

        elif command == "analyze":
            from system_manager_cli.commands.analyze import run
            exit_code = run(app, args)

        elif command == "backup":
            from system_manager_cli.commands.backup import run
            exit_code = run(app, args)

        elif command == "organize":
            from system_manager_cli.commands.organize import run
            exit_code = run(app, args)

        elif command == "schedule":
            from system_manager_cli.commands.schedule import run
            exit_code = run(app, args)

        elif command == "status":
            from system_manager_cli.commands.status import run
            exit_code = run(app, args)

        elif command == "update":
            from system_manager_cli.commands.update import run
            exit_code = run(app, args)

        elif command == "login":
            ok, _session_id, _username = _login(app)
            exit_code = 0 if ok else 1

        elif command == "logout":
            result = app.execute_logout_user()
            if result.get("status") == "success":
                print("  [OK] Logged out.")
            else:
                print("  [WARN] Logout completed (no active session).")
            exit_code = 0

        else:
            print(f"  [ERROR] Unknown command: {command!r}", file=sys.stderr)
            print("  Run  sysmanager --help  for available commands.", file=sys.stderr)
            exit_code = 2

    except KeyboardInterrupt:
        print("\n  Interrupted by user.")
        exit_code = 130
    except SystemExit as exc:
        raise exc
    except Exception as exc:
        print(f"  [ERROR] Command failed: {exc}", file=sys.stderr)
        if getattr(args, "verbose", False):
            import traceback
            traceback.print_exc()
        exit_code = 3

    raise SystemExit(exit_code)


def _cmd_health(app, args) -> None:
    """Handle: sysmanager health [--watch] [--interval N] [--json]"""
    from system_manager_cli.CLI.health_menu import run_health_menu
    try:
        run_health_menu(app)
    except Exception as exc:
        print(f"  [ERROR] Health monitor failed: {exc}")
        raise SystemExit(1)


def _cmd_analyze(app, args) -> None:
    """Handle: sysmanager analyze <path> [--no-ai] [--email EMAIL]"""
    from system_manager_cli.CLI.logs_menu import run_logs_menu
    try:
        run_logs_menu(app, session_id="")
    except Exception as exc:
        print(f"  [ERROR] Analysis failed: {exc}")
        raise SystemExit(1)


def _cmd_backup(app, args) -> None:
    """Handle: sysmanager backup <src> --dest <dest> [--zip]"""
    from system_manager_cli.CLI.backup_menu import run_backup_menu
    try:
        run_backup_menu()
    except Exception as exc:
        print(f"  [ERROR] Backup failed: {exc}")
        raise SystemExit(1)


def _cmd_organize(app, args) -> None:
    """Handle: sysmanager organize <path> [--dry-run]"""
    from system_manager_cli.CLI.file_organizer_menu import run_file_organizer_menu
    try:
        run_file_organizer_menu(app, session_id="")
    except Exception as exc:
        print(f"  [ERROR] Organize failed: {exc}")
        raise SystemExit(1)


def _cmd_schedule(app, args) -> None:
    """Handle: sysmanager schedule [list | add | run ID]"""
    from system_manager_cli.CLI.schedule_menu import run_schedule_menu
    try:
        run_schedule_menu(app, session_id="")
    except Exception as exc:
        print(f"  [ERROR] Schedule command failed: {exc}")
        raise SystemExit(1)


def _cmd_status(app, args) -> None:
    """Handle: sysmanager status [--json]"""
    try:
        health = app.execute_health_check()
        update = app.execute_update_status()
        
        status_data = {
            "status": "Operational",
            "health": health.get("data", {}),
            "updater": update.get("data", {}),
            "timestamp": health.get("timestamp")
        }

        if hasattr(args, 'json') and args.json:
            import json
            print(json.dumps(status_data, indent=2))
        else:
            print("\n  [SYSTEM STATUS]")
            print(f"  Overall:  {status_data['status']}")
            print(f"  Version:  {status_data['updater'].get('current_version', 'Unknown')}")
    except Exception as exc:
        print(f"  [ERROR] Status check failed: {exc}")
        raise SystemExit(1)


def _cmd_update(app, args) -> None:
    """Handle: sysmanager update [--check | --install | --status]"""
    from system_manager_cli.commands.update import run
    raise SystemExit(run(app, args))


def _cmd_login(app, args) -> None:
    """Handle: sysmanager login"""
    try:
        print("  Interactive login...")
        _login(app)
    except Exception as exc:
        print(f"  [ERROR] Login failed: {exc}")
        raise SystemExit(1)


def _cmd_logout(app, args) -> None:
    """Handle: sysmanager logout"""
    try:
        print("  [OK] Logged out.")
    except Exception as exc:
        print(f"  [ERROR] Logout failed: {exc}")
        raise SystemExit(1)


# ============================================================================
# MAIN LOOP
# ============================================================================

def main():
    if PHASE3_ENABLED:
        setup_readline()
    """Main entry point: parse arguments, route to command or TUI."""
    _configure_stdio()
    from system_manager_cli import cli_parser
    # Parse CLI arguments
    parser = cli_parser.build_parser()
    args, remaining = parser.parse_known_args()

    if args.command:
        import os
        os.environ.setdefault("SYSTEM_MANAGER_CLI_QUIET_LOGS", "1")

    # Initialize app
    app = _bootstrap()
    
    try:
        # If a command was given, use CLI mode (not interactive TUI)
        if args.command:
            _handle_command(app, args)
            return
        
        # No command given - use interactive TUI (login + main menu)
        session_id, username = run_login_screen(app)
    except SystemExit as e:
        sys.exit(e.code)

    while True:
        _print_main_menu(username, app)
        
        if PHASE3_ENABLED:
            choice = read_input_with_history("\n  Enter choice: ")
        else:
            choice = input("\n  Enter choice: ").strip()

        if not choice:
            print("  [WARN] Please enter a valid choice.")
            continue
        
        try:
            continue_loop, session_id, username = _handle_main_menu_input(
                choice, app, session_id, username
            )
            if not continue_loop:
                # User chose logout - return to login screen
                session_id, username = run_login_screen(app)
        except KeyboardInterrupt:
            print("\n\n  [WARN] Interrupted. Returning to menu...")
            continue
        except SystemExit:
            raise
        except Exception as exc:
            print(f"  [ERROR] {exc}")
            continue


if __name__ == "__main__":
    main()
