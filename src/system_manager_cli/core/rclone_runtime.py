"""Locate the rclone executable in source, installed, and frozen builds."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _binary_name() -> str:
    return "rclone.exe" if sys.platform == "win32" else "rclone"


def _candidate_paths() -> list[Path]:
    name = _binary_name()
    candidates: list[Path] = []

    env_path = os.getenv("RCLONE_BINARY", "").strip()
    if env_path:
        candidates.append(Path(env_path).expanduser())

    # PyInstaller one-file extracts bundled binaries under sys._MEIPASS.
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        root = Path(meipass)
        candidates.extend([
            root / "resources" / "bin" / name,
            root / "build" / "resources" / "bin" / name,
        ])

    executable_dir = Path(sys.executable).resolve().parent
    candidates.extend([
        executable_dir / "resources" / "bin" / name,
        executable_dir / "build" / "resources" / "bin" / name,
        Path.cwd() / "build" / "resources" / "bin" / name,
    ])

    return candidates


def find_rclone() -> str | None:
    """Return an executable rclone path, or None when unavailable."""
    for candidate in _candidate_paths():
        if candidate.is_file():
            return str(candidate)

    return shutil.which("rclone")


def rclone_command(*args: str) -> list[str]:
    """Build a subprocess command for rclone, raising if it is unavailable."""
    executable = find_rclone()
    if executable is None:
        raise FileNotFoundError(
            "rclone was not found. Install rclone or set RCLONE_BINARY to its full path."
        )
    return [executable, *args]
