from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class RcloneRemote:
    storage_name: str   # e.g. "Google Drive", "Dropbox"
    remote_name: str    # e.g. "mydrive", "mybox"

    def display(self) -> str:
        return f"  Cloud Storage: {self.storage_name} | Remote Name: {self.remote_name}"


@dataclass
class BackupConfig:
    last_destination_path: Optional[str] = None
    rclone_remotes: List[RcloneRemote] = field(default_factory=list)
    email: Optional[str] = None

    def find_remote(self, name: str) -> Optional[RcloneRemote]:
        """Find a remote by storage name or remote name (case-insensitive)."""
        name_lower = name.lower()
        for remote in self.rclone_remotes:
            if (remote.remote_name.lower() == name_lower or
                    remote.storage_name.lower() == name_lower):
                return remote
        return None

    def add_remote(self, storage_name: str, remote_name: str):
        """Add or update a remote."""
        existing = self.find_remote(remote_name)
        if existing:
            existing.storage_name = storage_name
        else:
            self.rclone_remotes.append(RcloneRemote(storage_name=storage_name,
                                                      remote_name=remote_name))

    def list_remotes_display(self) -> str:
        if not self.rclone_remotes:
            return "  (No remotes configured)"
        lines = []
        for i, r in enumerate(self.rclone_remotes, 1):
            lines.append(f"  {i}. {r.display()}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "last_destination_path": self.last_destination_path,
            "email": self.email,
            "rclone_remotes": [
                {"storage_name": r.storage_name, "remote_name": r.remote_name}
                for r in self.rclone_remotes
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BackupConfig":
        remotes = [
            RcloneRemote(storage_name=r["storage_name"], remote_name=r["remote_name"])
            for r in data.get("rclone_remotes", [])
        ]
        return cls(
            last_destination_path=data.get("last_destination_path"),
            email=data.get("email"),
            rclone_remotes=remotes,
        )
