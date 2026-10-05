import os
import json
from pathlib import Path
from typing import Optional, Dict, Any

CREDENTIALS_FILE = Path(__file__).resolve().parent.parent / "gdrive_credentials.json"
SETTINGS_FILE = Path(__file__).resolve().parent.parent / "gdrive_settings.json"

SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

class GoogleDriveManager:
    def __init__(self):
        self._service = None

    def get_settings(self) -> Dict[str, Any]:
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "folder_id": os.environ.get("GDRIVE_FOLDER_ID", ""),
            "enabled": False,
            "service_account_configured": CREDENTIALS_FILE.exists()
        }

    def save_settings(self, folder_id: str, enabled: bool):
        settings = {
            "folder_id": folder_id.strip(),
            "enabled": enabled,
            "service_account_configured": CREDENTIALS_FILE.exists()
        }
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)
        return settings

    def save_service_account_json(self, content_str: str) -> bool:
        try:
            data = json.loads(content_str)
            with open(CREDENTIALS_FILE, "w") as f:
                json.dump(data, f, indent=2)
            # Reset client
            self._service = None
            return True
        except Exception:
            return False

    def is_configured(self) -> bool:
        settings = self.get_settings()
        return settings.get("enabled", False) and CREDENTIALS_FILE.exists()

    def _get_service(self):
        if self._service is not None:
            return self._service

        if not CREDENTIALS_FILE.exists():
            return None

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            creds = service_account.Credentials.from_service_account_file(
                str(CREDENTIALS_FILE), scopes=SCOPES
            )
            self._service = build("drive", "v3", credentials=creds)
            return self._service
        except Exception as e:
            print(f"[GoogleDrive] Error initializing service: {e}")
            return None

    def upload_file(self, local_path: str, custom_folder_id: Optional[str] = None) -> Optional[Dict[str, str]]:
        """Uploads a file to Google Drive. Returns dict with file_id and web_link."""
        service = self._get_service()
        if not service:
            return None

        path_obj = Path(local_path)
        if not path_obj.exists():
            return None

        from googleapiclient.http import MediaFileUpload

        settings = self.get_settings()
        folder_id = custom_folder_id or settings.get("folder_id")

        file_metadata = {"name": path_obj.name}
        if folder_id:
            file_metadata["parents"] = [folder_id]

        # Determine mimetype
        mimetype = "video/mp4" if path_obj.suffix.lower() == ".mp4" else "text/csv"
        media = MediaFileUpload(str(path_obj), mimetype=mimetype, resumable=True)

        try:
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id, webViewLink, webContentLink"
            ).execute()

            return {
                "file_id": file.get("id"),
                "web_view_link": file.get("webViewLink", ""),
                "name": path_obj.name
            }
        except Exception as e:
            print(f"[GoogleDrive] Upload error for {local_path}: {e}")
            return None

    def list_videos(self, custom_folder_id: Optional[str] = None) -> list:
        """Lists videos in the Google Drive folder."""
        service = self._get_service()
        if not service:
            return []

        settings = self.get_settings()
        folder_id = custom_folder_id or settings.get("folder_id")
        query = "mimeType contains 'video/' and trashed = false"
        if folder_id:
            query += f" and '{folder_id}' in parents"

        try:
            results = service.files().list(
                q=query,
                pageSize=30,
                orderBy="createdTime desc",
                fields="files(id, name, mimeType, webViewLink, webContentLink, createdTime, size, thumbnailLink)"
            ).execute()
            return results.get("files", [])
        except Exception as e:
            print(f"[GoogleDrive] Error listing files: {e}")
            return []

# Singleton instance
gdrive_manager = GoogleDriveManager()
