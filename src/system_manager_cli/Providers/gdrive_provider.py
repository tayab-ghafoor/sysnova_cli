"""
Google Drive backup provider using the Google Drive API (via google-auth + googleapiclient).

Required packages:
    pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client

OAuth credentials file (credentials.json) must be placed at:
    system_manager_cli/config/gdrive_credentials.json

On first run the user is directed to a browser for OAuth consent.
The resulting token is saved at:
    system_manager_cli/config/gdrive_token.json
"""

import os
import mimetypes
from typing import Optional

from .base_provider import BackupProvider

# FIX: `logger` is not exported from logger.py — use get_logger instead
from system_manager_cli.ulits.logger import get_logger
from system_manager_cli.ulits.progress import print_error

logger = get_logger(__name__)

CREDENTIALS_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "gdrive_credentials.json")
)
TOKEN_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "gdrive_token.json")
)
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class GDriveProvider(BackupProvider):

    def __init__(self):
        self._service = None

    @property
    def name(self) -> str:
        return "Google Drive"

    def authenticate(self) -> bool:
        """
        Authenticate with Google Drive using OAuth2.
        Opens browser on first use; re-uses saved token afterwards.
        """
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
        except ImportError:
            print_error(
                "Google API libraries not installed.\n"
                "  Run: pip install google-auth google-auth-oauthlib "
                "google-auth-httplib2 google-api-python-client"
            )
            logger.error("Google API libraries missing.")
            return False

        if not os.path.exists(CREDENTIALS_FILE):
            print_error(
                f"Google Drive credentials file not found.\n"
                f"  Expected: {CREDENTIALS_FILE}\n"
                f"  Download it from Google Cloud Console > APIs & Services > Credentials."
            )
            logger.error(f"Credentials file missing: {CREDENTIALS_FILE}")
            return False

        creds = None
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.warning(f"Token refresh failed: {e}. Re-authenticating...")
                    creds = None

            if not creds:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    print_error("Authentication failed.")
                    logger.error(f"OAuth flow error: {e}")
                    return False

            with open(TOKEN_FILE, "w") as token:
                token.write(creds.to_json())

        try:
            self._service = build("drive", "v3", credentials=creds)
            logger.info("Google Drive authenticated successfully.")
            return True
        except Exception as e:
            print_error("Authentication failed.")
            logger.error(f"Drive service build error: {e}")
            return False

    def upload(self, local_path: str, remote_destination: Optional[str] = None) -> bool:
        """Upload a file or folder to Google Drive."""
        if self._service is None:
            if not self.authenticate():
                return False

        try:

            if os.path.isfile(local_path):
                return self._upload_file(local_path)
            elif os.path.isdir(local_path):
                return self._upload_folder(local_path)
            else:
                print_error(f"Local path not found: {local_path}")
                logger.error(f"Upload source missing: {local_path}")
                return False
        except Exception as e:
            print_error("Upload interrupted.")
            logger.error(f"Upload error: {e}")
            return False

    def _upload_file(self, file_path: str, parent_id: Optional[str] = None) -> bool:
        from googleapiclient.http import MediaFileUpload

        filename = os.path.basename(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or "application/octet-stream"

        file_metadata = {"name": filename}
        if parent_id:
            file_metadata["parents"] = [parent_id]

        media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)

        request = self._service.files().create(
            body=file_metadata, media_body=media, fields="id"
        )

        # Real resumable upload with progress
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                print(f"\r  Progress: {pct}%", end="", flush=True)
        print()  # newline

        logger.info(f"Uploaded to Google Drive: {filename} (ID: {response.get('id')})")
        return True

    def _upload_folder(self, folder_path: str, parent_id: Optional[str] = None) -> bool:
        folder_name = os.path.basename(folder_path)
        folder_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            folder_metadata["parents"] = [parent_id]

        folder = self._service.files().create(
            body=folder_metadata, fields="id"
        ).execute()
        folder_id = folder.get("id")
        logger.debug(f"Created Drive folder: {folder_name} (ID: {folder_id})")

        for item in os.listdir(folder_path):
            item_path = os.path.join(folder_path, item)
            if os.path.isfile(item_path):
                self._upload_file(item_path, parent_id=folder_id)
            elif os.path.isdir(item_path):
                self._upload_folder(item_path, parent_id=folder_id)

        return True