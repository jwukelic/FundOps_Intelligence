"""Tests for the IRS 990 connector."""

from app.connectors.bigquery_client import BigQueryClient, InMemoryBigQueryStore
from app.connectors.irs990 import Irs990Connector, _grants_to_strength


# ---------------------------------------------------------------------------
# Strength mapping
# ---------------------------------------------------------------------------


def test_strength_zero_grants():
    assert _grants_to_strength(0) == 10


def test_strength_small_grants():
    assert _grants_to_strength(5_000) == 20


def test_strength_medium_grants():
    assert _grants_to_strength(50_000) == 40


def test_strength_large_grants():
    assert _grants_to_strength(500_000) == 60


def test_strength_very_large_grants():
    assert _grants_to_strength(5_000_000) == 80


def test_strength_mega_grants():
    assert _grants_to_strength(50_000_000) == 95


# ---------------------------------------------------------------------------
# build_signals with in-memory BQ (query returns [])
# ---------------------------------------------------------------------------


def _make_connector() -> Irs990Connector:
    store = InMemoryBigQueryStore()
    bq = BigQueryClient(project_id="test-project", store=store)
    return Irs990Connector(bq)


def test_build_signals_no_name_or_ein_returns_empty():
    conn = _make_connector()
    signals = conn.build_signals({"Id": "acc1"})
    assert signals == []


def test_build_signals_mock_bq_returns_empty():
    """In-memory BQ mock returns [] for any query; connector handles this gracefully."""
    conn = _make_connector()
    signals = conn.build_signals({"Id": "acc1", "Name": "Acme Foundation"})
    assert signals == []


def test_fetch_raw_filings_empty_store():
    conn = _make_connector()
    rows = conn.fetch_raw_filings({"Id": "acc1", "Name": "Acme Foundation"})
    assert rows == []


# ---------------------------------------------------------------------------
# where-clause helpers
# ---------------------------------------------------------------------------


def test_where_clause_prefers_ein():
    clause = Irs990Connector._where_clause("12-3456789", "Acme")
    assert "123456789" in clause
    assert "Acme" not in clause


def test_where_clause_falls_back_to_name():
    clause = Irs990Connector._where_clause("", "Acme Foundation")
    assert "Acme Foundation" in clause


def test_where_clause_strips_dashes_from_ein():
    clause = Irs990Connector._where_clause("12-3456789", "")
    assert "-" not in clause


def test_where_clause_escapes_single_quote_in_name():
    clause = Irs990Connector._where_clause("", "O'Brien Foundation")
    assert "O''Brien" in clause


# ---------------------------------------------------------------------------
# Pipeline integration: IRS 990 connector wired into run_pipeline
# ---------------------------------------------------------------------------


def test_pipeline_with_irs990_connector_no_crash():
    """Pipeline runs without error when irs990 connector returns empty signals."""
    from app.connectors.google_sheets import GoogleSheetsConnector
    from app.connectors.salesforce import InMemorySalesforceStore, SalesforceConnector
    from app.config import Settings
    from app.pipeline import run_pipeline

    store = InMemorySalesforceStore(
        accounts={
            "acc1": {
                "Id": "acc1",
                "FundOps_Enabled__c": True,
                "Name": "Test Foundation",
                "FundOps_Primary_Program__c": "Believe in Me",
            }
        },
        opportunities={},
        tasks={},
        signals={},
    )
    sf = SalesforceConnector(store=store)
    sheets = GoogleSheetsConnector()
    conn = _make_connector()

    result = run_pipeline(
        settings=Settings(fundops_project_id=""),
        salesforce=sf,
        sheets=sheets,
        irs990=conn,
    )
    assert result.scored_accounts == 1
    assert not result.errors
