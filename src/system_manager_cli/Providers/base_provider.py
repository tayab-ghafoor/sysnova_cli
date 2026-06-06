from abc import ABC, abstractmethod
from typing import Optional


class BackupProvider(ABC):
    """
    Abstract base class for all cloud backup providers.
    Every provider (Google Drive, rclone, etc.) must implement these methods.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name, e.g. 'Google Drive'."""
        ...

    @abstractmethod
    def authenticate(self) -> bool:
        """
        Perform any required authentication.
        Returns True if authenticated successfully, False otherwise.
        """
        ...

    @abstractmethod
    def upload(self, local_path: str, remote_destination: Optional[str] = None) -> bool:
        """
        Upload a local file or folder to the cloud storage.

        Args:
            local_path:          Absolute path to the local file/folder to upload.
            remote_destination:  Optional remote folder path where the file should go.

        Returns:
            True if upload succeeded, False otherwise.
        """
        ...

    def upload_with_progress(self, local_path: str, remote_destination: Optional[str] = None) -> bool:
        """
        Wrapper that shows simulated progress before delegating to upload().
        Override in subclasses if real progress reporting is available.
        """
        from system_manager_cli.ulits.progress import simulate_progress
        simulate_progress(label=f"Uploading to {self.name}")
        return self.upload(local_path, remote_destination)
