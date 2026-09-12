from __future__ import annotations

from app.models import ContentRecord


def retrieve_content(entity_key: str, contents: list[ContentRecord], limit: int = 5) -> list[ContentRecord]:
    tokens = {token for token in entity_key.lower().split() if token}
    ranked = sorted(
        contents,
        key=lambda item: (
            sum(1 for token in tokens if token in f"{item.title} {item.text}".lower()),
            item.updated_at,
        ),
        reverse=True,
    )
    return ranked[:limit]

