"""
smart_input.py — Smart prompt with command history and Tab completion.

Wraps Python's readline (Unix) / pyreadline3 (Windows) to give every
input() call:
  • ↑ / ↓ arrow keys for command history
  • Tab autocomplete for registered commands / paths
  • Graceful no-op fallback when readline is unavailable

Usage:
    from system_manager_cli.ulits.smart_input import SmartInput

    si = SmartInput()
    si.register_commands(["health", "backup", "analyze", "exit"])

    value = si.prompt("Select command")   # shows "> " prefix
    value = si.prompt("Path", completions=["/var/log", "/tmp"])
"""

from __future__ import annotations

from typing import Callable, Sequence

from .theme import T, colorize


# ── readline availability ─────────────────────────────────────────────────────

def _try_import_readline() -> object | None:
    """Import readline or pyreadline3; return the module or None."""
    try:
        import readline as _rl
        return _rl
    except ImportError:
        pass
    try:
        import pyreadline3 as _rl  # type: ignore
        return _rl
    except ImportError:
        pass
    return None


_RL = _try_import_readline()


# ─────────────────────────────────────────────────────────────────────────────
# SmartInput
# ─────────────────────────────────────────────────────────────────────────────

class SmartInput:
    """
    Enhanced input handler with history and completion.

    Args:
        history_size:  Maximum number of history entries (default 100).
        commands:      Initial list of autocomplete candidates.
    """

    # Default commands known to the app
    DEFAULT_COMMANDS: list[str] = [
        "health", "analyze", "backup", "organize",
        "schedule", "settings", "status", "login",
        "logout", "exit", "quit", "help",
        "1", "2", "3", "4", "5", "6", "7", "0",
        "y", "n", "yes", "no",
    ]

    def __init__(
        self,
        history_size: int = 100,
        commands: Sequence[str] | None = None,
    ) -> None:
        self._history:  list[str] = []
        self._commands: list[str] = list(commands or self.DEFAULT_COMMANDS)
        self._history_size = history_size
        self._completions:  list[str] = []

        if _RL:
            _RL.set_history_length(history_size)
            _RL.set_completer(self._completer)
            try:
                _RL.parse_and_bind("tab: complete")
            except Exception:
                pass

    # ── Public API ────────────────────────────────────────────────────

    def register_commands(self, commands: Sequence[str]) -> None:
        """Add extra words to the autocomplete list."""
        for cmd in commands:
            if cmd not in self._commands:
                self._commands.append(cmd)

    def prompt(
        self,
        message: str = "",
        symbol: str = "> ",
        completions: Sequence[str] | None = None,
        validator: Callable[[str], bool] | None = None,
        strip: bool = True,
        is_sensitive: bool = False,
    ) -> str:
        """
        Display a styled prompt and return the user's input.

        Args:
            message:       Text shown before the prompt symbol.
            symbol:        The prompt symbol (default "> ").
            completions:   Optional list of tab-complete candidates for this
                           specific prompt (merged with global commands).
            validator:     Optional callable(value) → bool.  Loops until True.
            strip:         Strip leading/trailing whitespace (default True).
            is_sensitive:  If True, do NOT add this input to history or readline.
                           Use this for passwords, API keys, tokens, PII, etc.
                           (default False).

        Returns:
            The user's input string.
        """
        self._completions = list(completions or []) + self._commands

        prompt_str = ""
        if message:
            prompt_str = f"\n  {colorize(message, T.DIM)}  "
        prompt_str += colorize(symbol, T.PRIMARY)

        while True:
            try:
                raw = input(prompt_str)
            except (EOFError, KeyboardInterrupt):
                print()
                return "exit"

            value = raw.strip() if strip else raw

            # FIX #12: Record in history ONLY if NOT sensitive data
            # Prevents passwords, API keys, tokens, etc. from being written to
            # ~/.python_history or readline history on disk.
            if value and not is_sensitive:
                self._history.append(value)
                if len(self._history) > self._history_size:
                    self._history = self._history[-self._history_size :]
                if _RL:
                    try:
                        _RL.add_history(value)
                    except Exception:
                        pass

            if validator is None or validator(value):
                return value

    def ask(
        self,
        question: str,
        choices: Sequence[str] = ("y", "n"),
        default: str = "",
    ) -> str:
        """
        Yes/no (or custom choice) prompt.

        Returns:
            The matched choice (lowercase).  Falls back to *default* on
            empty input if provided.
        """
        choices_lower = [c.lower() for c in choices]
        hint = "/".join(
            c.upper() if c == default else c for c in choices
        )
        while True:
            value = self.prompt(f"{question} ({hint})")
            low   = value.lower()
            if not low and default:
                return default.lower()
            if low in choices_lower:
                return low
            print(f"  {colorize('Please enter one of: ' + ', '.join(choices), T.WARNING)}")

    def get_history(self) -> list[str]:
        """Return a copy of the in-memory history list."""
        return list(self._history)

    # ── Tab completion callback ────────────────────────────────────────

    def _completer(self, text: str, state: int) -> str | None:
        """readline completer called with (text, state)."""
        candidates = [c for c in self._completions if c.startswith(text)]
        if state < len(candidates):
            return candidates[state]
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton for convenience
# ─────────────────────────────────────────────────────────────────────────────

_default = SmartInput()


def smart_prompt(
    message: str = "",
    symbol: str = "> ",
    completions: Sequence[str] | None = None,
    is_sensitive: bool = False,
) -> str:
    """
    Convenience function using the module-level SmartInput singleton.

    Args:
        message:       Prompt message.
        symbol:        Prompt symbol (default "> ").
        completions:   Tab-completion candidates.
        is_sensitive:  If True, don't add to history (use for passwords, keys, etc.)

    Example:
        from system_manager_cli.ulits.smart_input import smart_prompt
        choice = smart_prompt("Select option")
        password = smart_prompt("Enter password", is_sensitive=True)
    """
    return _default.prompt(
        message,
        symbol=symbol,
        completions=completions,
        is_sensitive=is_sensitive,
    )