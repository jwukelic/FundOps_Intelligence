from __future__ import annotations

import csv
import logging
from pathlib import Path

import httpx

from app.models import ConnectorResult, SignalRecord

LOGGER = logging.getLogger(__name__)

# Required columns that a Hootsuite CSV export must contain.
_REQUIRED_CSV_COLUMNS: frozenset[str] = frozenset({"id", "profile", "score", "summary"})
# Columns that, when present, are used for enrichment but are not mandatory.
_OPTIONAL_CSV_COLUMNS: frozenset[str] = frozenset({"url", "published_at"})

_HOOTSUITE_BASE = "https://platform.hootsuite.com/v1"
# Maximum pages fetched per run to stay within cost/time budget.
_MAX_PAGES = 10


def _validate_csv_headers(headers: list[str], path: str) -> None:
    """Raise ValueError if the CSV is missing any required column."""
    present = frozenset(h.strip().lower() for h in headers)
    missing = _REQUIRED_CSV_COLUMNS - present
    if missing:
        raise ValueError(
            f"Hootsuite CSV at '{path}' is missing required columns: {sorted(missing)}. "
            f"Found columns: {sorted(present)}"
        )


def _safe_float(value: str, default: float = 20.0) -> float:
    """Parse *value* as float; return *default* on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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
                return self._fetch_api(max_records=max_records, watermark=watermark)
            except Exception as exc:
                LOGGER.warning("Hootsuite API fetch failed, falling back to CSV: %s", exc)
        if self.csv_path and Path(self.csv_path).exists():
            return self._fetch_csv(max_records=max_records)
        return ConnectorResult()

    # ------------------------------------------------------------------
    # API path (paginated)
    # ------------------------------------------------------------------

    def _fetch_api(self, *, max_records: int, watermark: str | None) -> ConnectorResult:
        signals: list[SignalRecord] = []
        after: str | None = None
        pages = 0

        while len(signals) < max_records and pages < _MAX_PAGES:
            params: dict[str, str | int] = {"limit": min(50, max_records - len(signals))}
            if after:
                params["after"] = after
            if watermark:
                params["startTime"] = watermark

            response = httpx.get(
                f"{_HOOTSUITE_BASE}/messages",
                headers={"Authorization": "Bearer " + self.api_token},
                params=params,
                timeout=20.0,
            )
            response.raise_for_status()
            body = response.json()
            items = body.get("data", [])
            if not items:
                break

            for item in items:
                signals.append(
                    SignalRecord(
                        connector=self.name,
                        entity_type="account",
                        entity_key=item.get("profileName") or item.get("profile", "general"),
                        signal_type="engagement",
                        score=30.0,
                        external_id=item.get("id"),
                        source_url=item.get("permalink"),
                        summary=item.get("text") or "Hootsuite activity",
                        metadata={
                            "profile_id": item.get("profileId"),
                            "published_at": item.get("publishedAt"),
                        },
                    )
                )

            # Advance cursor; Hootsuite uses cursor-based pagination
            paging = body.get("paging", {})
            after = paging.get("cursors", {}).get("after") or paging.get("next")
            pages += 1
            if not after:
                break

        return ConnectorResult(signals=signals[:max_records])

    # ------------------------------------------------------------------
    # CSV fallback path (with schema validation)
    # ------------------------------------------------------------------

    def _fetch_csv(self, *, max_records: int) -> ConnectorResult:
        path = self.csv_path
        with Path(path).open(encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ValueError(f"Hootsuite CSV at '{path}' appears to be empty.")
            _validate_csv_headers(list(reader.fieldnames), path)
            rows = list(reader)

        signals: list[SignalRecord] = []
        for i, row in enumerate(rows[:max_records]):
            row_id = (row.get("id") or "").strip()
            profile = (row.get("profile") or "").strip() or "general"
            score_raw = (row.get("score") or "").strip()
            summary = (row.get("summary") or "").strip() or "Hootsuite CSV fallback"
            url = (row.get("url") or "").strip() or None

            if not row_id:
                LOGGER.warning("Hootsuite CSV row %d missing 'id'; skipping.", i)
                continue

            signals.append(
                SignalRecord(
                    connector=self.name,
                    entity_type="account",
                    entity_key=profile,
                    signal_type="engagement",
                    score=_safe_float(score_raw),
                    external_id=row_id,
                    source_url=url,
                    summary=summary,
                    metadata={"published_at": (row.get("published_at") or "").strip() or None},
                )
            )

        return ConnectorResult(signals=signals)

