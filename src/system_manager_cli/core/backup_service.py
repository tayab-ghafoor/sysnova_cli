"""
backup_service.py — Main backup orchestration.

Coordinates all backup steps:
    1. Validate source paths
    2. Resolve destination path
    3. Zip (optional) OR copy files
    4. Cloud backup (optional)
       4a. Upload only the backed-up artifact
       4b. Ask user about deleting local copy AFTER successful upload
    5. Send summary email

Bug fixes vs original:
    - rclone/gdrive now uploads only the zip file (if zipped) or only the
      individual source items copied into destination (not the whole destination
      folder), so unrelated files in the destination are never touched.
    - The "delete local backup" question is now asked INSIDE this function,
      AFTER the upload has succeeded, not before the backup even starts.
"""

from __future__ import annotations

import os
import shutil
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

from ..models.backup_result import BackupResult
from ..models.config_model import BackupConfig
from .Validator import validate_paths, validate_single_path
from .Packager import create_zip, delete_backup_file
from ..Providers.gdrive_provider import GDriveProvider
from ..Providers.rclone_provider import RcloneProvider
from ..ulits.logger import get_logger
from ..ulits.progress import (
    print_step, print_success, print_error, print_info, print_warning,
)

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _ask_delete_local_interactively(artifact_path: str) -> bool:
    """
    Ask the user — interactively, AFTER a successful upload — whether to
    delete the local backup artifact.
    """
    print()
    print_info(f"Local backup artifact: {artifact_path}")
    while True:
        ans = input(
            "\n  Do you want to delete the local backup now that it has been "
            "uploaded to the cloud? (y/n): "
        ).strip().lower()
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print_error("Please enter 'y' or 'n'.")


def _copy_sources_to_destination(
    source_paths: List[str], destination_path: str
) -> tuple[bool, List[str]]:
    """
    Copy each source file/folder into destination_path.

    Returns:
        (success, copied_artifact_paths)
        copied_artifact_paths — the individual items placed inside destination_path,
        NOT the destination folder itself.  These are what rclone/gdrive should upload.
    """
    print_step("Copying files to destination…")
    logger.info("Copying sources to: %s", destination_path)

    try:
        os.makedirs(destination_path, exist_ok=True)
    except OSError as exc:
        print_error(f"Cannot create destination directory: {exc}")
        return False, []

    copied: List[str] = []

    for source in source_paths:
        source = os.path.abspath(source)
        dest   = os.path.join(destination_path, os.path.basename(source))

        try:
            if os.path.isfile(source):
                shutil.copy2(source, dest)
                copied.append(dest)
                logger.debug("  Copied file: %s → %s", source, dest)
            elif os.path.isdir(source):
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                shutil.copytree(source, dest)
                copied.append(dest)
                logger.debug("  Copied folder: %s → %s", source, dest)
            else:
                logger.warning("  Skipped (not found): %s", source)
                print_warning(f"Source not found, skipped: {source}")
        except Exception as exc:
            print_error(f"Failed to copy {source}: {exc}")
            logger.error("Copy failed for %s: %s", source, exc)
            return False, copied

    if not copied:
        print_error("No files were copied — check that source paths exist.")
        return False, []

    print_success("Files copied to destination successfully.")
    return True, copied


def _upload_artifacts(
    provider,
    artifacts: List[str],
    result: BackupResult,
) -> bool:
    """
    Upload each artifact path (file or folder) through the given provider.
    Includes retry logic and proper error handling.
    Returns True only if every upload succeeds.
    """
    max_retries = 3
    retry_delay = 2
    
    for artifact in artifacts:
        print_step(f"Uploading: {os.path.basename(artifact)}")
        logger.info(f"Starting upload of artifact: {artifact}")
        
        success = False
        for attempt in range(1, max_retries + 1):
            try:
                ok = provider.upload_with_progress(artifact)
                
                if ok:
                    print_success(f"Upload successful: {os.path.basename(artifact)}")
                    logger.info(f"Successfully uploaded: {artifact}")
                    success = True
                    break
                    
                elif attempt < max_retries:
                    print_warning(f"Upload failed, retrying ({attempt}/{max_retries})…")
                    logger.warning(f"Upload attempt {attempt} failed for {artifact}, retrying…")
                    time.sleep(retry_delay)
                    
            except Exception as exc:
                logger.error(f"Upload exception (attempt {attempt}/{max_retries}): {exc}")
                print_error(f"Upload error: {exc}")
                
                if attempt < max_retries:
                    print_warning(f"Retrying upload ({attempt}/{max_retries})…")
                    time.sleep(retry_delay)
                else:
                    print_error(f"Upload failed after {max_retries} attempts")
                    break
        
        if not success:
            print_error(f"Upload failed for: {artifact}")
            result.error_message = f"Cloud upload failed after {max_retries} attempts: {artifact}"
            logger.error(f"Final upload failure for {artifact}")
            return False
    
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Email notification
# ─────────────────────────────────────────────────────────────────────────────

def send_email_notification(result: BackupResult, config: BackupConfig) -> None:
    """Send a status email if an email address is configured."""
    if not config.email:
        return

    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")

    if not smtp_user or not smtp_pass:
        logger.warning("SMTP_USER / SMTP_PASS not set — skipping backup email.")
        return

    subject = "✅ Backup Completed" if result.success else "❌ Backup Failed"
    body    = result.summary()

    msg = MIMEMultipart()
    msg["From"]    = smtp_user
    msg["To"]      = config.email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        logger.info("Backup notification sent to %s", config.email)
    except Exception as exc:
        logger.error("Failed to send backup email: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Main orchestration
# ─────────────────────────────────────────────────────────────────────────────

def run_backup_flow(
    source_paths: List[str],
    destination_path: str,
    zip_data: bool,
    cloud_backup: bool,
    cloud_method: Optional[str],        # "gdrive" | "rclone" | None
    rclone_remote_name: Optional[str],
    rclone_storage_name: Optional[str],
    # NOTE: delete_local_after is intentionally removed from the signature.
    # The user is now asked interactively AFTER a successful upload inside
    # this function, so the menu no longer needs to collect it upfront.
    config: BackupConfig,
) -> BackupResult:
    """
    Execute the full backup workflow.
    Called by backup_menu.py after all user inputs have been collected.
    """
    result = BackupResult(
        success=False,
        source_paths=source_paths,
        destination_path=destination_path,
    )

    print_step("Backup system started")
    logger.info("=== Backup flow started ===")
    result.add_log("Backup flow started")

    # ── Step 1: Validate source paths ──────────────────────────────────────
    print_step("Checking source paths…")
    path_results, all_valid = validate_paths(", ".join(source_paths))
    for pr in path_results:
        if pr.exists:
            print_success(f"Path verified: {pr.path}")
        else:
            print_error(f"Path does not exist: {pr.path}")

    if not all_valid:
        result.error_message = "One or more source paths are invalid."
        logger.error("Source path validation failed.")
        return result

    # ── Step 2: Validate destination ───────────────────────────────────────
    dest_result = validate_single_path(destination_path)
    if not dest_result.exists:
        print_error(f"Destination path does not exist: {destination_path}")
        result.error_message = "Destination path is invalid."
        return result
    print_success(f"Destination verified: {destination_path}")

    # ── Step 3: Zip OR copy ────────────────────────────────────────────────
    # artifacts = the exact file(s)/folder(s) to upload (NOT the destination dir)
    artifacts: List[str] = []

    if zip_data:
        # ── Zip: one .zip file is the artifact ────────────────────────
        zip_path = create_zip(source_paths, destination_path)
        if not zip_path:
            result.error_message = "Zip creation failed."
            logger.error("create_zip() returned None.")
            return result
        result.zipped   = True
        result.zip_path = zip_path
        artifacts       = [zip_path]
        result.add_log(f"Zip created: {zip_path}")
    else:
        # ── Copy: each copied item is an artifact ─────────────────────
        # We track exactly which items were placed into destination_path
        # so we never upload the whole destination folder.
        ok, copied_items = _copy_sources_to_destination(source_paths, destination_path)
        if not ok:
            result.error_message = "File copy failed."
            return result
        artifacts = copied_items
        result.add_log(f"Copied {len(artifacts)} item(s) to {destination_path}")

    # ── Step 4: Local-only backup ──────────────────────────────────────────
    if not cloud_backup:
        result.success = True
        result.add_log("Local backup only — skipping cloud upload.")
        artifact_display = artifacts[0] if len(artifacts) == 1 else destination_path
        print_success("Local backup completed!")
        print_info(f"Backup stored at: {artifact_display}")
        send_email_notification(result, config)
        return result

    # ── Step 5: Select cloud provider ─────────────────────────────────────
    print_step("Preparing cloud upload…")
    provider = None

    if cloud_method == "gdrive":
        provider = GDriveProvider()
        result.cloud_provider = "Google Drive"

    elif cloud_method == "rclone":
        if not rclone_remote_name:
            print_error("No rclone remote name was provided.")
            result.error_message = "rclone remote not configured."
            return result
        provider = RcloneProvider(
            remote_name=rclone_remote_name,
            storage_name=rclone_storage_name or rclone_remote_name,
        )
        result.cloud_provider = f"Rclone ({rclone_storage_name or rclone_remote_name})"
        result.cloud_remote   = rclone_remote_name

    else:
        print_error("Unknown cloud method — cannot upload.")
        result.error_message = "Unknown cloud method."
        return result

    # ── Step 6: Authenticate ───────────────────────────────────────────────
    if not provider.authenticate():
        print_error("Cloud authentication failed.")
        result.error_message = "Cloud authentication failed."
        return result

    # ── Step 7: Upload only the backed-up artifacts ────────────────────────
    # artifacts is either [zip_file] or [copied_item1, copied_item2, ...]
    # In both cases it contains exactly what came from the user's source paths.
    upload_ok = _upload_artifacts(provider, artifacts, result)
    if not upload_ok:
        return result

    result.cloud_uploaded = True
    artifact_display = artifacts[0] if len(artifacts) == 1 else f"{len(artifacts)} items"
    print_success(f"Upload complete → {result.cloud_provider}")
    print_info(f"Uploaded: {artifact_display}")

    # ── Step 8: Ask about deleting local copy (AFTER successful upload) ────
    try:
        # Only the zip file is a "temporary" local artifact worth deleting;
        # if the user didn't zip, their files were just copied — we still ask
        # in case they want to clean up the copies.
        for artifact in artifacts:
            delete_local = _ask_delete_local_interactively(artifact)
            if delete_local:
                deleted = delete_backup_file(artifact)
                if deleted:
                    print_success(f"Local copy deleted: {os.path.basename(artifact)}")
                    result.local_backup_deleted = True
                else:
                    print_warning(
                        f"Could not delete local copy: {artifact}  "
                        "(check permissions)"
                    )
            else:
                print_info(f"Local copy kept at: {artifact}")
    except (KeyboardInterrupt, EOFError):
        # Non-interactive mode (scheduled tasks etc.) — keep local copy
        print_info("Non-interactive mode: local backup kept.")

    result.success = True
    result.add_log("Backup flow completed successfully.")
    logger.info("=== Backup flow completed ===")

    send_email_notification(result, config)
    return result