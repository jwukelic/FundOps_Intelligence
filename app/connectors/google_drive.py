from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from typing import Any

import google.auth  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


@dataclass
class DriveDocument:
    file_id: str
    file_name: str
    program: str
    modified_time: str
    source_url: str
    text_hash: str
    extracted_text: str
    approval_status: str = "approved"


# Folder name → program label used for score_from_account matching.
# Sub-folders named after each program inside the approved folder are
# supported; top-level files get program="General".
_GENERAL_PROGRAM = "General"
_MAX_TEXT_BYTES = 40_000
_MIME_EXPORTABLE = "application/vnd.google-apps.document"
_MIME_PLAIN_TEXT = "text/plain"


class GoogleDriveConnector:
    """Google Drive approved-evidence connector.

    Lists files inside ``folder_id`` (recursively one level deep), exports
    Google Docs as plain text, and returns ``DriveDocument`` objects.

    In production, authenticates via ADC (Application Default Credentials).
    Only reads files; never writes.
    """

    def __init__(self, folder_id: str = "", credentials: Any = None) -> None:
        self._folder_id = folder_id or os.environ.get("FUNDOPS_APPROVED_DRIVE_FOLDER_ID", "")
        self._creds = credentials
        self._service: Any = None

        if self._folder_id:
            self._connect()

    def _connect(self) -> None:
        try:
            from googleapiclient.discovery import build  # type: ignore[import-untyped]

            creds = self._creds
            if creds is None:
                creds, _ = google.auth.default(
                    scopes=["https://www.googleapis.com/auth/drive.readonly"]
                )
            self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Google Drive connection failed: %s — evidence will be skipped.", exc)

    def list_approved_documents(self) -> list[DriveDocument]:
        if self._service is None or not self._folder_id:
            return []
        docs: list[DriveDocument] = []
        # List immediate children of approved folder.
        items = self._list_folder(self._folder_id)
        for item in items:
            if item.get("mimeType") == "application/vnd.google-apps.folder":
                # Treat sub-folder name as program label.
                program = item["name"]
                for child in self._list_folder(item["id"]):
                    doc = self._fetch_document(child, program)
                    if doc:
                        docs.append(doc)
            else:
                doc = self._fetch_document(item, _GENERAL_PROGRAM)
                if doc:
                    docs.append(doc)
        return docs

    def _list_folder(self, folder_id: str) -> list[dict[str, Any]]:
        try:
            result = (
                self._service.files()
                .list(
                    q=f"'{folder_id}' in parents and trashed = false",
                    fields="files(id,name,mimeType,modifiedTime,webViewLink)",
                    pageSize=100,
                )
                .execute()
            )
            return result.get("files", [])
        except Exception as exc:  # noqa: BLE001
            logger.error("Drive list failed for folder %s: %s", folder_id, exc)
            return []

    def _fetch_document(self, item: dict[str, Any], program: str) -> DriveDocument | None:
        file_id = item["id"]
        mime = item.get("mimeType", "")
        try:
            if mime == _MIME_EXPORTABLE:
                content = (
                    self._service.files()
                    .export(fileId=file_id, mimeType=_MIME_PLAIN_TEXT)
                    .execute()
                )
                text = content.decode("utf-8", errors="replace")[:_MAX_TEXT_BYTES] if isinstance(content, bytes) else str(content)[:_MAX_TEXT_BYTES]
            else:
                # Binary / other types: skip text extraction.
                text = ""
            text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            return DriveDocument(
                file_id=file_id,
                file_name=item.get("name", ""),
                program=program,
                modified_time=item.get("modifiedTime", ""),
                source_url=item.get("webViewLink", f"https://drive.google.com/file/d/{file_id}"),
                text_hash=text_hash,
                extracted_text=text,
                approval_status="approved",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Drive fetch failed for %s: %s", file_id, exc)
            return None
