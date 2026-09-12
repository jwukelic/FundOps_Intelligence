"""IRS Form 990 connector — queries the BigQuery public dataset.

Uses ``bigquery-public-data.irs_990`` to derive funding-capacity signals for
Salesforce Accounts that represent potential funders.

Two tables are queried:

* ``irs_990`` — regular filers; ``grntstodomgorgs`` is grants to domestic orgs.
* ``irs_990_pf`` — private foundations; ``totchrtblscrptblcmmtmnt`` is charitable
  disbursements including grants.

EIN lookup is preferred when ``FundOps_IRS_EIN__c`` is populated on the Account.
Name-based LIKE fallback is used otherwise.

Strength mapping (log-scaled to 0–100):
  grants < $10k         → 20
  grants $10k–$100k     → 40
  grants $100k–$1M      → 60
  grants $1M–$10M       → 80
  grants > $10M         → 95
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.connectors.bigquery_client import BigQueryClient

# Most recently published year in the public dataset.
_LATEST_YEAR = 2022

# Ordered list of years to try if the latest year has no results.
_FALLBACK_YEARS = [2021, 2020, 2019]

_SOURCE_URL = "https://console.cloud.google.com/bigquery?p=bigquery-public-data&d=irs_990&page=dataset"


def _grants_to_strength(grants: float) -> int:
    """Map dollar amount of grants to a 0–100 signal strength."""
    if grants <= 0:
        return 10
    log = math.log10(max(grants, 1))
    # log10 scale: 3=1k, 4=10k, 5=100k, 6=1M, 7=10M+
    if log < 4:
        return 20
    if log < 5:
        return 40
    if log < 6:
        return 60
    if log < 7:
        return 80
    return 95


class Irs990Connector:
    """Read-only connector against the BigQuery public IRS 990 dataset.

    Accepts the caller's ``BigQueryClient``; the client must be initialised
    with a real GCP project so cross-project queries work.  Pass
    ``store=...`` (in-memory) during tests — ``query`` returns ``[]`` for
    the mock store, so the connector gracefully returns an empty list.
    """

    def __init__(self, bq: "BigQueryClient") -> None:
        self._bq = bq

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_raw_filings(self, account: dict, year: int | None = None) -> list[dict]:
        """Return raw filing rows from the public dataset for *account*.

        Tries EIN first (precise); falls back to account name LIKE.
        Returns an empty list when no match is found or the BQ store is
        the in-memory mock (tests).
        """
        ein = (account.get("FundOps_IRS_EIN__c") or "").strip()
        name = (account.get("Name") or "").strip()
        if not ein and not name:
            return []

        target_year = year or _LATEST_YEAR
        rows = self._query_year(ein, name, target_year)

        # Retry previous years if the primary year has no data.
        if not rows:
            for y in _FALLBACK_YEARS:
                if y == target_year:
                    continue
                rows = self._query_year(ein, name, y)
                if rows:
                    break

        return rows

    def build_signals(self, account: dict, year: int | None = None) -> list[dict]:
        """Return a list of signal dicts (matching ``FundOps_Signal__c`` shape).

        Each dict can be passed to ``SalesforceConnector.upsert_signal``.
        Returns an empty list when no 990 data is found.
        """
        filings = self.fetch_raw_filings(account, year=year)
        if not filings:
            return []

        account_id = account.get("Id", "unknown")
        program = account.get("FundOps_Primary_Program__c", "Unknown")

        signals: list[dict] = []
        for filing in filings[:1]:  # Use most recent filing only.
            grants = float(filing.get("grants_paid", 0) or 0)
            assets = float(filing.get("total_assets", 0) or 0)
            tax_period = str(filing.get("tax_period", ""))
            filing_ein = str(filing.get("ein", ""))
            org_name = str(filing.get("org_name", account.get("Name", "")))

            strength = _grants_to_strength(grants)
            summary = (
                f"IRS 990 ({tax_period}): grants paid ${grants:,.0f}, "
                f"total assets ${assets:,.0f}."
            )
            external_id = f"{account_id}-irs990-{filing_ein}-{tax_period}"

            signals.append(
                {
                    "External_ID__c": external_id,
                    "Account__c": account_id,
                    "Program__c": program,
                    "Signal_Type__c": "FundingCapacity",
                    "Strength__c": strength,
                    "Confidence__c": 80,
                    "Summary__c": summary[:255],
                    "Source_Name__c": "IRS Form 990",
                    "Source_URL__c": _SOURCE_URL,
                    "Observation_Type__c": "PublicRecord",
                    "Raw_Hash__c": external_id,
                }
            )

        return signals

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _query_year(self, ein: str, name: str, year: int) -> list[dict]:
        """Query both 990 and 990-PF tables for the given year."""
        rows = self._query_990(ein, name, year)
        if not rows:
            rows = self._query_990_pf(ein, name, year)
        return rows

    def _query_990(self, ein: str, name: str, year: int) -> list[dict]:
        """Query irs_990 (regular filers) for grants to domestic orgs."""
        where = self._where_clause(ein, name)
        sql = f"""
            SELECT
                ein,
                organization_name AS org_name,
                tax_period,
                CAST(COALESCE(grntstodomgorgs, 0) AS FLOAT64) AS grants_paid,
                CAST(COALESCE(totnetassets, 0) AS FLOAT64) AS total_assets
            FROM `bigquery-public-data.irs_990.irs_990_{year}`
            WHERE {where}
            ORDER BY tax_period DESC
            LIMIT 1
        """
        try:
            return self._bq.query(sql)
        except Exception:  # noqa: BLE001
            return []

    def _query_990_pf(self, ein: str, name: str, year: int) -> list[dict]:
        """Query irs_990_pf (private foundations) for charitable distributions."""
        where = self._where_clause_pf(ein, name)
        sql = f"""
            SELECT
                ein,
                organization_name AS org_name,
                tax_period,
                CAST(COALESCE(totchrtblscrptblcmmtmnt, 0) AS FLOAT64) AS grants_paid,
                CAST(COALESCE(totassetsatendofyear, 0) AS FLOAT64) AS total_assets
            FROM `bigquery-public-data.irs_990.irs_990_pf_{year}`
            WHERE {where}
            ORDER BY tax_period DESC
            LIMIT 1
        """
        try:
            return self._bq.query(sql)
        except Exception:  # noqa: BLE001
            return []

    @staticmethod
    def _where_clause(ein: str, name: str) -> str:
        if ein:
            safe_ein = ein.replace("'", "").replace("-", "")
            return f"ein = '{safe_ein}'"
        safe_name = name.replace("'", "''")
        return f"UPPER(organization_name) LIKE UPPER('%{safe_name}%')"

    @staticmethod
    def _where_clause_pf(ein: str, name: str) -> str:
        if ein:
            safe_ein = ein.replace("'", "").replace("-", "")
            return f"ein = '{safe_ein}'"
        safe_name = name.replace("'", "''")
        return f"UPPER(organization_name) LIKE UPPER('%{safe_name}%')"
