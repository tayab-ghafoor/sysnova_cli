"""
phase3_features.py — Phase 3 Enhanced Input with Autocomplete and History.

Features
────────
- Tab autocomplete for menu shortcuts and commands
- Arrow-key command history navigation
- --json output for commands
- Inline help

Fixes applied
─────────────
- CommandHistory._load_history / _save_history now use the same XDG-compliant
  data directory as TaskScheduler instead of importing Config.DATA_DIR, which
  resolved to an inaccessible path (/data) and caused PermissionError on
  startup on Linux.
- Wrapped readline in try/except for Windows compatibility.
- Added macOS libedit compatibility for the tab-completion binding.
- Merged autocomplete logic so Tab-completion works for both shortcuts AND
  full commands.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

# Guard readline import for Windows / minimal containers.
try:
    import readline as _readline_module  # type: ignore[import]
    READLINE_AVAILABLE = True
except ImportError:
    try:
        import pyreadline3 as _readline_module  # type: ignore[import]
        READLINE_AVAILABLE = True
    except ImportError:
        _readline_module = None  # type: ignore[assignment]
        READLINE_AVAILABLE = False


# ── XDG-compliant data directory (mirrors task_scheduler.py) ──────────────────
# Centralised here so phase3_features never needs to import Config, which was
# the chain that ultimately led to the PermissionError on startup.

_APP_NAME = "sysnova"


def _get_data_dir() -> Path:
    """Return the application data directory, creating it if necessary."""
    xdg_data_home = os.environ.get("XDG_DATA_HOME", "").strip()
    if xdg_data_home:
        base = Path(xdg_data_home)
    else:
        base = Path.home() / ".local" / "share"
    data_dir = base / _APP_NAME
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


class CommandHistory:
    """Manages command history for the application."""

    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self.history: list[str] = []
        self.current_index = -1
        self._load_history()

    def add(self, command: str) -> None:
        """Add *command* to history (deduplicates consecutive identical entries)."""
        if command.strip() and (
            not self.history or command != self.history[-1]
        ):
            self.history.append(command)
            if len(self.history) > self.max_history:
                self.history.pop(0)
            self.current_index = len(self.history)
            self._save_history()

    def get_previous(self) -> Optional[str]:
        """Return the previous command from history."""
        if self.history:
            self.current_index = max(0, self.current_index - 1)
            return self.history[self.current_index]
        return None

    def get_next(self) -> Optional[str]:
        """Return the next command from history."""
        if self.history:
            self.current_index = min(
                len(self.history) - 1, self.current_index + 1
            )
            return self.history[self.current_index]
        return None

    def _load_history(self) -> None:
        """Load persisted history from the XDG data directory."""
        try:
            # FIX: use the shared XDG data-dir helper instead of importing
            # Config.DATA_DIR, which resolved to /data (unwritable) on Linux.
            history_file = _get_data_dir() / ".cli_history"
            if history_file.exists():
                lines = history_file.read_text(encoding="utf-8").strip().split(
                    "\n"
                )
                self.history = [
                    line for line in lines if line.strip()
                ][-self.max_history :]
                self.current_index = len(self.history)
        except Exception:
            # History is non-critical; never let a failure here crash startup.
            pass

    def _save_history(self) -> None:
        """Persist history to the XDG data directory."""
        try:
            # FIX: same XDG data-dir fix as _load_history.
            history_file = _get_data_dir() / ".cli_history"
            history_file.write_text(
                "\n".join(self.history), encoding="utf-8"
            )
        except Exception:
            pass

    @property
    def all(self) -> list[str]:
        """Return a copy of the full history list."""
        return self.history.copy()


class CommandAutocomplete:
    """Provides tab-autocomplete for commands and shortcuts."""

    SHORTCUTS: dict[str, str] = {
        "h": "health",
        "b": "backup",
        "l": "logs",
        "f": "files",
        "s": "schedule",
        "c": "config",
        "cfg": "config",
        "q": "quit",
        "?": "help",
    }

    COMMANDS: list[str] = [
        "health",
        "backup",
        "logs",
        "files",
        "schedule",
        "config",
        "analyze",
        "organize",
        "status",
        "help",
        "quit",
        "exit",
    ]

    @classmethod
    def autocomplete_all(cls, partial: str) -> list[str]:
        """Return combined autocomplete suggestions for menus and full commands."""
        partial_lower = partial.lower().strip()
        if not partial_lower:
            return []

        matches: list[str] = []

        # Match digits for menu selection.
        if partial_lower.isdigit():
            matches.extend(
                o for o in ("0", "1", "2", "3", "4", "5", "6", "7")
                if o.startswith(partial_lower)
            )

        # Match shortcuts.
        matches.extend(s for s in cls.SHORTCUTS if s.startswith(partial_lower))

        # Match full commands.
        matches.extend(c for c in cls.COMMANDS if c.startswith(partial_lower))

        # Return deduplicated and sorted list.
        return sorted(set(matches))

    @classmethod
    def complete_path(cls, partial: str) -> list[str]:
        """Return path-completion suggestions."""
        try:
            if partial.startswith("~"):
                partial = str(Path(partial).expanduser())
            path = Path(partial)
            base = (
                path
                if path.exists() and path.is_dir()
                else path.parent if path.parent.exists()
                else Path.cwd()
            )
            suggestions: list[str] = []
            try:
                for item in base.iterdir():
                    if item.name.lower().startswith(Path(partial).name.lower()):
                        suggestions.append(str(item))
            except PermissionError:
                pass
            return sorted(suggestions)
        except Exception:
            return []


class JSONOutputFormatter:
    """Formats command output as JSON for scripting."""

    @staticmethod
    def format_health(cpu: float, ram: float, disk: float) -> str:
        return json.dumps(
            {
                "command": "health",
                "status": "success",
                "data": {
                    "cpu_percent": cpu,
                    "ram_percent": ram,
                    "disk_percent": disk,
                },
            },
            indent=2,
        )

    @staticmethod
    def format_status(status: str) -> str:
        return json.dumps(
            {
                "command": "status",
                "status": "success",
                "data": {"system_status": status},
            },
            indent=2,
        )

    @staticmethod
    def format_backup_list(backups: list[dict]) -> str:
        return json.dumps(
            {
                "command": "backup",
                "status": "success",
                "data": {"backups": backups},
            },
            indent=2,
        )

    @staticmethod
    def format_schedule_list(tasks: list[dict]) -> str:
        return json.dumps(
            {
                "command": "schedule",
                "status": "success",
                "data": {"tasks": tasks},
            },
            indent=2,
        )

    @staticmethod
    def format_error(command: str, error_msg: str) -> str:
        return json.dumps(
            {"command": command, "status": "error", "error": error_msg},
            indent=2,
        )


# ── Enhanced Input Handler with readline support ──────────────────────────────

_history = CommandHistory()


def setup_readline() -> None:
    """Configure readline for enhanced interactive input (no-op if unavailable)."""
    if not READLINE_AVAILABLE or _readline_module is None:
        return
    try:
        def completer(text: str, state: int) -> Optional[str]:
            options = CommandAutocomplete.autocomplete_all(text)
            return options[state] if state < len(options) else None

        _readline_module.set_completer(completer)

        # macOS ships a libedit-based readline with a different bind syntax.
        doc = getattr(_readline_module, "__doc__", "") or ""
        if "libedit" in doc.lower():
            _readline_module.parse_and_bind("bind ^I rl_complete")
        else:
            _readline_module.parse_and_bind("tab: complete")

    except Exception:
        pass


def read_input_with_history(prompt: str) -> str:
    """Read input, adding it to the in-process history."""
    try:
        user_input = input(prompt).strip()
        _history.add(user_input)
        return user_input
    except KeyboardInterrupt:
        raise
    except EOFError:
        return "q"


def get_command_history() -> list[str]:
    """Return the full command history."""
    return _history.all


def export_history(filepath: str) -> None:
    """Export command history to *filepath*."""
    try:
        Path(filepath).write_text("\n".join(_history.all), encoding="utf-8")
    except Exception as exc:
        raise RuntimeError(f"Failed to export history: {exc}") from exc


# ── Feature flag ───────────────────────────────────────────────────────────────

PHASE3_ENABLED = True  # Set to False to disable Phase 3 features
