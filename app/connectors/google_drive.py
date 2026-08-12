from dataclasses import dataclass


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


class GoogleDriveConnector:
    def list_approved_documents(self) -> list[DriveDocument]:
        return []
