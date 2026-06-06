"""
spinner.py — Animated terminal spinner for long-running operations.

Zero external dependencies.  Runs in a daemon thread so the caller's code
keeps executing while the spinner is displayed.

Usage (context manager — recommended):
    from system_manager_cli.ulits.spinner import Spinner

    with Spinner("Uploading to Google Drive"):
        provider.upload(path)

Usage (manual):
    sp = Spinner("Connecting…")
    sp.start()
    do_work()
    sp.stop(success=True)          # prints ✔
    sp.stop(success=False, msg="Network error")  # prints ✖

All output goes to sys.stdout.  A final newline is always written so the
next print() starts on a clean line.
"""

from __future__ import annotations

import itertools
import sys
import threading
import time
from typing import Any

from .theme import T, colorize

# Spinner frame sets — pick based on terminal capability
_FRAMES_FANCY  = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
_FRAMES_SIMPLE = ["|", "/", "-", "\\"]


def _choose_frames() -> list[str]:
    """Use braille spinners on capable terminals, ASCII on basic ones."""
    import os
    term = os.environ.get("TERM", "")
    if sys.platform == "win32" or term in ("dumb", ""):
        return _FRAMES_SIMPLE
    return _FRAMES_FANCY


class Spinner:
    """
    Thread-safe animated spinner.

    Args:
        message:   Text displayed next to the spinner frame.
        color:     ANSI code applied to the spinning frame (default cyan).
        interval:  Seconds between frame updates (default 0.08).
    """

    def __init__(
        self,
        message: str = "Working",
        color: str = T.PRIMARY,
        interval: float = 0.08,
    ) -> None:
        self.message  = message
        self.color    = color
        self.interval = interval
        self._frames  = _choose_frames()
        self._stop_ev = threading.Event()
        self._thread  = threading.Thread(target=self._spin, daemon=True)
        self._lock    = threading.Lock()

    # ── Public API ────────────────────────────────────────────────────

    def start(self) -> "Spinner":
        """Start the spinner thread."""
        self._thread.start()
        return self

    def stop(self, success: bool = True, msg: str = "") -> None:
        """
        Stop the spinner and print a final status line.

        Args:
            success: If True prints ✔, else ✖.
            msg:     Optional override message.  Uses self.message if empty.
        """
        self._stop_ev.set()
        self._thread.join()
        final_msg = msg or self.message
        if success:
            marker = colorize("✔", T.SUCCESS)
        else:
            marker = colorize("✖", T.ERROR)
        sys.stdout.write(f"\r  {marker}  {final_msg}{' ' * 6}\n")
        sys.stdout.flush()

    def update_message(self, new_message: str) -> None:
        """Change the message shown next to the spinner while running."""
        with self._lock:
            self.message = new_message

    # ── Context manager ───────────────────────────────────────────────

    def __enter__(self) -> "Spinner":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop(success=(exc_type is None))

    # ── Internal ──────────────────────────────────────────────────────

    def _spin(self) -> None:
        for frame in itertools.cycle(self._frames):
            if self._stop_ev.is_set():
                break
            with self._lock:
                msg = self.message
            colored_frame = f"{self.color}{frame}{T.RESET}"
            line = f"\r  {colored_frame}  {msg}   "
            sys.stdout.write(line)
            sys.stdout.flush()
            time.sleep(self.interval)
        # Blank the spinner line so the final stop() message is clean
        sys.stdout.write("\r" + " " * 72 + "\r")
        sys.stdout.flush()


# ── Convenience wrapper ───────────────────────────────────────────────────────

def spin(message: str, func: Any, *args: Any, **kwargs: Any) -> Any:
    """
    Run *func* with the spinner active.  Returns func's return value.

    Example:
        result = spin("Fetching data", requests.get, url)
    """
    sp = Spinner(message)
    sp.start()
    try:
        return func(*args, **kwargs)
    finally:
        sp.stop(success=True)