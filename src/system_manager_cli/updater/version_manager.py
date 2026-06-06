"""
Version Manager for Automatic Software Updates

Handles local version storage, remote manifest fetching, version comparison,
and checksum verification.

Expected remote manifest format (https://systemmanagement.bela002.com/api/update.json):
{
    "latest_version": "1.2.0",
    "changelog_url":  "https://systemmanagement.bela002.com/changelog",
    "windows": {
        "url":    "https://systemmanagement.bela002.com/releases/app-1.2.0-win.zip",
        "sha256": "<hex digest>"
    },
    "linux": {
        "url":    "https://systemmanagement.bela002.com/releases/app-1.2.0-linux.zip",
        "sha256": "<hex digest>"
    },
    "macos": {
        "url":    "https://systemmanagement.bela002.com/releases/app-1.2.0-macos.zip",
        "sha256": "<hex digest>"
    }
}
"""

from __future__ import annotations

import hashlib
import json
import logging
import platform
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Network retry constants
# ---------------------------------------------------------------------------
MAX_RETRIES    = 3
RETRY_DELAY    = 1      # seconds before first retry
RETRY_BACKOFF  = 2      # exponential backoff multiplier
FETCH_TIMEOUT  = 15     # seconds for the manifest HTTP request


class VersionManager:
    """Manages version information and update availability checks."""

    def __init__(self, state_path: Path, update_url: str) -> None:
        self.state_path   = state_path
        self.update_url   = update_url
        self.version_file = state_path / "version.json"
        self.local_version: Dict[str, str] = self._load_local_version()

    # ------------------------------------------------------------------
    # Local version persistence
    # ------------------------------------------------------------------

    def _load_local_version(self) -> Dict[str, str]:
        """Load version.json from disk; initialise with 1.0.0 on first run."""
        if self.version_file.exists():
            try:
                with open(self.version_file, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if "version" not in data:
                    logger.warning("version.json missing 'version' field – reinitialising")
                    return self._create_default_version()
                return data
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to read version.json (%s) – reinitialising", exc)
                return self._create_default_version()

        logger.info("First run – initialising version.json with 1.0.0")
        return self._create_default_version()

    def _create_default_version(self) -> Dict[str, str]:
        """Write and return the default version record for a fresh install."""
        default: Dict[str, str] = {
            "version":    "1.0.0",
            "checksum":   "",
            "build_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "platform":   platform.system().lower(),
        }
        try:
            self.version_file.parent.mkdir(parents=True, exist_ok=True)
            self._atomic_write(self.version_file, default)
            logger.info("Initialised version file: %s", self.version_file)
        except OSError as exc:
            logger.error("Could not create version.json: %s", exc)
        return default

    def _save_local_version(self, info: Dict[str, str]) -> None:
        """Persist updated version info atomically."""
        info = dict(info)  # don't mutate caller's dict
        info["save_date"] = time.strftime("%Y-%m-%d %H:%M:%S")
        info["platform"]  = platform.system().lower()
        try:
            self.version_file.parent.mkdir(parents=True, exist_ok=True)
            self._atomic_write(self.version_file, info)
            self.local_version = info
            logger.info("Saved local version: %s", info.get("version"))
        except OSError as exc:
            logger.error("Failed to save version.json: %s", exc)
            raise

    @staticmethod
    def _atomic_write(dest: Path, data: dict) -> None:
        """Write *data* to *dest* atomically via a temp file + rename."""
        tmp = dest.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        tmp.replace(dest)

    # ------------------------------------------------------------------
    # Remote manifest fetching
    # ------------------------------------------------------------------

    def _detect_platform(self) -> str:
        """Return 'windows', 'linux', or 'macos'."""
        system = platform.system().lower()
        mapping = {"windows": "windows", "linux": "linux", "darwin": "macos"}
        key = mapping.get(system)
        if key is None:
            raise RuntimeError(f"Unsupported OS: {system}")
        return key

    def _build_headers(self) -> dict:
        """Build HTTP headers including optional auth."""
        # Import here to avoid circular imports at module load time
        from .config import UPDATE_AUTH

        headers = {
            "User-Agent": "sysnova-updater/1.0",
            "Accept":     "application/json",
        }
        if UPDATE_AUTH.get("api_key"):
            headers["Authorization"] = f"Bearer {UPDATE_AUTH['api_key']}"
        return headers

    def _build_auth(self) -> Optional[tuple]:
        from .config import UPDATE_AUTH
        u = UPDATE_AUTH.get("username")
        p = UPDATE_AUTH.get("password")
        return (u, p) if u and p else None

    def _fetch_update_manifest(self) -> Optional[Dict]:
        """
        GET the update manifest with exponential-backoff retries.

        Returns a normalised remote_info dict or None on failure.
        """
        headers    = self._build_headers()
        auth       = self._build_auth()
        last_error = ""

        for attempt in range(MAX_RETRIES):
            try:
                logger.debug("Fetching manifest (attempt %d/%d)", attempt + 1, MAX_RETRIES)
                resp = requests.get(
                    self.update_url,
                    headers=headers,
                    auth=auth,
                    timeout=FETCH_TIMEOUT,
                    verify=True,
                )
                resp.raise_for_status()
                data: dict = resp.json()

            # --- transient network errors → retry ---
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ) as exc:
                last_error = str(exc)
                logger.warning("Network error on attempt %d: %s", attempt + 1, exc)
                self._maybe_sleep(attempt)
                continue

            except requests.exceptions.HTTPError as exc:
                last_error = str(exc)
                logger.warning("HTTP error: %s", exc)
                # Retry on 5xx, abort on 4xx
                if resp.status_code >= 500:
                    self._maybe_sleep(attempt)
                    continue
                break

            except (json.JSONDecodeError, ValueError) as exc:
                logger.error("Could not parse manifest JSON: %s", exc)
                return None

            except Exception as exc:
                last_error = str(exc)
                logger.warning("Unexpected error on attempt %d: %s", attempt + 1, exc)
                self._maybe_sleep(attempt)
                continue

            # --- validate structure ---
            if "latest_version" not in data:
                logger.error("Manifest missing 'latest_version'")
                return None

            platform_key = self._detect_platform()
            platform_entry = data.get(platform_key)
            if not isinstance(platform_entry, dict):
                logger.error("Manifest missing platform section '%s'", platform_key)
                return None
            if "url" not in platform_entry:
                logger.error("Manifest platform '%s' missing 'url'", platform_key)
                return None

            remote_info = {
                "version":          data["latest_version"],
                "download_url":     platform_entry["url"],
                "package_checksum": platform_entry.get("sha256", ""),
                "changelog_url":    data.get("changelog_url", ""),
            }
            logger.info("Manifest OK – remote version: %s", remote_info["version"])
            return remote_info

        logger.error(
            "Manifest fetch failed after %d attempts. Last error: %s",
            MAX_RETRIES, last_error,
        )
        return None

    def _maybe_sleep(self, attempt: int) -> None:
        if attempt < MAX_RETRIES - 1:
            wait = RETRY_DELAY * (RETRY_BACKOFF ** attempt)
            logger.info("Retrying in %.1fs …", wait)
            time.sleep(wait)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_for_updates(self) -> Tuple[bool, Optional[Dict[str, str]]]:
        """
        Return (True, remote_info) if a newer version is available,
        (False, None) otherwise.
        """
        try:
            remote = self._fetch_update_manifest()
            if not remote:
                return False, None

            remote_ver = remote.get("version", "0.0.0")
            local_ver  = self.local_version.get("version", "0.0.0")

            if self._is_newer(remote_ver, local_ver):
                logger.info("Update available: %s → %s", local_ver, remote_ver)
                return True, remote

            logger.info("Up to date (%s)", local_ver)
            return False, None

        except Exception as exc:
            logger.warning("Update check error: %s", exc)
            return False, None

    def update_version_info(self, new_info: Dict[str, str]) -> None:
        """Persist new version info after a successful update."""
        self._save_local_version(new_info)

    def get_current_version(self) -> str:
        return self.local_version.get("version", "0.0.0")

    def verify_checksum(self, file_path: Path, expected: str) -> bool:
        """Return True if the SHA-256 of *file_path* matches *expected*."""
        if not expected:
            logger.warning("No checksum supplied – skipping verification")
            return True
        try:
            sha256 = hashlib.sha256()
            with open(file_path, "rb") as fh:
                for chunk in iter(lambda: fh.read(65536), b""):
                    sha256.update(chunk)
            ok = sha256.hexdigest().lower() == expected.lower()
            if not ok:
                logger.error("Checksum mismatch for %s", file_path)
            return ok
        except OSError as exc:
            logger.error("Checksum verification I/O error: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_newer(remote: str, local: str) -> bool:
        """Semantic version comparison: return True if remote > local."""
        def _parts(v: str):
            try:
                return [int(x) for x in v.split(".")]
            except ValueError:
                return [0]

        # Change this:
        # r, l = _parts(remote), _parts(local)
        # length = max(len(r), len(l))
        # r += [0] * (length - len(r))
        # l += [0] * (length - len(l))
        # return r > l

        # To this:
        rem, loc = _parts(remote), _parts(local)
        length = max(len(rem), len(loc))
        rem += [0] * (length - len(rem))
        loc += [0] * (length - len(loc))
        return rem > loc

    # Backward-compatible alias used by test_updater_system.py
    _is_newer_version = _is_newer
