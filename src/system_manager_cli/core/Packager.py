import os
import shutil
import zipfile
from datetime import datetime
from typing import List, Optional

# FIX: `logger` is not exported from logger.py — use get_logger instead
from system_manager_cli.ulits.logger import get_logger
from system_manager_cli.ulits.progress import print_step, print_success, print_error

logger = get_logger(__name__)


def create_zip(source_paths: List[str], destination_dir: str) -> Optional[str]:
    """
    Compress one or more files/folders into a single ZIP archive.

    The archive is saved inside destination_dir with a timestamped name:
        backup_YYYYMMDD_HHMMSS.zip

    Returns the full path to the created ZIP, or None on failure.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"backup_{timestamp}.zip"
    zip_path = os.path.join(destination_dir, zip_filename)

    print_step("Compressing data...")
    logger.info(f"Creating zip archive: {zip_path}")

    try:
        os.makedirs(destination_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for source in source_paths:
                source = os.path.abspath(source)
                if os.path.isfile(source):
                    arcname = os.path.basename(source)
                    zf.write(source, arcname=arcname)
                    logger.debug(f"  Added file: {source}")
                elif os.path.isdir(source):
                    base = os.path.basename(source)
                    for root, dirs, files in os.walk(source):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.join(
                                base,
                                os.path.relpath(file_path, start=source)
                            )
                            zf.write(file_path, arcname=arcname)
                    logger.debug(f"  Added folder: {source}")
                else:
                    logger.warning(f"  Skipped (not found): {source}")

        print_success(f"Zip created successfully: {zip_filename}")
        logger.info(f"Zip archive created: {zip_path}")
        return zip_path

    except PermissionError as e:
        print_error("Zip creation failed — permission denied.")
        logger.error(f"Permission denied during zip: {e}")
        return None
    except Exception as e:
        print_error("Zip creation failed.")
        logger.error(f"Unexpected error during zip: {e}")
        return None


def copy_without_zip(source_paths: List[str], destination_dir: str) -> bool:
    """
    Copy source files/folders directly to destination_dir without zipping.
    Returns True on success.
    """
    print_step("Copying files to destination...")
    logger.info(f"Copying files to: {destination_dir}")

    try:
        os.makedirs(destination_dir, exist_ok=True)

        for source in source_paths:
            source = os.path.abspath(source)
            dest = os.path.join(destination_dir, os.path.basename(source))
            if os.path.isfile(source):
                shutil.copy2(source, dest)
                logger.debug(f"  Copied file: {source} → {dest}")
            elif os.path.isdir(source):
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                shutil.copytree(source, dest)
                logger.debug(f"  Copied folder: {source} → {dest}")
            else:
                logger.warning(f"  Skipped (not found): {source}")

        print_success("Files copied to destination successfully.")
        return True

    except PermissionError as e:
        print_error("Copy failed — permission denied.")
        logger.error(f"Permission denied during copy: {e}")
        return False
    except Exception as e:
        print_error("Copy failed.")
        logger.error(f"Unexpected error during copy: {e}")
        return False


def delete_backup_file(backup_path: str) -> bool:
    """
    Delete a backup file or folder that was created by this tool.
    IMPORTANT: Only call this on paths that were created by the backup tool.

    Returns True if deleted successfully.
    """
    try:
        if os.path.isfile(backup_path):
            os.remove(backup_path)
            logger.info(f"Local backup file deleted: {backup_path}")
            return True
        elif os.path.isdir(backup_path):
            shutil.rmtree(backup_path)
            logger.info(f"Local backup folder deleted: {backup_path}")
            return True
        else:
            logger.warning(f"Backup path not found for deletion: {backup_path}")
            return False
    except PermissionError as e:
        logger.error(f"Permission denied when deleting backup: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during backup deletion: {e}")
        return False