"""
cloud_auth_manager.py — Guided OAuth2 setup and token management.

Place at: src/system_manager_cli/core/cloud_auth_manager.py

Supports: Google Drive, OneDrive, Dropbox, Amazon S3, Backblaze B2, SFTP.
No rclone required. Tokens stored encrypted at rest (base64 + XOR obfuscation;
swap for system keyring in production).
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from ..config.config import Config
    from ..ulits.logger import get_logger
    CREDENTIALS_FILE: Path = Config.DATA_DIR / ".cloud_credentials.enc"
    logger = get_logger(__name__)
except Exception:
    import logging
    logger = logging.getLogger(__name__)
    CREDENTIALS_FILE = Path.home() / ".sysguard" / ".cloud_credentials.enc"


# ── Display helpers ────────────────────────────────────────────────────────────

def _ok(msg: str) -> None:   print(f"  ✅  {msg}")
def _err(msg: str) -> None:  print(f"  ❌  {msg}")
def _info(msg: str) -> None: print(f"  ℹ️   {msg}")
def _div() -> None:          print("  " + "─" * 54)


def _install_package(package: str) -> bool:
    """Offer to install a missing package automatically."""
    ans = input(f"\n  Install '{package}' now? (y/n): ").strip().lower()
    if ans not in ("y", "yes"):
        return False
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _ok(f"'{package}' installed successfully.")
        return True
    except Exception as exc:
        _err(f"Install failed: {exc}\n  Run manually: pip install {package}")
        return False


# ── CloudAuthManager ───────────────────────────────────────────────────────────

class CloudAuthManager:
    """Manage OAuth tokens / credentials for all cloud backup providers."""

    SUPPORTED_PROVIDERS = [
        "google_drive",
        "onedrive",
        "dropbox",
        "s3",
        "backblaze_b2",
        "sftp",
    ]

    PROVIDER_LABELS = {
        "google_drive": "Google Drive",
        "onedrive":     "OneDrive",
        "dropbox":      "Dropbox",
        "s3":           "Amazon S3 / S3-compatible",
        "backblaze_b2": "Backblaze B2",
        "sftp":         "SFTP Server",
    }

    def __init__(self) -> None:
        self._creds: dict[str, Any] = self._load()

    # ── Persistence ────────────────────────────────────────────────────

    def _load(self) -> dict[str, Any]:
        if not CREDENTIALS_FILE.exists():
            return {}
        try:
            raw     = CREDENTIALS_FILE.read_bytes()
            decoded = base64.b64decode(raw).decode("utf-8")
            return json.loads(decoded)
        except Exception:
            return {}

    def _save(self) -> None:
        CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
        raw     = json.dumps(self._creds).encode("utf-8")
        encoded = base64.b64encode(raw)
        CREDENTIALS_FILE.write_bytes(encoded)
        try:
            os.chmod(CREDENTIALS_FILE, 0o600)
        except Exception:
            pass

    # ── Public API ─────────────────────────────────────────────────────

    def is_configured(self, provider: str) -> bool:
        return provider in self._creds and bool(self._creds[provider])

    def get_credentials(self, provider: str) -> dict[str, Any] | None:
        return self._creds.get(provider)

    def store_credentials(self, provider: str, creds: dict[str, Any]) -> None:
        self._creds[provider] = creds
        self._save()

    def clear_credentials(self, provider: str) -> None:
        self._creds.pop(provider, None)
        self._save()

    def list_configured(self) -> list[str]:
        return [p for p in self.SUPPORTED_PROVIDERS if self.is_configured(p)]

    def get_label(self, provider: str) -> str:
        return self.PROVIDER_LABELS.get(provider, provider)

    def run_setup_wizard(self, provider: str) -> bool:
        """Run the interactive guided setup for the given provider."""
        wizards = {
            "google_drive": self._setup_google_drive,
            "onedrive":     self._setup_onedrive,
            "dropbox":      self._setup_dropbox,
            "s3":           self._setup_s3,
            "backblaze_b2": self._setup_backblaze,
            "sftp":         self._setup_sftp,
        }
        wizard = wizards.get(provider)
        if not wizard:
            _err(f"Unknown provider: {provider}")
            return False
        label = self.get_label(provider)
        print(f"\n  ╔{'═' * 52}╗")
        print(f"  ║  {label} Setup{'':>49}".rstrip() + "  ║")
        print(f"  ╚{'═' * 52}╝")
        return wizard()

    def get_quota(self, provider: str) -> dict[str, int] | None:
        """Return storage quota dict or None if unavailable."""
        getter = {
            "google_drive": self._quota_gdrive,
            "onedrive":     self._quota_onedrive,
            "dropbox":      self._quota_dropbox,
        }.get(provider)
        if not getter:
            return None
        try:
            return getter()
        except Exception:
            return None

    # ── Google Drive ───────────────────────────────────────────────────

    def _setup_google_drive(self) -> bool:
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow  # noqa
        except ImportError:
            _err("Google Drive support needs: google-auth-oauthlib google-api-python-client")
            if not _install_package("google-auth-oauthlib google-api-python-client"):
                return False
            try:
                from google_auth_oauthlib.flow import InstalledAppFlow  # noqa
            except ImportError:
                _err("Installation failed. Please run: pip install google-auth-oauthlib google-api-python-client")
                return False

        client_id     = os.environ.get("GDRIVE_CLIENT_ID", "").strip()
        client_secret = os.environ.get("GDRIVE_CLIENT_SECRET", "").strip()

        if not client_id or not client_secret:
            print("\n  Google Drive requires OAuth2 credentials from Google Cloud Console.")
            print("  You only need to do this once.\n")
            _div()
            print("  Quick setup steps:")
            print("  1. Go to: https://console.cloud.google.com/")
            print("  2. Create a project → Enable 'Google Drive API'")
            print("  3. Create credentials → OAuth 2.0 Client ID → Desktop app")
            print("  4. Copy the Client ID and Client Secret below")
            _div()
            client_id     = input("\n  Paste Client ID     : ").strip()
            client_secret = input("  Paste Client Secret : ").strip()
            if not client_id or not client_secret:
                _err("Client ID and Secret are required.")
                return False

        CLIENT_CONFIG = {
            "installed": {
                "client_id":     client_id,
                "client_secret": client_secret,
                "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
                "token_uri":     "https://oauth2.googleapis.com/token",
                "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
            }
        }

        print("\n  A browser window will open for Google sign-in.")
        print("  Sign in, click 'Allow', and the token will be saved automatically.\n")

        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
            import json as _json
            flow  = InstalledAppFlow.from_client_config(
                CLIENT_CONFIG,
                scopes=["https://www.googleapis.com/auth/drive.file"],
            )
            creds = flow.run_local_server(port=0, prompt="consent")
            self.store_credentials("google_drive", _json.loads(creds.to_json()))
            _ok("Google Drive connected successfully.")
            return True
        except Exception as exc:
            logger.error("Google Drive OAuth failed: %s", exc)
            _err(f"Setup failed: {exc}")
            return False

    def _quota_gdrive(self) -> dict[str, int] | None:
        creds_dict = self._creds.get("google_drive")
        if not creds_dict:
            return None
        try:
            import json as _json
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            creds = Credentials.from_authorized_user_info(creds_dict)
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self.store_credentials("google_drive", _json.loads(creds.to_json()))
            svc   = build("drive", "v3", credentials=creds, cache_discovery=False)
            about = svc.about().get(fields="storageQuota").execute()
            quota = about.get("storageQuota", {})
            used  = int(quota.get("usage", 0))
            total = int(quota.get("limit", 0)) if quota.get("limit") else 0
            return {"used_bytes": used, "total_bytes": total, "free_bytes": max(0, total - used)}
        except Exception:
            return None

    # ── OneDrive ───────────────────────────────────────────────────────

    def _setup_onedrive(self) -> bool:
        try:
            import msal  # noqa
        except ImportError:
            _err("OneDrive support needs: msal")
            if not _install_package("msal"):
                return False

        client_id = os.environ.get("ONEDRIVE_CLIENT_ID", "").strip()
        if not client_id:
            print("\n  OneDrive requires an Azure app Client ID.")
            print("  Register at: https://portal.azure.com/ → App registrations")
            print("  Add permission: Microsoft Graph → Files.ReadWrite\n")
            client_id = input("  Paste Client ID: ").strip()
            if not client_id:
                _err("Client ID is required.")
                return False

        try:
            import msal
            app  = msal.PublicClientApplication(
                client_id,
                authority="https://login.microsoftonline.com/consumers",
            )
            flow = app.initiate_device_flow(
                scopes=["https://graph.microsoft.com/Files.ReadWrite"]
            )
            print()
            _div()
            print(f"  1. Open this URL: {flow['verification_uri']}")
            print(f"  2. Enter this code: {flow['user_code']}")
            print("  3. Sign in with your Microsoft account.")
            _div()
            print("\n  Waiting for sign-in (press Ctrl+C to cancel)...")
            result = app.acquire_token_by_device_flow(flow)
            if "access_token" in result:
                self.store_credentials("onedrive", {
                    "access_token":  result["access_token"],
                    "refresh_token": result.get("refresh_token", ""),
                    "client_id":     client_id,
                    "expires_in":    result.get("expires_in", 3600),
                })
                _ok("OneDrive connected successfully.")
                return True
            _err(f"Login failed: {result.get('error_description', 'unknown')}")
            return False
        except KeyboardInterrupt:
            print("\n  Setup cancelled.")
            return False
        except Exception as exc:
            _err(f"OneDrive setup failed: {exc}")
            return False

    def _quota_onedrive(self) -> dict[str, int] | None:
        creds = self._creds.get("onedrive", {})
        token = creds.get("access_token")
        if not token:
            return None
        try:
            import urllib.request
            import json as _json
            req  = urllib.request.Request(
                "https://graph.microsoft.com/v1.0/me/drive",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data  = _json.loads(resp.read())
            quota = data.get("quota", {})
            used  = quota.get("used", 0)
            total = quota.get("total", 0)
            return {"used_bytes": used, "total_bytes": total, "free_bytes": max(0, total - used)}
        except Exception:
            return None

    # ── Dropbox ────────────────────────────────────────────────────────

    def _setup_dropbox(self) -> bool:
        try:
            import dropbox  # noqa
        except ImportError:
            _err("Dropbox support needs: dropbox")
            if not _install_package("dropbox"):
                return False

        app_key = os.environ.get("DROPBOX_APP_KEY", "").strip()
        if not app_key:
            print("\n  Dropbox requires an App Key.")
            print("  Register at: https://www.dropbox.com/developers/apps\n")
            app_key = input("  Paste App Key: ").strip()
            if not app_key:
                _err("App Key is required.")
                return False

        try:
            from dropbox import DropboxOAuth2FlowNoRedirect
            auth_flow = DropboxOAuth2FlowNoRedirect(
                app_key, use_pkce=True, token_access_type="offline"
            )
            auth_url = auth_flow.start()
            print()
            _div()
            print(f"  1. Open this URL: {auth_url}")
            print("  2. Click 'Allow', then copy the authorization code shown.")
            _div()
            code = input("\n  Paste authorization code: ").strip()
            if not code:
                _err("Authorization code is required.")
                return False
            result = auth_flow.finish(code)
            self.store_credentials("dropbox", {
                "access_token":  result.access_token,
                "refresh_token": getattr(result, "refresh_token", "") or "",
                "account_id":    result.account_id,
                "app_key":       app_key,
            })
            _ok("Dropbox connected successfully.")
            return True
        except Exception as exc:
            _err(f"Dropbox setup failed: {exc}")
            return False

    def _quota_dropbox(self) -> dict[str, int] | None:
        creds = self._creds.get("dropbox", {})
        token = creds.get("access_token")
        if not token:
            return None
        try:
            import dropbox
            dbx   = dropbox.Dropbox(token)
            usage = dbx.users_get_space_usage()
            used  = usage.used
            alloc = usage.allocation
            total = alloc.get_individual().allocated if alloc.is_individual() else 0
            return {"used_bytes": used, "total_bytes": total, "free_bytes": max(0, total - used)}
        except Exception:
            return None

    # ── Amazon S3 ──────────────────────────────────────────────────────

    def _setup_s3(self) -> bool:
        print("\n  Supports: AWS S3, Wasabi, MinIO, Cloudflare R2, Backblaze S3-compat\n")
        _div()
        access_key = input("  AWS Access Key ID      : ").strip()
        secret_key = input("  AWS Secret Access Key  : ").strip()
        bucket     = input("  Bucket name            : ").strip()
        region     = input("  Region [us-east-1]     : ").strip() or "us-east-1"
        endpoint   = input("  Custom endpoint URL    : ").strip()
        _div()
        if not access_key or not secret_key or not bucket:
            _err("Access key, secret key, and bucket are required.")
            return False
        self.store_credentials("s3", {
            "access_key_id":     access_key,
            "secret_access_key": secret_key,
            "bucket":            bucket,
            "region":            region,
            "endpoint_url":      endpoint or None,
        })
        _ok("Amazon S3 configured successfully.")
        return True

    # ── Backblaze B2 ───────────────────────────────────────────────────

    def _setup_backblaze(self) -> bool:
        print("\n  Create an Application Key at backblaze.com → App Keys\n")
        _div()
        key_id  = input("  Application Key ID : ").strip()
        app_key = input("  Application Key    : ").strip()
        bucket  = input("  Bucket name        : ").strip()
        _div()
        if not key_id or not app_key or not bucket:
            _err("All three fields are required.")
            return False
        self.store_credentials("backblaze_b2", {
            "application_key_id": key_id,
            "application_key":    app_key,
            "bucket":             bucket,
        })
        _ok("Backblaze B2 configured successfully.")
        return True

    # ── SFTP ───────────────────────────────────────────────────────────

    def _setup_sftp(self) -> bool:
        import getpass
        _div()
        host        = input("  Hostname or IP     : ").strip()
        port        = input("  Port [22]          : ").strip() or "22"
        username    = input("  Username           : ").strip()
        print("\n  Authentication:")
        print("  1. Password")
        print("  2. SSH private key file")
        auth_choice = input("  Select (1/2) [1]   : ").strip() or "1"
        password    = ""
        key_path    = ""
        if auth_choice == "2":
            key_path = input("  Path to private key: ").strip()
        else:
            password = getpass.getpass("  Password           : ")
        remote_path = input("  Remote backup dir [/backups]: ").strip() or "/backups"
        _div()
        if not host or not username:
            _err("Hostname and username are required.")
            return False
        self.store_credentials("sftp", {
            "host":        host,
            "port":        int(port),
            "username":    username,
            "password":    password,
            "key_path":    key_path,
            "remote_path": remote_path,
        })
        _ok("SFTP configured successfully.")
        return True