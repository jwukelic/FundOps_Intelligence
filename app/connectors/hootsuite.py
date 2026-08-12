from __future__ import annotations

import csv
from pathlib import Path

import httpx

from app.models import ConnectorResult, SignalRecord


class HootsuiteConnector:
    name = "hootsuite"

    def __init__(self, api_token: str, csv_path: str, enabled: bool) -> None:
        self.api_token = api_token
        self.csv_path = csv_path
        self.enabled = enabled and bool(api_token or csv_path)

    def fetch(self, *, max_records: int, watermark: str | None) -> ConnectorResult:
        if not self.enabled:
            return ConnectorResult()
        if self.api_token:
            try:
                response = httpx.get(
                    "https://platform.hootsuite.com/v1/messages",
                    headers={"Authorization": "Bearer " + self.api_token},
                    timeout=20.0,
                )
                response.raise_for_status()
                items = response.json().get("data", [])[:max_records]
                return ConnectorResult(
                    signals=[
                        SignalRecord(
                            connector=self.name,
                            entity_type="account",
                            entity_key=item.get("profileName", "general"),
                            signal_type="engagement",
                            score=30.0,
                            external_id=item.get("id"),
                            source_url=item.get("permalink"),
                            summary=item.get("text", "Hootsuite activity"),
                        )
                        for item in items
                    ]
                )
            except Exception:
                pass
        if self.csv_path and Path(self.csv_path).exists():
            with Path(self.csv_path).open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))[:max_records]
            return ConnectorResult(
                signals=[
                    SignalRecord(
                        connector=self.name,
                        entity_type="account",
                        entity_key=row.get("profile", "general"),
                        signal_type="engagement",
                        score=float(row.get("score", "20")),
                        external_id=row.get("id"),
                        source_url=row.get("url"),
                        summary=row.get("summary", "Hootsuite CSV fallback"),
                    )
                    for row in rows
                ]
            )
        return ConnectorResult()
