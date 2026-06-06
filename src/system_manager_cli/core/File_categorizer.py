"""File Categorizer — Smart file organization with temp-file deletion.

Organizes files in a user-chosen folder into category sub-folders
(Documents, Images, Videos, Audio, Archives, Code, etc.) and handles
temporary/junk files by either deleting them or quarantining them.

Safe rules:
- Only processes TOP-LEVEL files (never recurses into sub-folders).
- Never touches the category output folders themselves on re-runs.
- On name collision, appends _1, _2 … rather than overwriting.
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .Exception import FileOrganizationError

# ──────────────────────────────────────────────────────────────────────────────
# Category → extension map
# ──────────────────────────────────────────────────────────────────────────────

CATEGORIES: dict[str, set[str]] = {
    "Documents": {
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".odt", ".ods", ".odp", ".txt", ".rtf", ".csv", ".md",
        ".epub", ".pages", ".numbers", ".key",
    },
    "Images": {
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp",
        ".tiff", ".tif", ".ico", ".heic", ".heif", ".raw",
        ".cr2", ".nef", ".arw",
    },
    "Code": {  # ← Moved UP so Code takes priority over Videos for .ts files
        ".py", ".js", ".ts", ".html", ".htm", ".css", ".java",
        ".c", ".cpp", ".cxx", ".h", ".hpp", ".cs", ".go", ".rs", ".rb",
        ".php", ".swift", ".kt", ".sh", ".bat", ".ps1", ".json",
        ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg",
        ".sql", ".r", ".lua", ".pl", ".env",
    },
    "Videos": {
        ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm",
        ".m4v", ".3gp", ".mpeg", ".mpg", ".vob",  # ".ts" removed - now Code
    },
    "Audio": {
        ".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma",
        ".m4a", ".aiff", ".opus",
    },
    "Archives": {
        ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2",
        ".xz", ".iso", ".dmg", ".cab",
    },
    "Executables": {
        ".exe", ".msi", ".apk", ".app", ".deb", ".rpm",
    },
    "Fonts": {
        ".ttf", ".otf", ".woff", ".woff2", ".eot",
    },
    "Data": {
        ".db", ".sqlite", ".sqlite3", ".parquet",
        ".pkl", ".pickle", ".h5", ".hdf5",
    },
}

# ──────────────────────────────────────────────────────────────────────────────
# Temporary / junk file detection
# ──────────────────────────────────────────────────────────────────────────────

DOTFILE_CATEGORIES: dict[str, str] = {
    ".env":           "Code",
    ".gitignore":     "Code",
    ".gitattributes": "Code",
    ".editorconfig":  "Code",
    ".dockerignore":  "Code",
    ".htaccess":      "Code",
    ".bashrc":        "Code",
    ".zshrc":         "Code",
    ".profile":       "Code",
}

TEMP_EXTENSIONS: set[str] = {
    ".tmp", ".temp", ".bak", ".old", ".orig",
    ".swp", ".swo", ".cache",
}

TEMP_NAME_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^~\$"),                        # MS Office lock files
    re.compile(r"^\.~lock\."),                  # LibreOffice lock files
    re.compile(r"thumbs\.db$", re.IGNORECASE),  # Windows thumbnail cache
    re.compile(r"desktop\.ini$", re.IGNORECASE),
    re.compile(r"^Thumbs\.db$"),
    re.compile(r"\.DS_Store$"),                 # macOS metadata
]

# Folders we never touch so re-runs are safe
_OWN_FOLDERS: set[str] = {
    *CATEGORIES.keys(),
    "Uncategorized",
    "_TempFiles",
}


class FileCategorizer:
    """Categorize files in a directory and optionally clean temp files."""

    def __init__(self, delete_temp_permanently: bool = False):
        self.delete_temp_permanently = delete_temp_permanently

    # ── Public ────────────────────────────────────────────────────────

    def organize(self, folder_path: str) -> dict[str, Any]:
        """
        Walk top-level files in *folder_path*, sort them into
        category sub-folders, and handle temp files.

        Returns a summary dict ready for display.
        """
        root = Path(folder_path).expanduser().resolve()
        if not root.exists():
            raise FileOrganizationError(f"Folder does not exist: {folder_path}")
        if not root.is_dir():
            raise FileOrganizationError(f"Path is not a folder: {folder_path}")

        counts:     dict[str, int] = {}
        temp_count: int            = 0
        skipped:    list[str]      = []

        for item in sorted(root.iterdir()):
            # Skip our own output folders and sub-directories first
            if item.name in _OWN_FOLDERS:
                continue
            if item.is_dir():
                continue
            if not item.is_file():
                continue

            try:
                # Check temp patterns BEFORE the hidden-file guard
                if self._is_temp(item):
                    self._handle_temp(item, root)
                    temp_count += 1
                    continue

                # Skip hidden files that are not temp and not categorisable
                # (but allow dotfile code configs like .env)
                category = self._get_category(item)
                if item.name.startswith(".") and category == "Uncategorized":
                    continue

                dest_dir = root / category
                dest_dir.mkdir(exist_ok=True)
                dest = self._safe_dest(dest_dir, item.name)
                shutil.move(str(item), str(dest))
                counts[category] = counts.get(category, 0) + 1

            except Exception as exc:
                skipped.append(f"{item.name}: {exc}")

        return {
            "status":             "success",
            "folder":             str(root),
            "category_counts":    counts,
            "temp_files_handled": temp_count,
            "temp_action":        (
                "deleted permanently"
                if self.delete_temp_permanently
                else "moved to _TempFiles folder"
            ),
            "skipped":            skipped,
            "timestamp":          datetime.now(timezone.utc).isoformat(),
        }

    # ── Private helpers ───────────────────────────────────────────────

    @staticmethod
    def _is_temp(path: Path) -> bool:
        if path.suffix.lower() in TEMP_EXTENSIONS:
            return True
        for pattern in TEMP_NAME_PATTERNS:
            if pattern.search(path.name):
                return True
        return False

    @staticmethod
    def _get_category(path: Path) -> str:
        # Extension-less dotfiles (e.g. .env)
        if not path.suffix and path.name.startswith("."):
            return DOTFILE_CATEGORIES.get(path.name.lower(), "Uncategorized")
        ext = path.suffix.lower()
        for category, extensions in CATEGORIES.items():
            if ext in extensions:
                return category
        return "Uncategorized"

    def _handle_temp(self, path: Path, root: Path) -> None:
        if self.delete_temp_permanently:
            path.unlink(missing_ok=True)
        else:
            quarantine = root / "_TempFiles"
            quarantine.mkdir(exist_ok=True)
            shutil.move(str(path), str(self._safe_dest(quarantine, path.name)))

    @staticmethod
    def _safe_dest(dest_dir: Path, filename: str) -> Path:
        dest = dest_dir / filename
        if not dest.exists():
            return dest
        stem    = Path(filename).stem
        ext     = Path(filename).suffix
        counter = 1
        while dest.exists():
            dest = dest_dir / f"{stem}_{counter}{ext}"
            counter += 1
        return dest