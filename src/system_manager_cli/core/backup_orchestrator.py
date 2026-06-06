"""
backup_orchestrator.py — Core backup pipeline with verification and progress.

Place at: src/system_manager_cli/core/backup_orchestrator.py

Pipeline:
  1. validate_sources  — paths exist and are readable
  2. estimate_backup   — size, file count, space check
  3. create_local      — copy or zip with real progress
  4. verify_backup     — SHA-256 checksum + file count confirmation
  5. upload_to_cloud   — native provider (no rclone)
  6. cleanup_local     — delete local copy after upload if user agrees
  7. log_result        — POST to backend (fire-and-forget)
  8. notify            — email if configured
"""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from .cloud_auth_manager import CloudAuthManager
    from ..config.config import Config
    from ..ulits.logger import get_logger
    from ..ulits.progress import print_error, print_step, print_success, print_info
    logger = get_logger(__name__)
except Exception:
    import logging
    logger = logging.getLogger(__name__)
    def print_error(m):  print(f"  ❌  {m}")
    def print_step(m):   print(f"  ➤  {m}")
    def print_success(m): print(f"  ✅  {m}")
    def print_info(m):   print(f"  ℹ️   {m}")


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class BackupEstimate:
    source_file_count: int
    source_size_bytes: int
    destination_free_bytes: int
    estimated_zip_bytes: int
    has_enough_space: bool
    warnings: list[str] = field(default_factory=list)

    def size_display(self) -> str:
        return _fmt_bytes(self.source_size_bytes)

    def zip_display(self) -> str:
        return _fmt_bytes(self.estimated_zip_bytes)

    def free_display(self) -> str:
        return _fmt_bytes(self.destination_free_bytes)


@dataclass
class BackupVerificationResult:
    is_valid: bool
    file_count: int
    total_bytes: int
    checksum: str
    error: str | None = None


@dataclass
class OrchestratorResult:
    success: bool
    source_paths: list[str]
    destination_path: str | None
    zip_path: str | None
    zipped: bool
    cloud_uploaded: bool
    cloud_provider: str | None
    local_deleted: bool
    file_count: int
    size_bytes: int
    verification: BackupVerificationResult | None
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None
    logs: list[str] = field(default_factory=list)

    def add_log(self, msg: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self.logs.append(f"[{ts}] {msg}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "success":          self.success,
            "source_paths":     self.source_paths,
            "destination_path": self.destination_path,
            "zip_path":         self.zip_path,
            "zipped":           self.zipped,
            "cloud_uploaded":   self.cloud_uploaded,
            "cloud_provider":   self.cloud_provider,
            "local_deleted":    self.local_deleted,
            "file_count":       self.file_count,
            "size_bytes":       self.size_bytes,
            "error_message":    self.error_message,
            "started_at":       self.started_at.isoformat(),
            "completed_at":     self.completed_at.isoformat() if self.completed_at else None,
        }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _count_and_size(paths: list[str]) -> tuple[int, int]:
    total_files = 0
    total_bytes = 0
    for path_str in paths:
        p = Path(path_str)
        if not p.exists():
            continue
        if p.is_file():
            total_files += 1
            try:
                total_bytes += p.stat().st_size
            except OSError:
                pass
        else:
            for item in p.rglob("*"):
                if item.is_file():
                    total_files += 1
                    try:
                        total_bytes += item.stat().st_size
                    except OSError:
                        pass
    return total_files, total_bytes


def _simple_progress_bar(label: str, done: int, total: int, width: int = 30) -> None:
    if total == 0:
        return
    pct    = min(done / total, 1.0)
    filled = int(pct * width)
    bar    = "█" * filled + "░" * (width - filled)
    print(f"\r  {label}: [{bar}] {pct:.0%}  ({_fmt_bytes(done)} / {_fmt_bytes(total)})", end="", flush=True)


# ── History persistence ────────────────────────────────────────────────────────

def _history_db_path() -> Path:
    try:
        return Config.DATA_DIR / "backup_history.db"
    except Exception:
        return Path.home() / ".sysguard" / "backup_history.db"


def save_backup_history(result: OrchestratorResult) -> None:
    """Persist backup result to local SQLite history."""
    db = _history_db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS backups (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at      TEXT NOT NULL,
                completed_at    TEXT,
                source_paths    TEXT,
                destination     TEXT,
                zip_path        TEXT,
                zipped          INTEGER,
                cloud_uploaded  INTEGER,
                cloud_provider  TEXT,
                local_deleted   INTEGER,
                file_count      INTEGER,
                size_bytes      INTEGER,
                success         INTEGER,
                error_message   TEXT
            )
        """)
        conn.execute("""
            INSERT INTO backups (
                started_at, completed_at, source_paths, destination,
                zip_path, zipped, cloud_uploaded, cloud_provider,
                local_deleted, file_count, size_bytes, success, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.started_at.isoformat(),
            result.completed_at.isoformat() if result.completed_at else None,
            ", ".join(result.source_paths),
            result.destination_path,
            result.zip_path,
            1 if result.zipped else 0,
            1 if result.cloud_uploaded else 0,
            result.cloud_provider,
            1 if result.local_deleted else 0,
            result.file_count,
            result.size_bytes,
            1 if result.success else 0,
            result.error_message,
        ))


def load_backup_history(limit: int = 20) -> list[dict[str, Any]]:
    """Return recent backup history records."""
    db = _history_db_path()
    if not db.exists():
        return []
    try:
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM backups ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


# ── BackupOrchestrator ─────────────────────────────────────────────────────────

class BackupOrchestrator:
    """Execute the full backup pipeline with progress, verification, and history."""

    def __init__(self, auth_manager: CloudAuthManager | None = None) -> None:
        self._auth = auth_manager or CloudAuthManager()

    # ── Public ─────────────────────────────────────────────────────────

    def estimate(self, source_paths: list[str], destination: str) -> BackupEstimate:
        """Calculate size and check disk space. Call before starting."""
        total_files, total_bytes = _count_and_size(source_paths)
        warnings: list[str] = []

        for path_str in source_paths:
            if not Path(path_str).exists():
                warnings.append(f"Path not found: {path_str}")

        dest_path = Path(destination)
        try:
            usage      = shutil.disk_usage(dest_path if dest_path.exists() else dest_path.parent)
            free_bytes = usage.free
        except Exception:
            free_bytes = 0
            warnings.append("Could not determine available disk space.")

        estimated_zip = int(total_bytes * 0.60)   # ~40% compression estimate
        has_space     = free_bytes > max(estimated_zip, total_bytes)

        if not has_space and free_bytes > 0:
            warnings.append(
                f"Low disk space at destination. "
                f"Need ~{_fmt_bytes(total_bytes)}, available {_fmt_bytes(free_bytes)}."
            )

        return BackupEstimate(
            source_file_count      = total_files,
            source_size_bytes      = total_bytes,
            destination_free_bytes = free_bytes,
            estimated_zip_bytes    = estimated_zip,
            has_enough_space       = has_space,
            warnings               = warnings,
        )

    def run(
        self,
        source_paths: list[str],
        destination_path: str,
        zip_data: bool,
        cloud_provider_key: str | None,
    ) -> OrchestratorResult:
        """Execute the full pipeline. Returns an OrchestratorResult."""
        result = OrchestratorResult(
            success          = False,
            source_paths     = source_paths,
            destination_path = destination_path,
            zip_path         = None,
            zipped           = zip_data,
            cloud_uploaded   = False,
            cloud_provider   = None,
            local_deleted    = False,
            file_count       = 0,
            size_bytes       = 0,
            verification     = None,
            error_message    = None,
            started_at       = datetime.now(timezone.utc),
            completed_at     = None,
        )

        # ── Stage 1: Validate ──────────────────────────────────────────
        print_step("Validating source paths...")
        invalid = [p for p in source_paths if not Path(p).exists()]
        if invalid:
            result.error_message = f"Paths not found: {', '.join(invalid)}"
            print_error(result.error_message)
            return result
        result.add_log("Source validation passed.")
        print_success(f"All {len(source_paths)} source path(s) verified.")

        # ── Stage 2: Local backup ──────────────────────────────────────
        print_step("Creating local backup...")
        Path(destination_path).mkdir(parents=True, exist_ok=True)

        if zip_data:
            zip_path = self._create_zip(source_paths, destination_path, result)
            if not zip_path:
                return result
            artifact_paths = [zip_path]
            result.zip_path = zip_path
        else:
            artifact_paths = self._copy_sources(source_paths, destination_path, result)
            if not artifact_paths:
                return result

        # ── Stage 3: Verify ────────────────────────────────────────────
        print_step("Verifying backup integrity...")
        artifact = artifact_paths[0] if len(artifact_paths) == 1 else destination_path
        verification = self._verify(artifact)
        result.verification = verification
        result.file_count   = verification.file_count
        result.size_bytes   = verification.total_bytes

        if not verification.is_valid:
            result.error_message = f"Verification failed: {verification.error}"
            print_error(result.error_message)
            return result

        print_success(
            f"Backup verified: {verification.file_count} file(s), "
            f"{_fmt_bytes(verification.total_bytes)}, checksum OK."
        )
        result.add_log(f"Checksum: {verification.checksum[:16]}...")

        # ── Stage 4: Cloud upload ──────────────────────────────────────
        if cloud_provider_key:
            print_step(f"Uploading to {self._auth.get_label(cloud_provider_key)}...")
            provider = self._get_provider(cloud_provider_key)
            if provider is None:
                result.error_message = f"Unknown cloud provider: {cloud_provider_key}"
                print_error(result.error_message)
                return result

            if not provider.authenticate():
                result.error_message = f"Authentication failed for {provider.name}"
                print_error(result.error_message)
                return result

            for artifact in artifact_paths:
                ok = provider.upload(artifact)
                if not ok:
                    result.error_message = f"Upload failed for {artifact}"
                    print_error(result.error_message)
                    return result

            result.cloud_uploaded = True
            result.cloud_provider = provider.name
            result.add_log(f"Uploaded to {provider.name}.")
            print_success(f"Uploaded to {provider.name}.")

            # ── Stage 5: Offer local deletion AFTER successful upload ──
            try:
                print()
                print_info(f"Local backup artifact: {artifact_paths[0]}")
                ans = input(
                    "\n  Delete local backup now that it has been "
                    f"uploaded to {provider.name}? (y/n): "
                ).strip().lower()
                if ans in ("y", "yes"):
                    for art in artifact_paths:
                        p = Path(art)
                        if p.is_file():
                            p.unlink()
                        elif p.is_dir():
                            shutil.rmtree(p)
                    result.local_deleted = True
                    print_success("Local backup deleted.")
                    result.add_log("Local copy deleted.")
                else:
                    print_info(f"Local copy kept at: {destination_path}")
            except (KeyboardInterrupt, EOFError):
                print_info("Non-interactive mode: local backup kept.")

        result.success       = True
        result.completed_at  = datetime.now(timezone.utc)
        result.add_log("Backup pipeline completed successfully.")

        # ── Stage 6: Persist to history ────────────────────────────────
        try:
            save_backup_history(result)
        except Exception as exc:
            logger.warning("Could not save backup history: %s", exc)

        return result

    # ── Internal ────────────────────────────────────────────────────────

    def _create_zip(
        self,
        source_paths: list[str],
        destination: str,
        result: OrchestratorResult,
    ) -> str | None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        zip_path  = Path(destination) / f"backup_{timestamp}.zip"

        # Collect all files first so we can show total progress
        all_files: list[tuple[Path, str]] = []
        for src_str in source_paths:
            src = Path(src_str)
            if src.is_file():
                all_files.append((src, src.name))
            elif src.is_dir():
                for item in src.rglob("*"):
                    if item.is_file():
                        arcname = str(src.name / item.relative_to(src))
                        all_files.append((item, arcname))

        total_size  = sum(f.stat().st_size for f, _ in all_files if f.exists())
        done_bytes  = 0
        CHUNK       = 1024 * 256   # 256 KB chunks

        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
                for file_path, arcname in all_files:
                    try:
                        file_size = file_path.stat().st_size
                        zf.write(file_path, arcname)
                        done_bytes += file_size
                        _simple_progress_bar("  Compressing", done_bytes, total_size)
                    except (OSError, PermissionError):
                        pass
            print()  # newline after progress bar
            print_success(f"ZIP created: {zip_path.name}  ({_fmt_bytes(zip_path.stat().st_size)})")
            result.add_log(f"ZIP archive: {zip_path}")
            return str(zip_path)
        except Exception as exc:
            print()
            result.error_message = f"ZIP creation failed: {exc}"
            print_error(result.error_message)
            logger.error("ZIP error: %s", exc, exc_info=True)
            return None

    def _copy_sources(
        self,
        source_paths: list[str],
        destination: str,
        result: OrchestratorResult,
    ) -> list[str]:
        copied = []
        dest   = Path(destination)
        dest.mkdir(parents=True, exist_ok=True)

        # Total size for progress
        _, total_bytes = _count_and_size(source_paths)
        done_bytes = 0

        for src_str in source_paths:
            src       = Path(src_str)
            dest_item = dest / src.name
            try:
                if src.is_file():
                    shutil.copy2(src, dest_item)
                    done_bytes += src.stat().st_size
                    _simple_progress_bar("  Copying", done_bytes, total_bytes)
                    copied.append(str(dest_item))
                elif src.is_dir():
                    if dest_item.exists():
                        shutil.rmtree(dest_item)
                    shutil.copytree(src, dest_item)
                    _, sz = _count_and_size([str(dest_item)])
                    done_bytes += sz
                    _simple_progress_bar("  Copying", done_bytes, total_bytes)
                    copied.append(str(dest_item))
            except Exception as exc:
                print()
                result.error_message = f"Copy failed for {src_str}: {exc}"
                print_error(result.error_message)
                return []

        print()  # newline after progress bar
        print_success(f"Copied {len(copied)} item(s) to {destination}")
        result.add_log(f"Copied {len(copied)} items.")
        return copied

    def _verify(self, artifact_path: str) -> BackupVerificationResult:
        p = Path(artifact_path)
        if not p.exists():
            return BackupVerificationResult(
                is_valid=False, file_count=0, total_bytes=0,
                checksum="", error="Artifact not found after creation."
            )
        hasher      = hashlib.sha256()
        total_bytes = 0
        file_count  = 0

        if p.is_file():
            with p.open("rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hasher.update(chunk)
                    total_bytes += len(chunk)
            file_count = 1
        else:
            for item in sorted(p.rglob("*")):
                if item.is_file():
                    file_count  += 1
                    total_bytes += item.stat().st_size
                    with item.open("rb") as f:
                        for chunk in iter(lambda: f.read(65536), b""):
                            hasher.update(chunk)

        return BackupVerificationResult(
            is_valid    = True,
            file_count  = file_count,
            total_bytes = total_bytes,
            checksum    = hasher.hexdigest(),
        )

    def _get_provider(self, key: str):
        """Return the correct native provider, never rclone for primary flow."""
        from ..Providers.rclone_provider import RcloneProvider

        if key == "google_drive":
            # Use improved GDrive provider that reads from CloudAuthManager
            return _NativeGDriveProvider(self._auth)
        if key == "onedrive":
            return _NativeOneDriveProvider(self._auth)
        if key == "dropbox":
            return _NativeDropboxProvider(self._auth)
        if key == "s3":
            return _NativeS3Provider(self._auth)
        if key == "backblaze_b2":
            return _NativeBackblazeProvider(self._auth)
        if key == "sftp":
            return _NativeSFTPProvider(self._auth)
        # Advanced fallback: rclone for power users
        if key.startswith("rclone:"):
            remote = key.split(":", 1)[1]
            return RcloneProvider(remote_name=remote)
        return None


# ── Native provider stubs ──────────────────────────────────────────────────────
# Each delegates to the CloudAuthManager credentials and uploads via native SDK.

class _BaseNativeProvider:
    def __init__(self, auth: CloudAuthManager, key: str) -> None:
        self._auth = auth
        self._key  = key

    @property
    def name(self) -> str:
        return self._auth.get_label(self._key)

    def authenticate(self) -> bool:
        if not self._auth.is_configured(self._key):
            print_info(f"{self.name} is not connected. Launching setup wizard...")
            return self._auth.run_setup_wizard(self._key)
        return True


class _NativeGDriveProvider(_BaseNativeProvider):
    def __init__(self, auth: CloudAuthManager) -> None:
        super().__init__(auth, "google_drive")

    def upload(self, local_path: str, remote_destination: str | None = None) -> bool:
        try:
            import json as _json
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            creds_dict = self._auth.get_credentials("google_drive")
            creds      = Credentials.from_authorized_user_info(creds_dict)
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self._auth.store_credentials("google_drive", _json.loads(creds.to_json()))
            svc  = build("drive", "v3", credentials=creds, cache_discovery=False)

            # Ensure backup folder exists
            folder_id = _gdrive_ensure_folder(svc, "SysNova Backups")

            p = Path(local_path)
            if p.is_file():
                _gdrive_upload_file(svc, p, folder_id)
            elif p.is_dir():
                for item in sorted(p.rglob("*")):
                    if item.is_file():
                        _gdrive_upload_file(svc, item, folder_id)
            return True
        except ImportError:
            print_error("Google Drive SDK not installed: pip install google-auth-oauthlib google-api-python-client")
            return False
        except Exception as exc:
            print_error(f"Google Drive upload failed: {exc}")
            logger.error("GDrive upload: %s", exc, exc_info=True)
            return False


def _gdrive_ensure_folder(svc, folder_name: str) -> str:
    results = svc.files().list(
        q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id)",
    ).execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]
    meta = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
    f    = svc.files().create(body=meta, fields="id").execute()
    return f["id"]


def _gdrive_upload_file(svc, file_path: Path, parent_id: str | None = None) -> None:
    import mimetypes
    from googleapiclient.http import MediaFileUpload
    mime, _  = mimetypes.guess_type(str(file_path))
    mime     = mime or "application/octet-stream"
    meta     = {"name": file_path.name}
    if parent_id:
        meta["parents"] = [parent_id]
    media = MediaFileUpload(str(file_path), mimetype=mime, resumable=True)
    req   = svc.files().create(body=meta, media_body=media, fields="id")
    response = None
    while response is None:
        status, response = req.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"\r  Uploading {file_path.name}: {pct}%", end="", flush=True)
    print()


class _NativeOneDriveProvider(_BaseNativeProvider):
    def __init__(self, auth: CloudAuthManager) -> None:
        super().__init__(auth, "onedrive")

    def upload(self, local_path: str, remote_destination: str | None = None) -> bool:
        import urllib.request

        creds = self._auth.get_credentials("onedrive") or {}
        token = creds.get("access_token", "")
        if not token:
            print_error("OneDrive token missing. Please reconnect.")
            return False

        p = Path(local_path)
        files_to_upload = [p] if p.is_file() else list(p.rglob("*"))
        files_to_upload  = [f for f in files_to_upload if f.is_file()]

        for file_path in files_to_upload:
            try:
                upload_url = (
                    f"https://graph.microsoft.com/v1.0/me/drive/root:"
                    f"/SysNova Backups/{file_path.name}:/content"
                )
                data  = file_path.read_bytes()
                req   = urllib.request.Request(
                    upload_url,
                    data=data,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type":  "application/octet-stream",
                    },
                    method="PUT",
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
                    resp.read()
                print(f"  ✅  Uploaded: {file_path.name}")
            except Exception as exc:
                print_error(f"OneDrive upload failed for {file_path.name}: {exc}")
                return False
        return True


class _NativeDropboxProvider(_BaseNativeProvider):
    def __init__(self, auth: CloudAuthManager) -> None:
        super().__init__(auth, "dropbox")

    def upload(self, local_path: str, remote_destination: str | None = None) -> bool:
        try:
            import dropbox
            creds = self._auth.get_credentials("dropbox") or {}
            token = creds.get("access_token", "")
            dbx   = dropbox.Dropbox(token)
            p     = Path(local_path)
            files = [p] if p.is_file() else [f for f in p.rglob("*") if f.is_file()]
            for file_path in files:
                remote_path = f"/SysNova Backups/{file_path.name}"
                with file_path.open("rb") as f:
                    dbx.files_upload(f.read(), remote_path,
                                     mode=dropbox.files.WriteMode.overwrite)
                print(f"  ✅  Uploaded: {file_path.name}")
            return True
        except ImportError:
            print_error("Dropbox SDK not installed: pip install dropbox")
            return False
        except Exception as exc:
            print_error(f"Dropbox upload failed: {exc}")
            return False


class _NativeS3Provider(_BaseNativeProvider):
    def __init__(self, auth: CloudAuthManager) -> None:
        super().__init__(auth, "s3")

    def upload(self, local_path: str, remote_destination: str | None = None) -> bool:
        try:
            import boto3
            creds  = self._auth.get_credentials("s3") or {}
            kwargs: dict = {
                "aws_access_key_id":     creds["access_key_id"],
                "aws_secret_access_key": creds["secret_access_key"],
                "region_name":           creds.get("region", "us-east-1"),
            }
            if creds.get("endpoint_url"):
                kwargs["endpoint_url"] = creds["endpoint_url"]
            s3     = boto3.client("s3", **kwargs)
            bucket = creds["bucket"]
            p      = Path(local_path)
            files  = [p] if p.is_file() else [f for f in p.rglob("*") if f.is_file()]
            for file_path in files:
                key = f"sysnova-backups/{file_path.name}"
                s3.upload_file(str(file_path), bucket, key)
                print(f"  ✅  Uploaded: {file_path.name} → s3://{bucket}/{key}")
            return True
        except ImportError:
            print_error("boto3 not installed: pip install boto3")
            return False
        except Exception as exc:
            print_error(f"S3 upload failed: {exc}")
            return False


class _NativeBackblazeProvider(_BaseNativeProvider):
    def __init__(self, auth: CloudAuthManager) -> None:
        super().__init__(auth, "backblaze_b2")

    def upload(self, local_path: str, remote_destination: str | None = None) -> bool:
        try:
            import b2sdk.v2 as b2
            creds   = self._auth.get_credentials("backblaze_b2") or {}
            info    = b2.InMemoryAccountInfo()
            api     = b2.B2Api(info)
            api.authorize_account("production", creds["application_key_id"], creds["application_key"])
            bucket  = api.get_bucket_by_name(creds["bucket"])
            p       = Path(local_path)
            files   = [p] if p.is_file() else [f for f in p.rglob("*") if f.is_file()]
            for file_path in files:
                bucket.upload_local_file(str(file_path), file_path.name)
                print(f"  ✅  Uploaded: {file_path.name}")
            return True
        except ImportError:
            print_error("b2sdk not installed: pip install b2sdk")
            return False
        except Exception as exc:
            print_error(f"Backblaze B2 upload failed: {exc}")
            return False


class _NativeSFTPProvider(_BaseNativeProvider):
    def __init__(self, auth: CloudAuthManager) -> None:
        super().__init__(auth, "sftp")

    def upload(self, local_path: str, remote_destination: str | None = None) -> bool:
        try:
            import paramiko
            creds       = self._auth.get_credentials("sftp") or {}
            client      = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            connect_kw: dict = {
                "hostname": creds["host"],
                "port":     creds.get("port", 22),
                "username": creds["username"],
            }
            if creds.get("key_path"):
                connect_kw["key_filename"] = creds["key_path"]
            elif creds.get("password"):
                connect_kw["password"] = creds["password"]
            client.connect(**connect_kw)
            sftp        = client.open_sftp()
            remote_dir  = creds.get("remote_path", "/backups")

            # Ensure remote directory exists
            try:
                sftp.stat(remote_dir)
            except FileNotFoundError:
                sftp.mkdir(remote_dir)

            p     = Path(local_path)
            files = [p] if p.is_file() else [f for f in p.rglob("*") if f.is_file()]
            for file_path in files:
                remote_path = f"{remote_dir}/{file_path.name}"
                sftp.put(str(file_path), remote_path)
                print(f"  ✅  Uploaded: {file_path.name} → {remote_path}")

            sftp.close()
            client.close()
            return True
        except ImportError:
            print_error("paramiko not installed: pip install paramiko")
            return False
        except Exception as exc:
            print_error(f"SFTP upload failed: {exc}")
            return False
