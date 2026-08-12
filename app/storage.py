from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from google.cloud import bigquery

from app.models import AuditEvent, ContentRecord, OpportunityRecord, ScoreCard, SignalRecord


SQL_DIR = Path(__file__).resolve().parent / "sql"

# Maps (table_name, field_name) -> BigQuery scalar type string used in QueryParameter.
# ARRAY and JSON fields are serialised to STRING; BOOL, FLOAT64, TIMESTAMP, DATE get
# their native BQ types so the query engine can enforce type safety without casting.
_BQ_TYPES: dict[tuple[str, str], str] = {
    # signals
    ("signals", "signal_id"): "STRING",
    ("signals", "connector"): "STRING",
    ("signals", "entity_type"): "STRING",
    ("signals", "entity_key"): "STRING",
    ("signals", "signal_type"): "STRING",
    ("signals", "score"): "FLOAT64",
    ("signals", "external_id"): "STRING",
    ("signals", "source_id"): "STRING",
    ("signals", "source_url"): "STRING",
    ("signals", "summary"): "STRING",
    ("signals", "raw_text"): "STRING",
    ("signals", "metadata"): "STRING",   # JSON serialised
    ("signals", "observed_at"): "TIMESTAMP",
    ("signals", "raw_hash"): "STRING",
    # scores
    ("scores", "score_id"): "STRING",
    ("scores", "entity_key"): "STRING",
    ("scores", "entity_type"): "STRING",
    ("scores", "total_score"): "FLOAT64",
    ("scores", "priority"): "STRING",
    ("scores", "reasons"): "STRING",          # JSON-serialised ARRAY
    ("scores", "supporting_sources"): "STRING",  # JSON-serialised ARRAY
    ("scores", "scored_at"): "TIMESTAMP",
    # sync_state
    ("sync_state", "connector_name"): "STRING",
    ("sync_state", "watermark"): "STRING",
    ("sync_state", "updated_at"): "TIMESTAMP",
    # ai_cache
    ("ai_cache", "input_hash"): "STRING",
    ("ai_cache", "response_json"): "STRING",
    ("ai_cache", "updated_at"): "TIMESTAMP",
    # content_index
    ("content_index", "content_id"): "STRING",
    ("content_index", "connector"): "STRING",
    ("content_index", "entity_key"): "STRING",
    ("content_index", "title"): "STRING",
    ("content_index", "text"): "STRING",
    ("content_index", "approved"): "BOOL",
    ("content_index", "source_url"): "STRING",
    ("content_index", "metadata"): "STRING",   # JSON serialised
    ("content_index", "updated_at"): "TIMESTAMP",
    # opportunity_intake
    ("opportunity_intake", "external_id"): "STRING",
    ("opportunity_intake", "account_key"): "STRING",
    ("opportunity_intake", "name"): "STRING",
    ("opportunity_intake", "amount"): "FLOAT64",
    ("opportunity_intake", "stage_name"): "STRING",
    ("opportunity_intake", "close_date"): "DATE",
    ("opportunity_intake", "source_url"): "STRING",
    ("opportunity_intake", "metadata"): "STRING",  # JSON serialised
    ("opportunity_intake", "updated_at"): "TIMESTAMP",
    # audit_log (append-only, listed for completeness)
    ("audit_log", "target_type"): "STRING",
    ("audit_log", "target_id"): "STRING",
    ("audit_log", "action"): "STRING",
    ("audit_log", "before"): "STRING",   # JSON serialised
    ("audit_log", "after"): "STRING",    # JSON serialised
    ("audit_log", "changed_at"): "TIMESTAMP",
    # connector_runs (append-only)
    ("connector_runs", "connector_name"): "STRING",
    ("connector_runs", "status"): "STRING",
    ("connector_runs", "error_message"): "STRING",
    ("connector_runs", "ran_at"): "TIMESTAMP",
}


def load_sql(name: str) -> str:
    return (SQL_DIR / name).read_text(encoding="utf-8")


def _bq_scalar(table: str, field: str, value: Any) -> bigquery.ScalarQueryParameter:
    """Return a typed ScalarQueryParameter for *field* in *table*."""
    bq_type = _BQ_TYPES.get((table, field), "STRING")
    coerced = _coerce_value(value, bq_type)
    return bigquery.ScalarQueryParameter(field, bq_type, coerced)


def _coerce_value(value: Any, bq_type: str) -> Any:
    """Coerce *value* to the Python type expected by the BigQuery client for *bq_type*."""
    if value is None:
        return None
    if bq_type == "STRING":
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return str(value) if not isinstance(value, str) else value
    if bq_type == "FLOAT64":
        return float(value)
    if bq_type == "BOOL":
        return bool(value)
    if bq_type == "TIMESTAMP":
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)
    if bq_type == "DATE":
        if isinstance(value, date):
            return value.isoformat()
        return str(value) if value else None
    return value


class InMemoryWarehouse:
    def __init__(self) -> None:
        self.signals: dict[str, SignalRecord] = {}
        self.scores: dict[str, ScoreCard] = {}
        self.sync_state: dict[str, str] = {}
        self.ai_cache: dict[str, dict[str, Any]] = {}
        self.content_index: dict[str, ContentRecord] = {}
        self.audit_log: list[AuditEvent] = []
        self.connector_runs: list[dict[str, Any]] = []
        self.opportunity_intake: dict[str, OpportunityRecord] = {}

    def ensure_tables(self) -> None:
        return None

    def get_sync_state(self, connector_name: str) -> str | None:
        return self.sync_state.get(connector_name)

    def set_sync_state(self, connector_name: str, watermark: str) -> None:
        self.sync_state[connector_name] = watermark

    def upsert_signal(self, signal: SignalRecord) -> bool:
        is_new = signal.signal_id not in self.signals
        self.signals[signal.signal_id] = signal
        return is_new

    def list_signals_for_entity(self, entity_key: str) -> list[SignalRecord]:
        return [signal for signal in self.signals.values() if signal.entity_key == entity_key]

    def upsert_score(self, scorecard: ScoreCard) -> None:
        self.scores[f"{scorecard.entity_type}:{scorecard.entity_key}"] = scorecard

    def get_ai_cache(self, input_hash: str) -> dict[str, Any] | None:
        return self.ai_cache.get(input_hash)

    def put_ai_cache(self, input_hash: str, payload: dict[str, Any]) -> None:
        self.ai_cache[input_hash] = payload

    def upsert_content(self, content: ContentRecord) -> None:
        self.content_index[content.content_id] = content

    def list_content(self, entity_key: str) -> list[ContentRecord]:
        return [item for item in self.content_index.values() if item.entity_key == entity_key and item.approved]

    def upsert_opportunity_intake(self, opportunity: OpportunityRecord) -> None:
        self.opportunity_intake[opportunity.external_id] = opportunity

    def list_opportunities(self) -> list[OpportunityRecord]:
        return list(self.opportunity_intake.values())

    def append_audit(self, event: AuditEvent) -> None:
        self.audit_log.append(event)

    def append_connector_run(self, payload: dict[str, Any]) -> None:
        self.connector_runs.append(payload)


class BigQueryWarehouse:
    def __init__(self, project_id: str, dataset: str) -> None:
        self.project_id = project_id
        self.dataset = dataset
        self.client = bigquery.Client(project=project_id) if project_id else None

    def _table(self, table_name: str) -> str:
        return f"{self.project_id}.{self.dataset}.{table_name}"

    def ensure_tables(self) -> None:
        if not self.client:
            return
        for statement in [part.strip() for part in load_sql("create_tables.sql").split(";\n") if part.strip()]:
            self.client.query(statement).result()

    def get_sync_state(self, connector_name: str) -> str | None:
        if not self.client:
            return None
        query = f"SELECT watermark FROM `{self._table('sync_state')}` WHERE connector_name=@connector_name LIMIT 1"
        config = bigquery.QueryJobConfig(
            query_parameters=[_bq_scalar("sync_state", "connector_name", connector_name)]
        )
        rows = list(self.client.query(query, job_config=config).result())
        return rows[0]["watermark"] if rows else None

    def set_sync_state(self, connector_name: str, watermark: str) -> None:
        if not self.client:
            return
        row = {"connector_name": connector_name, "watermark": watermark, "updated_at": datetime.now(UTC)}
        self._typed_merge("sync_state", "connector_name", row)

    def upsert_signal(self, signal: SignalRecord) -> bool:
        return self._typed_merge("signals", "signal_id", asdict(signal))

    def list_signals_for_entity(self, entity_key: str) -> list[SignalRecord]:
        if not self.client:
            return []
        query = f"SELECT * FROM `{self._table('signals')}` WHERE entity_key=@entity_key"
        config = bigquery.QueryJobConfig(
            query_parameters=[_bq_scalar("signals", "entity_key", entity_key)]
        )
        rows = self.client.query(query, job_config=config).result()
        return [SignalRecord(**dict(row.items())) for row in rows]

    def upsert_score(self, scorecard: ScoreCard) -> None:
        payload = asdict(scorecard) | {
            "score_id": f"{scorecard.entity_type}:{scorecard.entity_key}",
            "scored_at": datetime.now(UTC),
        }
        self._typed_merge("scores", "score_id", payload)

    def get_ai_cache(self, input_hash: str) -> dict[str, Any] | None:
        if not self.client:
            return None
        query = f"SELECT response_json FROM `{self._table('ai_cache')}` WHERE input_hash=@input_hash LIMIT 1"
        config = bigquery.QueryJobConfig(
            query_parameters=[_bq_scalar("ai_cache", "input_hash", input_hash)]
        )
        rows = list(self.client.query(query, job_config=config).result())
        return json.loads(rows[0]["response_json"]) if rows else None

    def put_ai_cache(self, input_hash: str, payload: dict[str, Any]) -> None:
        row = {"input_hash": input_hash, "response_json": json.dumps(payload), "updated_at": datetime.now(UTC)}
        self._typed_merge("ai_cache", "input_hash", row)

    def upsert_content(self, content: ContentRecord) -> None:
        self._typed_merge("content_index", "content_id", asdict(content))

    def list_content(self, entity_key: str) -> list[ContentRecord]:
        if not self.client:
            return []
        query = f"SELECT * FROM `{self._table('content_index')}` WHERE entity_key=@entity_key AND approved=TRUE"
        config = bigquery.QueryJobConfig(
            query_parameters=[_bq_scalar("content_index", "entity_key", entity_key)]
        )
        rows = self.client.query(query, job_config=config).result()
        return [ContentRecord(**dict(row.items())) for row in rows]

    def upsert_opportunity_intake(self, opportunity: OpportunityRecord) -> None:
        self._typed_merge("opportunity_intake", "external_id", asdict(opportunity))

    def list_opportunities(self) -> list[OpportunityRecord]:
        if not self.client:
            return []
        rows = self.client.query(f"SELECT * FROM `{self._table('opportunity_intake')}`").result()
        return [OpportunityRecord(**dict(row.items())) for row in rows]

    def append_audit(self, event: AuditEvent) -> None:
        if not self.client:
            return
        self._typed_append("audit_log", asdict(event))

    def append_connector_run(self, payload: dict[str, Any]) -> None:
        if not self.client:
            return
        self._typed_append("connector_runs", payload)

    # ------------------------------------------------------------------
    # Core typed helpers
    # ------------------------------------------------------------------

    def _typed_merge(self, table_name: str, id_field: str, payload: dict[str, Any]) -> bool:
        """Atomic MERGE upsert with per-field typed query parameters.

        Returns True when the row did not previously exist (INSERT branch),
        False when it was updated (MATCHED branch).  When the BigQuery client
        is not configured, returns False without raising.
        """
        if not self.client:
            return False

        fields = list(payload.keys())
        non_id_fields = [f for f in fields if f != id_field]

        # Build the VALUES list for the USING clause: (@field AS field, ...)
        source_cols = ", ".join(f"@{f} AS {f}" for f in fields)
        # SET clause: col = source.col for every non-key field
        set_clause = ", ".join(f"target.{f} = source.{f}" for f in non_id_fields)
        # INSERT column/value lists
        insert_cols = ", ".join(fields)
        insert_vals = ", ".join(f"source.{f}" for f in fields)

        query = f"""
        MERGE `{self._table(table_name)}` AS target
        USING (SELECT {source_cols}) AS source
        ON target.{id_field} = source.{id_field}
        WHEN MATCHED THEN
          UPDATE SET {set_clause}
        WHEN NOT MATCHED THEN
          INSERT ({insert_cols}) VALUES ({insert_vals})
        """
        params = [_bq_scalar(table_name, field, payload[field]) for field in fields]
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        job = self.client.query(query, job_config=job_config)
        job.result()
        # num_dml_affected_rows == 1 for both branches; use DML stats to detect insert
        stats = job.dml_stats
        return bool(stats and stats.inserted_row_count > 0)

    def _typed_append(self, table_name: str, payload: dict[str, Any]) -> None:
        """INSERT a single row into an append-only table using typed parameters.

        Uses a parameterised INSERT rather than the streaming insert API so that
        all values are coerced to their declared column types before they reach
        BigQuery, avoiding silent type mismatches in audit_log / connector_runs.
        """
        if not self.client:
            return

        fields = list(payload.keys())
        col_list = ", ".join(fields)
        val_list = ", ".join(f"@{f}" for f in fields)
        query = f"INSERT INTO `{self._table(table_name)}` ({col_list}) VALUES ({val_list})"
        params = [_bq_scalar(table_name, field, payload[field]) for field in fields]
        self.client.query(query, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()

