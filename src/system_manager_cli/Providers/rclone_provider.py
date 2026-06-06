"""
Rclone backup provider.

Delegates all cloud operations to the rclone CLI binary.
Supports every storage backend that rclone supports
(Google Drive, S3, Dropbox, OneDrive, Backblaze, SFTP, etc.)

Prerequisites:
    - rclone must be installed and available on PATH.
    - A remote must be configured: run `rclone config` in a terminal.
    - The remote name must be registered in backup_config.json via config_manager.
"""

import subprocess
from typing import Optional

from .base_provider import BackupProvider

# FIX: `logger` is not exported from logger.py — use get_logger instead
from system_manager_cli.core.rclone_runtime import find_rclone, rclone_command
from system_manager_cli.ulits.logger import get_logger
from system_manager_cli.ulits.progress import print_step, print_success, print_error

logger = get_logger(__name__)

# Upload timeout: 6 hours (long files on slow connections)
RCLONE_UPLOAD_TIMEOUT = 6 * 3600


class RcloneProvider(BackupProvider):

    def __init__(self, remote_name: str, storage_name: str = ""):
        """
        Args:
            remote_name:   The rclone remote identifier (e.g. "mydrive").
            storage_name:  Human-readable storage label (e.g. "Google Drive").
        """
        self.remote_name = remote_name
        self.storage_name = storage_name or remote_name

    @property
    def name(self) -> str:
        return f"Rclone ({self.storage_name})"

    def authenticate(self) -> bool:
        """
        Verify rclone is installed and the configured remote is accessible.
        """
        rclone = find_rclone()
        if not rclone:
            print_error(
                "rclone is not installed, bundled, or configured.\n"
                "  Install rclone or set RCLONE_BINARY to its full path."
            )
            logger.error("rclone binary not found.")
            return False

        # Check if the remote exists in rclone's own config
        result = subprocess.run(
            rclone_command("listremotes"),
            capture_output=True, text=True
        )
        configured_remotes = [r.rstrip(":") for r in result.stdout.strip().splitlines()]

        if self.remote_name not in configured_remotes:
            print_error(
                f"Remote '{self.remote_name}' is not configured in rclone.\n"
                f"  Run: rclone config   to add a new remote."
            )
            logger.error(f"rclone remote not found: {self.remote_name}")
            return False

        logger.info(f"rclone remote verified: {self.remote_name}")
        return True

    def upload(self, local_path: str, remote_destination: Optional[str] = None) -> bool:
        """
        Upload local_path to the configured rclone remote.

        Args:
            local_path:         Absolute path to local file or folder.
            remote_destination: Optional sub-path within the remote root.
                                 Defaults to remote root ("<remote_name>:").
        """
        if not self.authenticate():
            return False

        remote_target = f"{self.remote_name}:"
        if remote_destination:
            remote_target += remote_destination.lstrip("/")

        print_step(f"Uploading backup to cloud via rclone → {remote_target}")
        logger.info(f"rclone copy: {local_path} → {remote_target}")

        try:
            result = subprocess.run(
                rclone_command("copy", local_path, remote_target, "--progress"),
                text=True,
                timeout=RCLONE_UPLOAD_TIMEOUT,
            )

            if result.returncode == 0:
                print_success(f"Backup uploaded to {self.name} successfully.")
                logger.info(f"rclone upload complete: {local_path} → {remote_target}")
                return True
            else:
                print_error("Upload interrupted or failed.")
                logger.error(
                    f"rclone exited with code {result.returncode}. "
                    f"stderr: {result.stderr}"
                )
                return False

        except subprocess.TimeoutExpired:
            print_error(f"Upload timeout after {RCLONE_UPLOAD_TIMEOUT / 3600:.1f} hours.")
            logger.error(
                f"rclone upload timeout after {RCLONE_UPLOAD_TIMEOUT}s: {local_path} → {remote_target}"
            )
            return False
        except FileNotFoundError:
            print_error("rclone binary not found. Please install rclone.")
            logger.error("rclone binary missing during upload.")
            return False
        except Exception as e:
            print_error("Upload interrupted.")
            logger.error(f"Unexpected rclone error: {e}")
            return False
