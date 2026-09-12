from __future__ import annotations

from googleapiclient.discovery import build

from app.models import ConnectorResult, ContentRecord


class GoogleDriveConnector:
    name = "google_drive"

    def __init__(self, folder_id: str, enabled: bool, credentials=None) -> None:
        self.folder_id = folder_id
        self.enabled = enabled and bool(folder_id)
        self.credentials = credentials

    def fetch(self, *, max_records: int, watermark: str | None) -> ConnectorResult:
        if not self.enabled:
            return ConnectorResult()
        service = build("drive", "v3", credentials=self.credentials, cache_discovery=False)
        query = f"'{self.folder_id}' in parents and trashed = false"
        response = service.files().list(q=query, pageSize=max_records, fields="files(id,name,modifiedTime,webViewLink,description)").execute()
        items = [
            ContentRecord(
                content_id=f"drive:{item['id']}",
                connector=self.name,
                entity_key=item.get("name", "general"),
                title=item.get("name", "Untitled"),
                text=item.get("description", ""),
                approved=True,
                source_url=item.get("webViewLink"),
                metadata={"modifiedTime": item.get("modifiedTime")},
            )
            for item in response.get("files", [])
        ]
        return ConnectorResult(content=items)

