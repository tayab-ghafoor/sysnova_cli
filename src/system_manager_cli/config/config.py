from __future__ import annotations

import os
import sys
from pathlib import Path


def _get_app_data_root() -> Path:
    """Return a writable application data root appropriate for the current OS."""
    override = os.getenv("SYSTEM_MANAGER_CLI_HOME", "").strip()
    if override:
        return Path(override).expanduser()

    if sys.platform == "win32":
        base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "SysNova"

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "SysNova"

    # Runtime state belongs in XDG_DATA_HOME, not in the install directory.
    base = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "sysnova"


# ====================== Determine paths (module level) ======================
if getattr(sys, "frozen", False):
    # Running as bundled executable (production)
    _PROJECT_ROOT = Path(sys.executable).resolve().parent
    _PACKAGE_DIR = Path(getattr(sys, "_MEIPASS", _PROJECT_ROOT)) / "system_manager_cli"
    _IS_FROZEN = True
else:
    # Running from source (development)
    _PROJECT_ROOT = Path(__file__).resolve().parents[3]
    _PACKAGE_DIR = _PROJECT_ROOT / 'src' / 'system_manager_cli'
    _IS_FROZEN = False


class Config:
    r"""Application configuration for production deployment on Railway.

    Configuration priority (higher overrides lower):
        1. Environment variables (os.getenv) - set on Railway platform
        2. Default values (safe defaults)
    
    NOTE: For exe distribution - do NOT include .env files.
          All configuration comes from Railway environment variables.
          Frontend requests backend directly without requiring env files in exe.
    """
    # ====================== Read‑only application directories ======================
    PROJECT_ROOT = _PROJECT_ROOT
    PACKAGE_DIR = _PACKAGE_DIR
    IS_FROZEN = _IS_FROZEN

    # ====================== User‑writable data directories ======================
    APP_DATA_ROOT = _get_app_data_root()

    DATA_DIR = APP_DATA_ROOT / 'data'
    LOGS_DIR = APP_DATA_ROOT / 'logs'
    REPORTS_DIR = APP_DATA_ROOT / 'reports'
    BACKUPS_DIR = APP_DATA_ROOT / 'backups'
    UPDATER_DIR = APP_DATA_ROOT / '.updater' / 'backups'

    # ====================== Environment‑aware settings (from Railway) ======================
    EMAIL_SENDER = os.getenv('EMAIL_SENDER', '')
    EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', '')
    EMAIL_RECIPIENT = os.getenv('EMAIL_RECIPIENT', '')
    SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '465'))
    SMTP_USE_SSL = os.getenv('SMTP_USE_SSL', 'true').lower() == 'true'
    SMTP_USE_TLS = os.getenv('SMTP_USE_TLS', 'false').lower() == 'true'

    APP_ENV = os.getenv('APP_ENV', 'production').strip().lower()
    DEVELOPMENT_MODE = (
        APP_ENV in {'dev', 'development', 'local'}
        or os.getenv('SYSTEM_MANAGER_DEV_MODE', 'false').lower() == 'true'
    )

    CPU_THRESHOLD = int(os.getenv('CPU_THRESHOLD', '80'))
    RAM_THRESHOLD = int(os.getenv('RAM_THRESHOLD', '85'))
    DISK_THRESHOLD = int(os.getenv('DISK_THRESHOLD', '90'))

    # BACKEND_URL MUST be set on Railway platform for production
    # No default fallback - if not configured, backend features are disabled
    BACKEND_URL = os.getenv('BACKEND_URL', 'https://backendcli-production.up.railway.app').strip()
    
    @classmethod
    def validate_backend_url(cls) -> tuple[bool, str]:
        """
        Validate that BACKEND_URL is properly configured.
        
        Returns:
            (is_valid, message)
        """
        if not cls.BACKEND_URL:
            return False, "BACKEND_URL environment variable not set. Backend features disabled."
        
        if not cls.BACKEND_URL.startswith(("http://", "https://")):
            return False, f"Invalid BACKEND_URL format: {cls.BACKEND_URL}. Must start with http:// or https://"
        
        try:
            from urllib.parse import urlparse
            parsed = urlparse(cls.BACKEND_URL)
            if not parsed.netloc:
                return False, f"Invalid BACKEND_URL: missing hostname in {cls.BACKEND_URL}"
        except Exception as e:
            return False, f"Invalid BACKEND_URL: {e}"
        
        return True, "BACKEND_URL is valid"

    _backup_drive_env = os.getenv('BACKUP_DRIVE', '')
    BACKUP_DRIVE = Path(_backup_drive_env) if _backup_drive_env else BACKUPS_DIR

    MAX_BACKUPS = int(os.getenv('MAX_BACKUPS', '7'))

    RCLONE_REMOTE = os.getenv('RCLONE_REMOTE', 'gdrive')
    RCLONE_BACKUP_PATH = os.getenv('RCLONE_BACKUP_PATH', '/backups')
    USE_RCLONE = os.getenv('USE_RCLONE', 'true').lower() == 'true'

    # ====================== Directory initialisation ======================
    @classmethod
    def ensure_directories(cls) -> None:
        """
        Create all required user‑writable directories.
        Call this once at application startup.
        
        Raises:
            PermissionError: If unable to create required directories.
        """
        directories = [
            cls.DATA_DIR,
            cls.LOGS_DIR,
            cls.REPORTS_DIR,
            cls.BACKUPS_DIR,
            cls.UPDATER_DIR,
        ]
        
        failed_dirs = []
        for path in directories:
            try:
                path.mkdir(parents=True, exist_ok=True)
            except PermissionError as e:
                failed_dirs.append((str(path), str(e)))
            except OSError as e:
                failed_dirs.append((str(path), str(e)))
        
        if failed_dirs:
            error_details = "; ".join([f"{p}: {err}" for p, err in failed_dirs])
            raise PermissionError(
                f"Failed to create required directories: {error_details}. "
                f"Ensure write permissions in user data directory: {cls.APP_DATA_ROOT}"
            )

    @classmethod
    def get_data_dir(cls) -> Path:
        """Return the data directory (ensures it exists)."""
        cls.ensure_directories()
        return cls.DATA_DIR

    @classmethod
    def get_logs_dir(cls) -> Path:
        """Return the logs directory (ensures it exists)."""
        cls.ensure_directories()
        return cls.LOGS_DIR

    @classmethod
    def get_reports_dir(cls) -> Path:
        """Return the reports directory (ensures it exists)."""
        cls.ensure_directories()
        return cls.REPORTS_DIR

    @classmethod
    def get_backups_dir(cls) -> Path:
        """Return the backups directory (ensures it exists)."""
        cls.ensure_directories()
        return cls.BACKUPS_DIR


def ensure_config_directories() -> None:
    """Compatibility helper for older imports."""
    Config.ensure_directories()


def get_data_dir() -> Path:
    """Compatibility helper for older imports."""
    return Config.get_data_dir()

def get_logs_dir() -> Path:
    """Compatibility helper for older imports."""
    return Config.get_logs_dir()

def get_reports_dir() -> Path:
    """Compatibility helper for older imports."""
    return Config.get_reports_dir()

def get_backups_dir() -> Path:
    """Compatibility helper for older imports."""
    return Config.get_backups_dir()
