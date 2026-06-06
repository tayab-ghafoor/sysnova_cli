"""CLI Orchestrator — thin shell that delegates to sub-menu modules.

Architecture rule: CLI can ONLY communicate with app.py.
All sub-menu logic lives in the dedicated menu modules under CLI/.
CLIManager owns the top-level loop and authentication gate only;
it never implements business actions itself.

Why this file was rewritten (Fix 2):
    The original CLIManager contained a second, diverged copy of the
    main menu loop with stub sub-menu implementations.  main.py already
    contained the correct, complete implementations.  Having two loops
    caused a split-brain: running `CLIManager.run()` gave a broken
    experience while running `main.py` worked correctly.

    This version removes the duplicate logic entirely.  CLIManager now
    delegates every sub-menu call to the same functions used by main.py,
    so both entry points produce identical behaviour.
"""

from __future__ import annotations

import getpass
from typing import Any

from system_manager_cli.CLI.menu import MenuDisplay
from system_manager_cli.CLI.prompts import PromptCollector
from system_manager_cli.ulits.logger import get_logger

logger = get_logger(__name__)


class CLIManager:
    """Top-level CLI orchestrator.

    Owns:
      - The authentication gate (login / register / verify loop)
      - The main menu loop
      - Routing each menu choice to the correct sub-menu module

    Does NOT own:
      - Any sub-menu implementation
      - Any business logic
      - Any direct calls to core/, analysis/, or reporting/
    """

    def __init__(self, app: Any):
        self.app    = app
        self.menu   = MenuDisplay()
        self.prompts = PromptCollector()

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the application — authentication gate then main loop."""
        logger.info("CLIManager.run() started")
        session_id, username = self._run_login_screen()
        self._run_main_loop(session_id, username)
        logger.info("CLIManager.run() finished")

    # ------------------------------------------------------------------
    # Authentication gate  (mirrors main.py:run_login_screen)
    # ------------------------------------------------------------------

    def _run_login_screen(self) -> tuple[str, str]:
        """Loop until the user authenticates.  Returns (session_id, username)."""
        while True:
            print("\n" + "=" * 52)
            print("       SYSNOVA")
            print("=" * 52)
            print("  1.  Login")
            print("  2.  Register")
            print("  3.  Verify Email")
            print("  0.  Exit")
            print("=" * 52)

            choice = input("\n  Select (0-3): ").strip()

            if choice == "1":
                ok, session_id, username = self._login()
                if ok:
                    return session_id, username

            elif choice == "2":
                self._register()

            elif choice == "3":
                self._verify_email()

            elif choice == "0":
                print("\n  Goodbye!\n")
                raise SystemExit(0)

            else:
                print("  ⚠️   Please enter 0, 1, 2, or 3.")

    # ------------------------------------------------------------------
    # Main menu loop  (mirrors main.py:main)
    # ------------------------------------------------------------------

    def _run_main_loop(self, session_id: str, username: str) -> None:
        while True:
            print("\n" + "=" * 52)
            print(f"  {username.upper()} — LOGGED IN")
            print("=" * 52)
            print("       MAIN MENU")
            print("=" * 52)
            print("  1.  Health Monitor")
            print("  2.  File Categorization & Temp File Deletion")
            print("  3.  Logs Analysis System")
            print("  4.  Data Backup System")
            print("  5.  Schedule Tasks")
            print("  6.  Settings")
            print("  7.  Logout")
            print("  0.  Exit")
            print("=" * 52)

            choice = input("\n  Select (0-7): ").strip()

            if choice == "1":
                self._health_monitor()
            elif choice == "2":
                self._file_categorization(session_id)
            elif choice == "3":
                self._logs_analysis(session_id)
            elif choice == "4":
                self._data_backup()
            elif choice == "5":
                self._schedule_tasks(session_id)
            elif choice == "6":
                self._settings()
            elif choice == "7":
                print(f"\n  ✅  Logged out. See you next time, {username}!")
                session_id, username = self._run_login_screen()
            elif choice == "0":
                print(f"\n  Goodbye, {username}!\n")
                raise SystemExit(0)
            else:
                print("  ⚠️   Invalid choice. Please enter a number from 0 to 7.")

    # ------------------------------------------------------------------
    # Sub-menu delegates — each calls the real implementation module.
    # NO business logic lives here.
    # ------------------------------------------------------------------

    def _health_monitor(self) -> None:
        from system_manager_cli.CLI.health_menu import run_health_menu
        run_health_menu(self.app)

    def _file_categorization(self, session_id: str) -> None:
        from system_manager_cli.CLI.file_organizer_menu import run_file_organizer_menu
        run_file_organizer_menu(self.app, session_id)

    def _logs_analysis(self, session_id: str) -> None:
        from system_manager_cli.CLI.logs_menu import run_logs_menu
        run_logs_menu(self.app, session_id)

    def _data_backup(self) -> None:
        from system_manager_cli.CLI.backup_menu import run_backup_menu
        run_backup_menu(self.app)

    def _schedule_tasks(self, session_id: str) -> None:
        from system_manager_cli.CLI.schedule_menu import run_schedule_menu
        run_schedule_menu(self.app, session_id)

    def _settings(self) -> None:
        from system_manager_cli.CLI.settings_menu import run_settings_menu
        run_settings_menu(self.app)

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    def _login(self) -> tuple[bool, str, str]:
        print("\n" + "=" * 52)
        print("  LOGIN")
        print("=" * 52)

        email = self._collect_email()
        if not email:
            return False, "", ""

        password = self._collect_password("Enter Password:")
        if not password:
            return False, "", ""

        result = self.app.execute_login_user(email, password)
        data   = result.get("data", {})

        if result.get("status") == "success":
            user     = data.get("user", {})
            username = user.get("full_name") or user.get("username") or email.split("@")[0]
            token    = data.get("token", "session_ok")
            print(f"\n  ✅  Welcome back, {username}!")
            return True, token, username

        msg = data.get("message", result.get("error", "Login failed."))
        print(f"\n  ❌  {msg}")
        return False, "", ""

    def _register(self) -> None:
        print("\n" + "=" * 52)
        print("  REGISTER")
        print("=" * 52)

        full_name = input("\n  Enter Full Name: ").strip()
        if not full_name:
            return

        email = self._collect_email()
        if not email:
            return

        password = self._collect_password("Enter Password:")
        if not password:
            return

        confirm = self._collect_password("Confirm Password:")
        if confirm is None:
            return

        result = self.app.execute_register_user(full_name, email, password, confirm)
        data   = result.get("data", {})
        msg    = data.get("message", result.get("error", ""))

        if result.get("status") == "success":
            print(f"\n  ✅  {msg}")
            code = data.get("verification_code")
            if code:
                print()
                print("  Development verification code:")
                print(f"  {code}")
        else:
            print(f"\n  ❌  {msg}")

        input("\n  Press any key to continue...")

    def _verify_email(self) -> None:
        print("\n" + "=" * 52)
        print("  VERIFY EMAIL")
        print("=" * 52)

        email = self._collect_email()
        if not email:
            return

        code = input("\n  Enter Verification Code: ").strip()
        if not code:
            return

        result = self.app.execute_verify_email(email, code)
        data   = result.get("data", {})
        msg    = data.get("message", result.get("error", ""))

        if result.get("status") == "success":
            print(f"\n  ✅  {msg}")
        else:
            print(f"\n  ❌  {msg}")

        input("\n  Press any key to continue...")

    # ------------------------------------------------------------------
    # Input helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_email() -> str:
        """Prompt until a structurally valid email is entered, or blank to cancel."""
        while True:
            value = input("\n  Enter Email Address (blank to cancel): ").strip()
            if not value:
                return ""
            if "@" in value and "." in value:
                return value
            print("  ⚠️   Please enter a valid email address.")

    @staticmethod
    def _collect_password(label: str = "Enter Password:") -> str | None:
        """Ask show/hide preference then read password.  Returns None on cancel.
        
        FIX #12: Uses SmartInput with is_sensitive=True to prevent password
        from being added to readline history when user chooses to show password.
        """
        from system_manager_cli.ulits.smart_input import smart_prompt
        
        show = input("\n  Show password while typing? (y/n, blank to cancel): ").strip().lower()
        if not show:
            return None
        if show in ("y", "yes"):
            # Password visible while typing → use SmartInput with is_sensitive=True
            # to prevent readline history capture
            value = smart_prompt(label, is_sensitive=True)
        else:
            # getpass.getpass() doesn't echo; history is not a concern here
            value = getpass.getpass(f"  {label} ")
        return value or None
