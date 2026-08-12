from __future__ import annotations

import httpx

from app.models import ConnectorResult, SignalRecord


class MailchimpConnector:
    name = "mailchimp"

    def __init__(self, api_key: str, server_prefix: str, enabled: bool) -> None:
        self.api_key = api_key
        self.server_prefix = server_prefix
        self.enabled = enabled and bool(api_key and server_prefix)

    def fetch(self, *, max_records: int, watermark: str | None) -> ConnectorResult:
        if not self.enabled:
            return ConnectorResult()
        url = f"https://{self.server_prefix}.api.mailchimp.com/3.0/reports"
        response = httpx.get(url, auth=("anystring", self.api_key), params={"count": max_records}, timeout=20.0)
        response.raise_for_status()
        reports = response.json().get("reports", [])
        signals = [
            SignalRecord(
                connector=self.name,
                entity_type="account",
                entity_key=report.get("campaign_title", "general"),
                signal_type="engagement",
                score=min(float(report.get("open_rate", 0.0)) * 100, 100.0),
                external_id=report.get("id"),
                source_id=report.get("id"),
                summary=f"Mailchimp campaign engagement for {report.get('campaign_title', 'campaign')}",
                metadata={"emails_sent": report.get("emails_sent"), "open_rate": report.get("open_rate")},
            )
            for report in reports
        ]
        return ConnectorResult(signals=signals)

