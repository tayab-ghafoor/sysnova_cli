"""
Production-grade Auto Updater

Full update lifecycle:
  1. Check remote manifest for a newer version.
  2. Download the release zip with SHA-256 verification.
  3. Stage the extracted files as a *pending update* (written to disk).
  4. On the NEXT startup, apply the pending update atomically before any
     app code is imported, then restart.
  5. On failure: rollback to the most recent backup automatically.

Works for both PyInstaller frozen executables (.exe) and plain Python
source installations.

Windows note
------------
A running .exe cannot be deleted or overwritten by itself on Windows.
We therefore rename the current .exe to <name>.exe.old (which is allowed
because we are only renaming, not writing), copy the new .exe into place,
then schedule the .old file for deletion on the next OS boot via
MoveFileExW(MOVEFILE_DELAY_UNTIL_REBOOT).  The restart that follows loads
the freshly written executable.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import sys
import threading
import time
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

import requests

from .version_manager import VersionManager
from .config import UPDATE_CONFIG

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Runtime helpers
# ---------------------------------------------------------------------------

def _is_frozen() -> bool:
    """True when running as a PyInstaller-frozen executable."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def _get_installation_root() -> Path:
    """
    Frozen  → directory that contains the .exe
    Source  → parent of the 'system_manager_cli' package directory
    """
    if _is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _get_user_data_root() -> Path:
    """
    Get the platform-appropriate user data directory (writable, not in Program Files).
    
    Windows  -> %LOCALAPPDATA%\\SysNova
    macOS    -> ~/Library/Application Support/SysNova
    Linux    -> ~/.config/sysnova or $XDG_CONFIG_HOME/sysnova
    """
    if sys.platform == "win32":
        # Windows: use LOCALAPPDATA (C:\\Users\\<user>\\AppData\\Local)
        base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return (base / "SysNova").resolve()
    elif sys.platform == "darwin":
        # macOS: use ~/Library/Application Support
        return (Path.home() / "Library" / "Application Support" / "SysNova").resolve()
    else:
        # Linux and others: use XDG_CONFIG_HOME or ~/.config
        base = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
        return (base / "sysnova").resolve()


# ---------------------------------------------------------------------------
# AutoUpdater
# ---------------------------------------------------------------------------

class AutoUpdater:
    """
    Orchestrates download → staging → pending-update → apply → restart.
    """

    def __init__(
        self,
        install_path: Optional[Path] = None,
        state_path:   Optional[Path] = None,
        update_url:   Optional[str]  = None,
    ) -> None:
        """
        Args:
            install_path: Root directory of the installed application.
                          Auto-detected if not provided.
            state_path:   Directory for backups, logs, pending update files.
                          Defaults to platform-specific user data directory (.updater subdirectory).
            update_url:   URL of the remote update manifest.
                          Falls back to ``UPDATE_CONFIG['version_url']``.
        """
        self.is_frozen = _is_frozen()
        self.install_path = (
            Path(install_path).resolve()
            if install_path is not None
            else _get_installation_root().resolve()
        )
        self.state_path = (
            Path(state_path).resolve()
            if state_path is not None
            else (_get_user_data_root() / ".updater").resolve()
        )
        self.update_url = update_url or UPDATE_CONFIG["version_url"]

        # Sub-directories inside state_path
        self.backup_path        = self.state_path / "backups"
        self.temp_update_path   = self.state_path / "temp_update"
        self.logs_path          = self.state_path / "logs"
        self.update_log_path    = self.logs_path  / "update.log"
        self.pending_update_file = self.state_path / "pending_update.json"
        self.startup_success_file = self.state_path / ".startup_success"

        # Create required directories with proper error handling
        try:
            for d in (self.state_path, self.backup_path, self.temp_update_path, self.logs_path):
                d.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as e:
            raise RuntimeError(
                f"Failed to create updater directories at {self.state_path}: {e}. "
                f"Check that {self.state_path.parent} is writable."
            ) from e

        self.update_in_progress = False
        self._setup_logging()

        # VersionManager stores version.json inside state_path
        self.version_manager = VersionManager(self.state_path, self.update_url)

        self.update_logger.info("AutoUpdater initialised")
        self.update_logger.info("  install_path : %s", self.install_path)
        self.update_logger.info("  state_path   : %s", self.state_path)
        self.update_logger.info("  frozen       : %s", self.is_frozen)

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _setup_logging(self) -> None:
        ul = logging.getLogger("updater")
        ul.setLevel(logging.DEBUG)
        # Remove stale handlers (important when AutoUpdater is reinstantiated)
        for h in ul.handlers[:]:
            ul.removeHandler(h)
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        fh  = logging.FileHandler(self.update_log_path, encoding="utf-8")
        fh.setFormatter(fmt)
        ul.addHandler(fh)
        if os.environ.get("UPDATE_LOG_TO_CONSOLE", "").lower() in ("1", "true"):
            ch = logging.StreamHandler()
            ch.setFormatter(fmt)
            ul.addHandler(ch)
        self.update_logger = ul

    # ------------------------------------------------------------------
    # Background polling
    # ------------------------------------------------------------------

    def start_background_updater(self) -> None:
        """Start a daemon thread that polls for updates at the configured interval."""
        if not UPDATE_CONFIG.get("auto_update_enabled", False):
            self.update_logger.info("Auto-update disabled – background thread not started")
            return

        def _worker() -> None:
            interval = UPDATE_CONFIG.get("check_interval_hours", 24) * 3600
            self.update_logger.info("Background updater started (interval: %ds)", interval)
            while True:
                time.sleep(interval)
                try:
                    available, _ = self.check_for_updates()
                    if available and not self.update_in_progress:
                        self.update_logger.info("Background: update found – staging now")
                        self.update(
                            progress_callback=lambda m: self.update_logger.info("BG: %s", m)
                        )
                except Exception as exc:
                    self.update_logger.error("Background worker error: %s", exc)

        t = threading.Thread(target=_worker, daemon=True, name="AutoUpdateWorker")
        t.start()

    # ------------------------------------------------------------------
    # Update check
    # ------------------------------------------------------------------

    def check_for_updates(self) -> Tuple[bool, Optional[Dict[str, str]]]:
        self.update_logger.info("Checking for updates at %s …", self.update_url)
        try:
            available, info = self.version_manager.check_for_updates()
            if available and info is not None:
                self.update_logger.info("Remote version: %s", info.get("version"))
            else:
                self.update_logger.info("No update available")
            return available, info
        except Exception as exc:
            self.update_logger.error("Update check failed: %s", exc)
            return False, None

    def get_version(self) -> str:
        return self.version_manager.get_current_version()

    # ------------------------------------------------------------------
    # Main update orchestration  (STAGE ONLY – apply happens at startup)
    # ------------------------------------------------------------------

    def update(
        self,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """
        Download and stage the latest release.

        Does NOT swap files immediately.  Instead it writes a
        ``pending_update.json`` file.  The swap happens the next time
        ``apply_pending_update()`` is called at startup.

        Returns True if staging succeeded.
        """
        if self.update_in_progress:
            self.update_logger.warning("Update already in progress – skipping")
            return False

        self.update_in_progress = True
        try:
            available, remote_info = self.check_for_updates()
            if not available or not remote_info:
                self._cb(progress_callback, "No update available")
                return False

            version = remote_info["version"]
            self._cb(progress_callback, f"Update found: v{version} – downloading …")
            self.update_logger.info("Starting update to v%s", version)

            # Clean the temp directory for this run
            shutil.rmtree(self.temp_update_path, ignore_errors=True)
            self.temp_update_path.mkdir(parents=True, exist_ok=True)

            zip_path    = self.temp_update_path / "update.zip"
            extract_dir = self.temp_update_path / "extracted"

            if not self._download_update(remote_info, zip_path, progress_callback):
                self.update_logger.error("Download failed – aborting")
                return False

            self._cb(progress_callback, "Verifying and extracting …")
            if not self._extract_and_verify(remote_info, zip_path, extract_dir):
                self.update_logger.error("Extraction/verification failed – aborting")
                return False

            # Remove the zip now that we have the extracted content
            zip_path.unlink(missing_ok=True)

            self._create_pending_update(remote_info, extract_dir)
            self._cb(progress_callback, "Update staged – will be applied on next restart")
            self.update_logger.info("Staging complete for v%s", version)
            return True

        except Exception as exc:
            self.update_logger.error("Update failed unexpectedly: %s", exc, exc_info=True)
            return False
        finally:
            self.update_in_progress = False

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def _download_update(
        self,
        info: Dict,
        zip_path: Path,
        callback: Optional[Callable],
    ) -> bool:
        url = info.get("download_url", "")
        if not url:
            self.update_logger.error("No download_url in remote_info")
            return False

        expected_checksum = info.get("package_checksum", "")
        timeout = UPDATE_CONFIG.get("download_timeout", 60)

        for attempt in range(1, 4):
            try:
                self._cb(callback, f"Downloading … (attempt {attempt}/3)")
                self.update_logger.info("Downloading from %s", url)

                with requests.get(url, stream=True, timeout=timeout, verify=True) as resp:
                    resp.raise_for_status()
                    total    = int(resp.headers.get("content-length", 0))
                    received = 0
                    with open(zip_path, "wb") as fh:
                        for chunk in resp.iter_content(chunk_size=65536):
                            if chunk:
                                fh.write(chunk)
                                received += len(chunk)
                                if total and callback:
                                    pct = int(received * 100 / total)
                                    callback(f"  Downloading … {pct}%")

                # Verify checksum immediately after download
                if expected_checksum:
                    self._cb(callback, "Verifying checksum …")
                    if not self._verify_checksum(zip_path, expected_checksum):
                        self.update_logger.warning(
                            "Checksum mismatch on attempt %d", attempt
                        )
                        zip_path.unlink(missing_ok=True)
                        if attempt < 3:
                            time.sleep(2)
                            continue
                        return False

                self.update_logger.info("Download OK (%d bytes)", received)
                return True

            except requests.exceptions.RequestException as exc:
                self.update_logger.warning("Download error attempt %d: %s", attempt, exc)
                zip_path.unlink(missing_ok=True)
                if attempt < 3:
                    time.sleep(3)

        return False

    # ------------------------------------------------------------------
    # Extraction & manifest validation
    # ------------------------------------------------------------------

    def _extract_and_verify(
        self,
        info: Dict,
        zip_path: Path,
        extract_dir: Path,
    ) -> bool:
        try:
            extract_dir.mkdir(parents=True, exist_ok=True)
            resolved_extract = extract_dir.resolve()

            with zipfile.ZipFile(zip_path, "r") as zf:
                # Zip-Slip protection: every member must stay inside extract_dir
                for member in zf.namelist():
                    target = (extract_dir / member).resolve()
                    if not str(target).startswith(str(resolved_extract)):
                        self.update_logger.error(
                            "Zip-Slip attempt blocked: %s", member
                        )
                        return False
                    zf.extract(member, extract_dir)

            # Optional manifest.json inside the zip
            manifest_file = extract_dir / "manifest.json"
            if manifest_file.exists():
                with open(manifest_file, "r", encoding="utf-8") as fh:
                    manifest = json.load(fh)
                for required_file in manifest.get("required_files", []):
                    if not (extract_dir / required_file).exists():
                        self.update_logger.error(
                            "Required file missing after extraction: %s", required_file
                        )
                        return False

            self.update_logger.info("Extraction OK into %s", extract_dir)
            return True

        except zipfile.BadZipFile as exc:
            self.update_logger.error("Bad zip file: %s", exc)
            return False
        except Exception as exc:
            self.update_logger.error("Extraction failed: %s", exc, exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Pending-update mechanism
    # ------------------------------------------------------------------

    def _create_pending_update(self, remote_info: Dict, extracted_dir: Path) -> None:
        pending = {
            "version":        remote_info["version"],
            "extracted_path": str(extracted_dir.resolve()),
            "timestamp":      time.time(),
            "platform":       self._detect_platform_key(),
        }
        with open(self.pending_update_file, "w", encoding="utf-8") as fh:
            json.dump(pending, fh, indent=2)
        self.update_logger.info(
            "Pending update written: v%s → %s",
            pending["version"], self.pending_update_file,
        )

    def apply_pending_update(self) -> bool:
        """
        Call this AT STARTUP, before importing any application code.

        Reads pending_update.json, creates a backup, swaps the files, updates
        version.json, then cleans up.  Returns True if an update was applied
        (caller should restart the process immediately).
        """
        if not self.pending_update_file.exists():
            return False

        try:
            with open(self.pending_update_file, "r", encoding="utf-8") as fh:
                pending = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            self.update_logger.error("Could not read pending_update.json: %s", exc)
            self.pending_update_file.unlink(missing_ok=True)
            return False

        version       = pending.get("version", "unknown")
        extracted_dir = Path(pending.get("extracted_path", ""))

        self.update_logger.info("Applying pending update to v%s …", version)

        if not extracted_dir.exists():
            self.update_logger.error(
                "Extracted directory gone (%s) – removing stale pending marker", extracted_dir
            )
            self.pending_update_file.unlink(missing_ok=True)
            return False

        # 1. Create backup of current installation
        backup_dir = self._create_backup()
        if backup_dir is None:
            self.update_logger.error("Backup failed – aborting update")
            return False

        # 2. Perform the atomic swap
        if not self._swap_installation(extracted_dir):
            self.update_logger.error("Swap failed – rolling back …")
            self._restore_backup(backup_dir)
            return False

        # 3. Persist the new version
        self.version_manager.update_version_info({
            "version":    version,
            "build_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        })

        # 4. Cleanup
        self.pending_update_file.unlink(missing_ok=True)
        shutil.rmtree(extracted_dir.parent, ignore_errors=True)
        self._cleanup_old_backups(UPDATE_CONFIG.get("backup_count", 3))

        self.update_logger.info("Successfully updated to v%s", version)
        return True

    # ------------------------------------------------------------------
    # Backup
    # ------------------------------------------------------------------

    def _create_backup(self) -> Optional[Path]:
        """Snapshot the current installation; return the backup directory."""
        try:
            ts         = int(time.time())
            backup_dir = self.backup_path / f"backup_{ts}"

            if self.is_frozen:
                exe_path = Path(sys.executable).resolve()
                backup_dir.mkdir(parents=True)
                shutil.copy2(exe_path, backup_dir / exe_path.name)
                self.update_logger.info("Backup of exe created: %s", backup_dir)
            else:
                pkg_dir = self.install_path / "system_manager_cli"
                if not pkg_dir.exists():
                    self.update_logger.error("Package dir not found: %s", pkg_dir)
                    return None
                shutil.copytree(pkg_dir, backup_dir)
                self.update_logger.info("Backup of package created: %s", backup_dir)

            return backup_dir

        except Exception as exc:
            self.update_logger.error("Backup creation failed: %s", exc, exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Atomic file swap  (the heart of the updater)
    # ------------------------------------------------------------------

    def _swap_installation(self, new_version_dir: Path) -> bool:
        """
        Replace the live application files with those from *new_version_dir*.

        Frozen (Windows .exe)
        ─────────────────────
        1. Rename  app.exe  →  app.exe.old   (rename is allowed on a running exe)
        2. Copy    new.exe  →  app.exe        (copy into the now-free slot)
        3. Schedule  app.exe.old  for deletion on next reboot (MoveFileExW).

        Source installation
        ───────────────────
        1. Rename  system_manager_cli  →  system_manager_cli.old.<ts>
        2. Move    new/system_manager_cli  →  system_manager_cli
        3. Delete  system_manager_cli.old.<ts>  in a background thread.
        """
        try:
            if self.is_frozen:
                return self._swap_frozen(new_version_dir)
            else:
                return self._swap_source(new_version_dir)
        except Exception as exc:
            self.update_logger.error("_swap_installation error: %s", exc, exc_info=True)
            return False

    def _swap_frozen(self, new_version_dir: Path) -> bool:
        """Replace the running .exe with the new one."""
        current_exe = Path(sys.executable).resolve()
        exe_name    = current_exe.name
        new_exe     = new_version_dir / exe_name

        # Fallback: look one level deeper (common zip layout)
        if not new_exe.exists():
            matches = list(new_version_dir.rglob(exe_name))
            if matches:
                new_exe = matches[0]

        if not new_exe.exists():
            self.update_logger.error(
                "New executable '%s' not found inside %s", exe_name, new_version_dir
            )
            return False

        old_exe = current_exe.with_suffix(".exe.old")

        self.update_logger.info("Renaming %s → %s", current_exe.name, old_exe.name)
        os.replace(current_exe, old_exe)           # rename – works on running exe

        self.update_logger.info("Copying new exe → %s", current_exe)
        shutil.copy2(new_exe, current_exe)         # write new content

        self._schedule_file_deletion(old_exe)      # clean up .old on reboot
        self.update_logger.info("Frozen swap complete")
        return True

    def _swap_source(self, new_version_dir: Path) -> bool:
        """Replace the source package directory atomically."""
        current_pkg = self.install_path / "system_manager_cli"
        new_pkg     = new_version_dir / "system_manager_cli"

        if not new_pkg.exists():
            self.update_logger.error(
                "New package dir not found: %s", new_pkg
            )
            return False

        temp_old = self.install_path / f"system_manager_cli.old.{int(time.time())}"

        self.update_logger.info("Renaming current package → %s", temp_old.name)
        os.replace(current_pkg, temp_old)   # atomic on POSIX, fast on Windows

        self.update_logger.info("Moving new package into place")
        os.replace(new_pkg, current_pkg)

        self._schedule_directory_deletion(temp_old)
        self.update_logger.info("Source swap complete")
        return True

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    def _restore_backup(self, backup_dir: Path) -> bool:
        try:
            if self.is_frozen:
                exe_name    = Path(sys.executable).name
                current_exe = Path(sys.executable).resolve()
                backup_exe  = backup_dir / exe_name
                if backup_exe.exists():
                    shutil.copy2(backup_exe, current_exe)
                    self.update_logger.info("Frozen rollback complete")
                    return True
            else:
                current_pkg = self.install_path / "system_manager_cli"
                if backup_dir.exists():
                    shutil.rmtree(current_pkg, ignore_errors=True)
                    shutil.copytree(backup_dir, current_pkg)
                    self.update_logger.info("Source rollback complete")
                    return True
            self.update_logger.error("Backup not found for rollback")
            return False
        except Exception as exc:
            self.update_logger.error("Rollback failed: %s", exc, exc_info=True)
            return False

    # ------------------------------------------------------------------
    # File deletion helpers (Windows .old exe cleanup)
    # ------------------------------------------------------------------

    def _schedule_file_deletion(self, file_path: Path) -> None:
        """
        On Windows: schedule deletion-on-reboot via MoveFileExW.
        On other platforms: unlink immediately.
        """
        try:
            if sys.platform == "win32":
                import ctypes
                # First rename to a .del extension so the slot is freed sooner
                del_path = file_path.with_suffix(".del")
                try:
                    os.replace(file_path, del_path)
                    file_path = del_path
                except OSError:
                    pass  # keep original name if rename fails
                # MOVEFILE_DELAY_UNTIL_REBOOT = 0x4
                ctypes.windll.kernel32.MoveFileExW(str(file_path), None, 0x00000004)
                self.update_logger.info(
                    "Scheduled %s for deletion on next reboot", file_path.name
                )
            else:
                file_path.unlink(missing_ok=True)
        except Exception as exc:
            self.update_logger.warning("Could not schedule deletion of %s: %s", file_path, exc)

    def _schedule_directory_deletion(self, dir_path: Path) -> None:
        """Delete a directory tree in a background thread with retries."""
        def _del() -> None:
            for attempt in range(6):
                try:
                    shutil.rmtree(dir_path, ignore_errors=False)
                    return
                except OSError:
                    time.sleep(2 ** attempt)
            self.update_logger.warning(
                "Could not remove old directory after retries: %s", dir_path
            )

        threading.Thread(target=_del, daemon=True, name="DirCleanup").start()

    # ------------------------------------------------------------------
    # Backup rotation
    # ------------------------------------------------------------------

    def _cleanup_old_backups(self, keep_count: int) -> None:
        try:
            backups = sorted(
                self.backup_path.glob("backup_*"),
                key=lambda p: p.stat().st_mtime,
            )
            for old in backups[:-keep_count]:
                shutil.rmtree(old, ignore_errors=True)
                self.update_logger.info("Removed old backup: %s", old.name)
        except Exception as exc:
            self.update_logger.warning("Backup cleanup error: %s", exc)

    # ------------------------------------------------------------------
    # Crash detection & rollback
    # ------------------------------------------------------------------

    def mark_startup_success(self) -> None:
        """
        Call this once the application has finished initialising successfully.
        The updater uses the absence / age of this file to detect crashes.
        """
        self.startup_success_file.write_text(str(time.time()), encoding="utf-8")

    def check_rollback_needed(self) -> bool:
        """
        If the last update appears to have caused a crash (startup success
        file is missing or stale), roll back to the most recent backup.

        Returns True if a rollback was performed.
        """
        if not self.startup_success_file.exists():
            # No file yet – first run after install, not a crash
            return False
        try:
            recorded_at = float(self.startup_success_file.read_text(encoding="utf-8"))
            # If the file is very recent, startup succeeded normally
            if time.time() - recorded_at < 300:
                return False
            # Stale file → crashed on last run
            self.update_logger.warning(
                "Startup-success file is stale – assuming crash; rolling back"
            )
            backups = sorted(
                self.backup_path.glob("backup_*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if backups and self._restore_backup(backups[0]):
                self.startup_success_file.unlink(missing_ok=True)
                return True
        except Exception as exc:
            self.update_logger.warning("Rollback check error: %s", exc)
        return False

    # ------------------------------------------------------------------
    # Application restart
    # ------------------------------------------------------------------

    def restart_application(self) -> None:
        """
        Replace the current process with a fresh copy of the application.
        On Windows with a frozen exe, os.execv is not available – we use
        subprocess.Popen instead and then exit.
        """
        self.update_logger.info("Restarting application …")
        try:
            if self.is_frozen:
                if sys.platform == "win32":
                    import subprocess
                    subprocess.Popen(
                        [sys.executable] + sys.argv[1:],
                        close_fds=True,
                    )
                    sys.exit(0)
                else:
                    os.execv(sys.executable, [sys.executable] + sys.argv[1:])
            else:
                main_script = Path(sys.argv[0]).resolve()
                if not main_script.exists():
                    main_script = Path(__file__).parent.parent / "main.py"
                if sys.platform == "win32":
                    import subprocess
                    subprocess.Popen(
                        [sys.executable, str(main_script)] + sys.argv[1:],
                        close_fds=True,
                    )
                    sys.exit(0)
                else:
                    os.execv(
                        sys.executable,
                        [sys.executable, str(main_script)] + sys.argv[1:],
                    )
        except Exception as exc:
            self.update_logger.error("Restart failed: %s", exc, exc_info=True)

    # ------------------------------------------------------------------
    # Status reporting
    # ------------------------------------------------------------------

    def get_update_status(self) -> Dict[str, Any]:
        return {
            "current_version":   self.get_version(),
            "update_in_progress": self.update_in_progress,
            "startup_success":   self.startup_success_file.exists(),
            "pending_update":    self.pending_update_file.exists(),
            "last_check":        getattr(self, "_last_check_time", "Never"),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cb(callback: Optional[Callable[[str], None]], message: str) -> None:
        if callback:
            try:
                callback(message)
            except Exception:
                pass

    @staticmethod
    def _detect_platform_key() -> str:
        import platform as _platform
        s = _platform.system().lower()
        return {"windows": "windows", "linux": "linux", "darwin": "macos"}.get(s, s)

    @staticmethod
    def _verify_checksum(path: Path, expected: str) -> bool:
        sha256 = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest().lower() == expected.lower()
