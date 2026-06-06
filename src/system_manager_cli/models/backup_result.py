from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


@dataclass
class PathValidationResult:
    path: str
    exists: bool
    error: Optional[str] = None

    def __str__(self):
        status = "✅ Verified" if self.exists else "❌ Invalid"
        return f"{status}: {self.path}"


@dataclass
class BackupResult:
    success: bool
    source_paths: List[str] = field(default_factory=list)
    destination_path: Optional[str] = None
    zip_path: Optional[str] = None
    zipped: bool = False
    cloud_uploaded: bool = False
    cloud_provider: Optional[str] = None
    cloud_remote: Optional[str] = None
    local_backup_deleted: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None
    log_messages: List[str] = field(default_factory=list)

    def add_log(self, message: str):
        self.log_messages.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def summary(self) -> str:
        lines = [
            "=" * 50,
            "       BACKUP SUMMARY",
            "=" * 50,
            f"Status        : {'SUCCESS ✅' if self.success else 'FAILED ❌'}",
            f"Source Paths  : {', '.join(self.source_paths)}",
            f"Destination   : {self.destination_path}",
            f"Zipped        : {'Yes' if self.zipped else 'No'}",
            f"Cloud Backup  : {'Yes' if self.cloud_uploaded else 'No'}",
        ]
        if self.cloud_uploaded:
            lines.append(f"Cloud Provider: {self.cloud_provider}")
            if self.cloud_remote:
                lines.append(f"Remote Name   : {self.cloud_remote}")
        lines.append(f"Local Deleted : {'Yes' if self.local_backup_deleted else 'No'}")
        lines.append(f"Time          : {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        if self.error_message:
            lines.append(f"Error         : {self.error_message}")
        lines.append("=" * 50)
        return "\n".join(lines)
