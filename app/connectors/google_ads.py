from __future__ import annotations

from app.models import ConnectorResult


class GoogleAdsConnector:
    name = "google_ads"

    def __init__(self, customer_id: str, developer_token: str, enabled: bool) -> None:
        self.customer_id = customer_id
        self.developer_token = developer_token
        self.enabled = enabled and bool(customer_id and developer_token)

    def fetch(self, *, max_records: int, watermark: str | None) -> ConnectorResult:
        return ConnectorResult()

