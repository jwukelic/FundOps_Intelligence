from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from google.cloud import bigquery

from app.models import AuditEvent, ContentRecord, OpportunityRecord, ScoreCard, SignalRecord


SQL_DIR = Path(__file__).resolve().parent / "sql"


def load_sql(name: str) -> str:
    return (SQL_DIR / name).read_text(encoding="utf-8")


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
            query_parameters=[bigquery.ScalarQueryParameter("connector_name", "STRING", connector_name)]
        )
        rows = list(self.client.query(query, job_config=config).result())
        return rows[0]["watermark"] if rows else None

    def set_sync_state(self, connector_name: str, watermark: str) -> None:
        if not self.client:
            return
        query = f"""
        MERGE `{self._table('sync_state')}` AS target
        USING (SELECT @connector_name AS connector_name, @watermark AS watermark, CURRENT_TIMESTAMP() AS updated_at) AS source
        ON target.connector_name = source.connector_name
        WHEN MATCHED THEN UPDATE SET watermark = source.watermark, updated_at = source.updated_at
        WHEN NOT MATCHED THEN INSERT (connector_name, watermark, updated_at) VALUES (source.connector_name, source.watermark, source.updated_at)
        """
        config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("connector_name", "STRING", connector_name),
                bigquery.ScalarQueryParameter("watermark", "STRING", watermark),
            ]
        )
        self.client.query(query, job_config=config).result()

    def upsert_signal(self, signal: SignalRecord) -> bool:
        return self._upsert_by_id("signals", "signal_id", signal.signal_id, asdict(signal))

    def list_signals_for_entity(self, entity_key: str) -> list[SignalRecord]:
        if not self.client:
            return []
        query = f"SELECT * FROM `{self._table('signals')}` WHERE entity_key=@entity_key"
        config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("entity_key", "STRING", entity_key)]
        )
        rows = self.client.query(query, job_config=config).result()
        return [SignalRecord(**dict(row.items())) for row in rows]

    def upsert_score(self, scorecard: ScoreCard) -> None:
        payload = asdict(scorecard) | {"score_id": f"{scorecard.entity_type}:{scorecard.entity_key}"}
        self._upsert_by_id("scores", "score_id", payload["score_id"], payload)

    def get_ai_cache(self, input_hash: str) -> dict[str, Any] | None:
        if not self.client:
            return None
        query = f"SELECT response_json FROM `{self._table('ai_cache')}` WHERE input_hash=@input_hash LIMIT 1"
        config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("input_hash", "STRING", input_hash)]
        )
        rows = list(self.client.query(query, job_config=config).result())
        return json.loads(rows[0]["response_json"]) if rows else None

    def put_ai_cache(self, input_hash: str, payload: dict[str, Any]) -> None:
        row = {"input_hash": input_hash, "response_json": json.dumps(payload), "updated_at": datetime.now(UTC).isoformat()}
        self._upsert_by_id("ai_cache", "input_hash", input_hash, row)

    def upsert_content(self, content: ContentRecord) -> None:
        self._upsert_by_id("content_index", "content_id", content.content_id, asdict(content))

    def list_content(self, entity_key: str) -> list[ContentRecord]:
        if not self.client:
            return []
        query = f"SELECT * FROM `{self._table('content_index')}` WHERE entity_key=@entity_key AND approved=TRUE"
        config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("entity_key", "STRING", entity_key)]
        )
        rows = self.client.query(query, job_config=config).result()
        return [ContentRecord(**dict(row.items())) for row in rows]

    def upsert_opportunity_intake(self, opportunity: OpportunityRecord) -> None:
        self._upsert_by_id("opportunity_intake", "external_id", opportunity.external_id, asdict(opportunity))

    def list_opportunities(self) -> list[OpportunityRecord]:
        if not self.client:
            return []
        rows = self.client.query(f"SELECT * FROM `{self._table('opportunity_intake')}`").result()
        return [OpportunityRecord(**dict(row.items())) for row in rows]

    def append_audit(self, event: AuditEvent) -> None:
        if not self.client:
            return
        self.client.insert_rows_json(self._table("audit_log"), [asdict(event)])

    def append_connector_run(self, payload: dict[str, Any]) -> None:
        if not self.client:
            return
        self.client.insert_rows_json(self._table("connector_runs"), [payload])

    def _upsert_by_id(self, table_name: str, id_field: str, id_value: str, payload: dict[str, Any]) -> bool:
        if not self.client:
            return False
        query = f"SELECT {id_field} FROM `{self._table(table_name)}` WHERE {id_field}=@id_value LIMIT 1"
        config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("id_value", "STRING", id_value)]
        )
        exists = bool(list(self.client.query(query, job_config=config).result()))
        if exists:
            assignments = ", ".join(f"{key}=@{key}" for key in payload if key != id_field)
            update_query = f"UPDATE `{self._table(table_name)}` SET {assignments} WHERE {id_field}=@{id_field}"
            params = [bigquery.ScalarQueryParameter(key, "STRING", json.dumps(value) if isinstance(value, (dict, list)) else value) for key, value in payload.items()]
            self.client.query(update_query, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()
            return False
        self.client.insert_rows_json(self._table(table_name), [self._json_safe(payload)])
        return True

    @staticmethod
    def _json_safe(payload: dict[str, Any]) -> dict[str, Any]:
        safe: dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, datetime):
                safe[key] = value.isoformat()
            elif isinstance(value, (dict, list)):
                safe[key] = json.dumps(value)
            else:
                safe[key] = value
        return safe

