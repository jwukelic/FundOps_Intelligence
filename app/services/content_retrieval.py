from app.connectors.google_drive import DriveDocument


def build_content_index(docs: list[DriveDocument]) -> list[dict]:
    return [
        {
            "file_id": d.file_id,
            "file_name": d.file_name,
            "program": d.program,
            "source_url": d.source_url,
            "text_hash": d.text_hash,
            "approval_status": d.approval_status,
        }
        for d in docs
    ]
