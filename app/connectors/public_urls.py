from __future__ import annotations

import httpx

from app.models import ConnectorResult, ContentRecord


class PublicURLConnector:
    name = "public_urls"

    def __init__(self, urls: list[str], enabled: bool) -> None:
        self.urls = urls
        self.enabled = enabled and bool(urls)

    def fetch(self, *, max_records: int, watermark: str | None) -> ConnectorResult:
        if not self.enabled:
            return ConnectorResult()
        content: list[ContentRecord] = []
        for url in self.urls[:max_records]:
            response = httpx.get(url, timeout=20.0)
            response.raise_for_status()
            content.append(
                ContentRecord(
                    content_id=f"url:{url}",
                    connector=self.name,
                    entity_key=url,
                    title=url,
                    text=response.text[:4000],
                    approved=True,
                    source_url=url,
                )
            )
        return ConnectorResult(content=content, public_urls=self.urls[:max_records])

