from __future__ import annotations

import logging
import os
from typing import Any

import google.auth  # type: ignore[import-untyped]

from app.models import OpportunityInput

logger = logging.getLogger(__name__)

# Column indices (0-based) expected in the intake sheet.
# Row format: URL | Organization | Program | Opportunity Type | Notes | Status | SF Opp ID | Error
_COL_URL = 0
_COL_ORG = 1
_COL_PROGRAM = 2
_COL_TYPE = 3
_COL_NOTES = 4
_COL_STATUS = 5
_COL_SF_ID = 6
_COL_ERROR = 7

_STATUS_NEW = "new"
_STATUS_CHANGED = "changed"
_STATUS_PROCESSED = "processed"
_STATUS_ERROR = "error"

# First data row (0-based); row 0 is the header.
_FIRST_DATA_ROW = 1


class GoogleSheetsConnector:
    """Google Sheets intake connector.

    In production, reads credential from ADC (Application Default Credentials)
    so no extra secret is needed when running on Cloud Run.

    The intake sheet must have columns:
      A: URL  B: Organization  C: Program  D: Opportunity Type
      E: Notes  F: Status  G: Salesforce Opportunity ID  H: Error
    """

    def __init__(self, sheet_id: str = "", credentials: Any = None) -> None:
        self._sheet_id = sheet_id or os.environ.get("FUNDOPS_INTAKE_SHEET_ID", "")
        self._creds = credentials
        self._service: Any = None
        self._rows_cache: list[list[str]] = []

        if self._sheet_id:
            self._connect()

    def _connect(self) -> None:
        try:
            from googleapiclient.discovery import build  # type: ignore[import-untyped]

            creds = self._creds
            if creds is None:
                creds, _ = google.auth.default(
                    scopes=["https://www.googleapis.com/auth/spreadsheets"]
                )
            self._service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Google Sheets connection failed: %s — intake will be skipped.", exc)

    def _read_all_rows(self) -> list[list[str]]:
        if self._service is None or not self._sheet_id:
            return []
        try:
            result = (
                self._service.spreadsheets()
                .values()
                .get(spreadsheetId=self._sheet_id, range="Sheet1!A:H")
                .execute()
            )
            rows: list[list[str]] = result.get("values", [])
            return rows
        except Exception as exc:  # noqa: BLE001
            logger.error("Sheets read failed: %s", exc)
            return []

    def list_new_or_changed_intake_rows(self) -> list[OpportunityInput]:
        self._rows_cache = self._read_all_rows()
        results: list[OpportunityInput] = []
        for i, row in enumerate(self._rows_cache):
            if i < _FIRST_DATA_ROW:
                continue  # skip header
            _pad(row, _COL_ERROR + 1)
            status = row[_COL_STATUS].strip().lower()
            url = row[_COL_URL].strip()
            if not url:
                continue
            if status in (_STATUS_PROCESSED,):
                continue
            results.append(
                OpportunityInput(
                    url=url,
                    organization=row[_COL_ORG].strip(),
                    program=row[_COL_PROGRAM].strip(),
                    opportunity_type=row[_COL_TYPE].strip(),
                    notes=row[_COL_NOTES].strip(),
                    row_id=str(i),
                )
            )
        return results

    def mark_processed(self, row_id: str, salesforce_opportunity_id: str, error: str = "") -> None:
        if self._service is None or not self._sheet_id:
            return
        try:
            row_index = int(row_id)
        except ValueError:
            logger.warning("mark_processed: non-integer row_id '%s' — skipping Sheets write.", row_id)
            return
        # Sheets API is 1-based; row 0 in our list = row 1 in Sheets.
        sheet_row = row_index + 1
        status = _STATUS_ERROR if error else _STATUS_PROCESSED
        try:
            self._service.spreadsheets().values().update(
                spreadsheetId=self._sheet_id,
                range=f"Sheet1!F{sheet_row}:H{sheet_row}",
                valueInputOption="RAW",
                body={"values": [[status, salesforce_opportunity_id, error[:255]]]},
            ).execute()
        except Exception as exc:  # noqa: BLE001
            logger.error("Sheets write failed for row %s: %s", row_id, exc)


def _pad(row: list[str], length: int) -> None:
    while len(row) < length:
        row.append("")
