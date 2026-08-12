from datetime import datetime, timezone

from app.connectors.bigquery_client import BigQueryClient, InMemoryBigQueryStore
from app.models import Signal
from app.services.bigquery_cache import BigQueryAICache
from app.services.bigquery_writer import BigQueryWriter


def _make_bq() -> tuple[BigQueryClient, InMemoryBigQueryStore]:
    store = InMemoryBigQueryStore()
    bq = BigQueryClient(project_id="test-project", store=store)
    return bq, store


# ---------------------------------------------------------------------------
# BigQueryAICache
# ---------------------------------------------------------------------------


def test_bq_cache_miss_returns_none():
    bq, _ = _make_bq()
    cache = BigQueryAICache(bq)
    assert cache.get("nonexistent-key") is None


def test_bq_cache_put_and_hit():
    bq, _ = _make_bq()
    cache = BigQueryAICache(bq)
    payload = {"summary": "Grant for youth programs", "confidence": 0.9}
    cache.put("key1", "hash1", "gpt-5-mini", payload)
    result = cache.get("key1")
    assert result == payload


def test_bq_cache_returns_latest_for_same_key():
    bq, store = _make_bq()
    cache = BigQueryAICache(bq)
    cache.put("key1", "hash1", "gpt-5-mini", {"v": 1})
    cache.put("key1", "hash1", "gpt-5-mini", {"v": 2})
    result = cache.get("key1")
    assert result == {"v": 2}


def test_bq_cache_isolates_different_keys():
    bq, _ = _make_bq()
    cache = BigQueryAICache(bq)
    cache.put("keyA", "hA", "gpt-5-mini", {"a": True})
    cache.put("keyB", "hB", "gpt-5-mini", {"b": True})
    assert cache.get("keyA") == {"a": True}
    assert cache.get("keyB") == {"b": True}


# ---------------------------------------------------------------------------
# BigQueryWriter
# ---------------------------------------------------------------------------


def test_bq_writer_write_score_inserts_row():
    bq, store = _make_bq()
    writer = BigQueryWriter(bq)
    writer.write_score(
        account_id="001",
        program="Believe in Me",
        score=76,
        priority="High",
        components={
            "mission_and_program_fit": 80.0,
            "funding_capacity": 55.0,
            "timing_and_current_intent": 60.0,
            "relationship_access": 40.0,
            "internal_readiness": 65.0,
            "engagement_momentum": 50.0,
            "data_confidence": 70.0,
        },
        explanation="Program: Believe in Me. Priority score 76 (High).",
    )
    rows = store.query_table("scores")
    assert len(rows) == 1
    assert rows[0]["salesforce_account_id"] == "001"
    assert rows[0]["total_score"] == 76
    assert rows[0]["priority"] == "High"


def test_bq_writer_write_signal_inserts_row():
    bq, store = _make_bq()
    writer = BigQueryWriter(bq)
    now = datetime.now(timezone.utc)
    signal = Signal(
        external_id="001-priority-20260101",
        account_id="001",
        program="Cougs 4 Kids",
        signal_type="PriorityScore",
        strength=65,
        confidence=70,
        summary="Priority Medium from deterministic score.",
        source_name="FundOps Scoring",
        source_url="internal://fundops/scoring",
        observed_at=now,
        raw_hash="abc123",
    )
    writer.write_signal(signal)
    rows = store.query_table("signals")
    assert len(rows) == 1
    assert rows[0]["external_id"] == "001-priority-20260101"
    assert rows[0]["strength"] == 65


def test_bq_writer_write_audit_inserts_row():
    bq, store = _make_bq()
    writer = BigQueryWriter(bq)
    writer.write_audit("Account", "001", "FundOps_Score__c", None, 76)
    rows = store.query_table("audit_log")
    assert len(rows) == 1
    assert rows[0]["entity_id"] == "001"
    assert rows[0]["new_value"] == "76"
    assert rows[0]["old_value"] == ""


def test_bq_writer_write_connector_run():
    bq, store = _make_bq()
    writer = BigQueryWriter(bq)
    writer.write_connector_run("pipeline", "success", 3, 0, "")
    rows = store.query_table("connector_runs")
    assert len(rows) == 1
    assert rows[0]["connector"] == "pipeline"
    assert rows[0]["status"] == "success"
    assert rows[0]["processed_count"] == 3


# ---------------------------------------------------------------------------
# Pipeline integration with BigQueryWriter
# ---------------------------------------------------------------------------


def test_pipeline_writes_scores_and_signals_to_bq():
    from app.config import Settings
    from app.connectors.google_sheets import GoogleSheetsConnector
    from app.connectors.salesforce import InMemorySalesforceStore, SalesforceConnector
    from app.pipeline import run_pipeline

    sf_store = InMemorySalesforceStore(
        accounts={"001": {"Id": "001", "FundOps_Enabled__c": True, "FundOps_Primary_Program__c": "iLevelUP"}},
        opportunities={},
        tasks={},
        signals={},
    )
    bq, bq_store = _make_bq()
    writer = BigQueryWriter(bq)

    result = run_pipeline(
        settings=Settings(fundops_max_accounts=5),
        salesforce=SalesforceConnector(sf_store),
        sheets=GoogleSheetsConnector(),
        bq_writer=writer,
    )

    assert result.scored_accounts == 1
    assert len(bq_store.query_table("scores")) == 1
    assert len(bq_store.query_table("signals")) == 1
    assert len(bq_store.query_table("audit_log")) == 1
    assert len(bq_store.query_table("connector_runs")) == 1
