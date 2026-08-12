from __future__ import annotations

from googleapiclient.discovery import build

from app.models import ConnectorResult, OpportunityRecord, SignalRecord


class GoogleSheetsConnector:
    name = "google_sheets"

    def __init__(self, spreadsheet_id: str, cell_range: str, enabled: bool, credentials=None) -> None:
        self.spreadsheet_id = spreadsheet_id
        self.cell_range = cell_range
        self.enabled = enabled and bool(spreadsheet_id)
        self.credentials = credentials

    def fetch(self, *, max_records: int, watermark: str | None) -> ConnectorResult:
        if not self.enabled:
            return ConnectorResult()
        service = build("sheets", "v4", credentials=self.credentials, cache_discovery=False)
        values = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=self.cell_range)
            .execute()
            .get("values", [])
        )
        rows = values[1 : max_records + 1]
        opportunities: list[OpportunityRecord] = []
        signals: list[SignalRecord] = []
        for row in rows:
            external_id, account_key, name, amount, stage_name, close_date, source_url = (row + [""] * 7)[:7]
            opportunities.append(
                OpportunityRecord(
                    external_id=external_id,
                    account_key=account_key,
                    name=name,
                    amount=float(amount) if amount else None,
                    stage_name=stage_name or "Prospecting",
                    close_date=close_date or None,
                    source_url=source_url or None,
                )
            )
            signals.append(
                SignalRecord(
                    connector=self.name,
                    entity_type="account",
                    entity_key=account_key,
                    signal_type="intent",
                    score=75.0 if amount else 40.0,
                    external_id=f"{external_id}:intake",
                    source_url=source_url or None,
                    summary=f"Opportunity intake for {name}",
                    metadata={"stage_name": stage_name, "amount": amount},
                )
            )
        return ConnectorResult(signals=signals, opportunities=opportunities)

