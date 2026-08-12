"""Tests for the BigQuery typed merge helpers in app.storage.

All tests run against the pure-Python helpers (_bq_scalar, _coerce_value,
and the BigQueryWarehouse methods that use them) without requiring a live
BigQuery connection.  BigQueryWarehouse is exercised through a fake client
that records every DML call so we can assert on query shape and parameter
types without needing GCP credentials.
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from app.models import AuditEvent, ContentRecord, OpportunityRecord, ScoreCard, SignalRecord
from app.storage import BigQueryWarehouse, _BQ_TYPES, _bq_scalar, _coerce_value


# ---------------------------------------------------------------------------
# _coerce_value unit tests
# ---------------------------------------------------------------------------

class TestCoerceValue:
    def test_string_passthrough(self):
        assert _coerce_value("hello", "STRING") == "hello"

    def test_dict_to_json_string(self):
        result = _coerce_value({"k": 1}, "STRING")
        assert json.loads(result) == {"k": 1}

    def test_list_to_json_string(self):
        result = _coerce_value(["a", "b"], "STRING")
        assert json.loads(result) == ["a", "b"]

    def test_float64(self):
        assert _coerce_value("3.14", "FLOAT64") == 3.14
        assert isinstance(_coerce_value(7, "FLOAT64"), float)

    def test_bool(self):
        assert _coerce_value(True, "BOOL") is True
        assert _coerce_value(0, "BOOL") is False

    def test_timestamp_datetime(self):
        dt = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
        assert _coerce_value(dt, "TIMESTAMP") == dt.isoformat()

    def test_timestamp_string_passthrough(self):
        s = "2026-01-15T12:00:00+00:00"
        assert _coerce_value(s, "TIMESTAMP") == s

    def test_date_object(self):
        d = date(2026, 9, 1)
        assert _coerce_value(d, "DATE") == "2026-09-01"

    def test_date_string_passthrough(self):
        assert _coerce_value("2026-09-01", "DATE") == "2026-09-01"

    def test_none_returns_none(self):
        assert _coerce_value(None, "STRING") is None
        assert _coerce_value(None, "FLOAT64") is None


# ---------------------------------------------------------------------------
# _bq_scalar unit tests
# ---------------------------------------------------------------------------

class TestBqScalar:
    def test_known_field_uses_declared_type(self):
        param = _bq_scalar("signals", "score", 42.0)
        assert param.type_ == "FLOAT64"
        assert param.value == 42.0

    def test_known_bool_field(self):
        param = _bq_scalar("content_index", "approved", True)
        assert param.type_ == "BOOL"
        assert param.value is True

    def test_known_timestamp_field(self):
        dt = datetime(2026, 6, 1, tzinfo=UTC)
        param = _bq_scalar("signals", "observed_at", dt)
        assert param.type_ == "TIMESTAMP"
        assert param.value == dt.isoformat()

    def test_metadata_serialised_to_string(self):
        param = _bq_scalar("signals", "metadata", {"key": "val"})
        assert param.type_ == "STRING"
        assert json.loads(param.value) == {"key": "val"}

    def test_unknown_field_defaults_to_string(self):
        param = _bq_scalar("signals", "nonexistent_field", "x")
        assert param.type_ == "STRING"

    def test_array_field_serialised_to_string(self):
        param = _bq_scalar("scores", "reasons", ["good fit", "high intent"])
        assert param.type_ == "STRING"
        assert json.loads(param.value) == ["good fit", "high intent"]


# ---------------------------------------------------------------------------
# _BQ_TYPES coverage: every table+field pair that the warehouse touches
# ---------------------------------------------------------------------------

class TestBqTypesMapping:
    @pytest.mark.parametrize("table,field,expected_type", [
        ("signals", "score", "FLOAT64"),
        ("signals", "observed_at", "TIMESTAMP"),
        ("signals", "metadata", "STRING"),
        ("scores", "total_score", "FLOAT64"),
        ("scores", "scored_at", "TIMESTAMP"),
        ("scores", "reasons", "STRING"),
        ("content_index", "approved", "BOOL"),
        ("content_index", "updated_at", "TIMESTAMP"),
        ("opportunity_intake", "amount", "FLOAT64"),
        ("opportunity_intake", "close_date", "DATE"),
        ("opportunity_intake", "updated_at", "TIMESTAMP"),
        ("audit_log", "changed_at", "TIMESTAMP"),
        ("sync_state", "updated_at", "TIMESTAMP"),
        ("ai_cache", "updated_at", "TIMESTAMP"),
    ])
    def test_type_registered(self, table, field, expected_type):
        assert _BQ_TYPES[(table, field)] == expected_type


# ---------------------------------------------------------------------------
# BigQueryWarehouse._typed_merge / _typed_append integration (mock client)
# ---------------------------------------------------------------------------

def _make_warehouse() -> tuple[BigQueryWarehouse, MagicMock]:
    """Return a warehouse backed by a mock BQ client."""
    wh = BigQueryWarehouse.__new__(BigQueryWarehouse)
    wh.project_id = "test-project"
    wh.dataset = "fundops"
    mock_client = MagicMock()
    # Simulate job with dml_stats showing an insert
    mock_job = MagicMock()
    mock_job.dml_stats.inserted_row_count = 1
    mock_client.query.return_value = mock_job
    wh.client = mock_client
    return wh, mock_client


class TestTypedMerge:
    def test_merge_query_contains_merge_keyword(self):
        wh, mock_client = _make_warehouse()
        signal = SignalRecord(
            connector="salesforce",
            entity_type="account",
            entity_key="acme",
            signal_type="fit",
            score=40.0,
            signal_id="sig-001",
            observed_at=datetime(2026, 6, 1, tzinfo=UTC),
        )
        from dataclasses import asdict
        wh._typed_merge("signals", "signal_id", asdict(signal))
        query_text: str = mock_client.query.call_args[0][0]
        assert "MERGE" in query_text
        assert "WHEN MATCHED THEN" in query_text
        assert "WHEN NOT MATCHED THEN" in query_text

    def test_merge_uses_typed_parameters(self):
        wh, mock_client = _make_warehouse()
        signal = SignalRecord(
            connector="sf",
            entity_type="account",
            entity_key="x",
            signal_type="fit",
            score=99.5,
            signal_id="sig-x",
            observed_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        from dataclasses import asdict
        wh._typed_merge("signals", "signal_id", asdict(signal))
        job_config = mock_client.query.call_args[1]["job_config"]
        params_by_name: dict[str, Any] = {p.name: p for p in job_config.query_parameters}
        assert params_by_name["score"].type_ == "FLOAT64"
        assert params_by_name["observed_at"].type_ == "TIMESTAMP"
        assert params_by_name["metadata"].type_ == "STRING"

    def test_merge_returns_true_on_insert(self):
        wh, _ = _make_warehouse()
        result = wh._typed_merge("ai_cache", "input_hash", {
            "input_hash": "abc",
            "response_json": "{}",
            "updated_at": datetime(2026, 1, 1, tzinfo=UTC),
        })
        assert result is True

    def test_upsert_score_includes_scored_at(self):
        wh, mock_client = _make_warehouse()
        sc = ScoreCard(
            entity_key="acme",
            entity_type="account",
            total_score=75.0,
            priority="high",
            reasons=["fit"],
            supporting_sources=["sf"],
        )
        wh.upsert_score(sc)
        job_config = mock_client.query.call_args[1]["job_config"]
        params_by_name = {p.name: p for p in job_config.query_parameters}
        assert "scored_at" in params_by_name
        assert params_by_name["scored_at"].type_ == "TIMESTAMP"
        assert params_by_name["total_score"].type_ == "FLOAT64"

    def test_upsert_content_bool_approved(self):
        wh, mock_client = _make_warehouse()
        content = ContentRecord(
            content_id="c1",
            connector="google_drive",
            entity_key="acme",
            title="Memo",
            text="Text",
            approved=True,
            updated_at=datetime(2026, 3, 1, tzinfo=UTC),
        )
        wh.upsert_content(content)
        job_config = mock_client.query.call_args[1]["job_config"]
        params_by_name = {p.name: p for p in job_config.query_parameters}
        assert params_by_name["approved"].type_ == "BOOL"

    def test_upsert_opportunity_float_and_date(self):
        wh, mock_client = _make_warehouse()
        opp = OpportunityRecord(
            external_id="opp-1",
            account_key="acme",
            name="Gift",
            amount=5000.0,
            close_date="2026-09-01",
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        wh.upsert_opportunity_intake(opp)
        job_config = mock_client.query.call_args[1]["job_config"]
        params_by_name = {p.name: p for p in job_config.query_parameters}
        assert params_by_name["amount"].type_ == "FLOAT64"
        assert params_by_name["close_date"].type_ == "DATE"


class TestTypedAppend:
    def test_append_uses_insert_not_insert_rows_json(self):
        wh, mock_client = _make_warehouse()
        payload = {
            "connector_name": "sf",
            "status": "ok",
            "error_message": None,
            "ran_at": datetime(2026, 1, 1, tzinfo=UTC),
        }
        wh._typed_append("connector_runs", payload)
        # Should NOT have called insert_rows_json
        mock_client.insert_rows_json.assert_not_called()
        # Should have called query
        mock_client.query.assert_called_once()
        query_text: str = mock_client.query.call_args[0][0]
        assert "INSERT INTO" in query_text

    def test_append_connector_run_ran_at_typed(self):
        wh, mock_client = _make_warehouse()
        payload = {
            "connector_name": "sf",
            "status": "ok",
            "error_message": None,
            "ran_at": datetime(2026, 1, 1, tzinfo=UTC),
        }
        wh.append_connector_run(payload)
        job_config = mock_client.query.call_args[1]["job_config"]
        params_by_name = {p.name: p for p in job_config.query_parameters}
        assert params_by_name["ran_at"].type_ == "TIMESTAMP"

    def test_append_audit_changed_at_typed(self):
        wh, mock_client = _make_warehouse()
        event = AuditEvent(
            target_type="Account",
            target_id="001",
            action="update",
            before={"score": 10},
            after={"score": 20},
            changed_at=datetime(2026, 5, 1, tzinfo=UTC),
        )
        wh.append_audit(event)
        job_config = mock_client.query.call_args[1]["job_config"]
        params_by_name = {p.name: p for p in job_config.query_parameters}
        assert params_by_name["changed_at"].type_ == "TIMESTAMP"
        # before/after should be JSON-serialised strings
        assert params_by_name["before"].type_ == "STRING"
        assert json.loads(params_by_name["before"].value) == {"score": 10}

    def test_no_client_append_is_noop(self):
        wh = BigQueryWarehouse.__new__(BigQueryWarehouse)
        wh.project_id = ""
        wh.dataset = "fundops"
        wh.client = None
        # Should not raise
        wh._typed_append("connector_runs", {"connector_name": "x", "status": "ok", "ran_at": datetime.now(UTC)})
