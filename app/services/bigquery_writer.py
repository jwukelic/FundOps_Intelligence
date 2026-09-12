from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.connectors.bigquery_client import BigQueryClient
from app.models import Signal


class BigQueryWriter:
    """Writes pipeline outputs to BigQuery tables in the ``fundops`` dataset.

    All methods are idempotent with respect to the caller — they append rows
    and rely on BigQuery partitioning + downstream deduplication via
    ``external_id`` / ``raw_hash`` rather than upsert semantics, which is
    consistent with the insert-only streaming model used by Cloud Run.
    """

    def __init__(self, bq: BigQueryClient) -> None:
        self._bq = bq

    # ------------------------------------------------------------------
    # Scores
    # ------------------------------------------------------------------

    def write_score(
        self,
        account_id: str,
        program: str,
        score: int,
        priority: str,
        components: dict[str, float],
        explanation: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        self._bq.insert_rows(
            "scores",
            [
                {
                    "score_date": now.date().isoformat(),
                    "scored_at": now.isoformat(),
                    "salesforce_account_id": account_id,
                    "program": program,
                    "total_score": score,
                    "priority": priority,
                    "mission_and_program_fit": components.get("mission_and_program_fit"),
                    "funding_capacity": components.get("funding_capacity"),
                    "timing_and_current_intent": components.get("timing_and_current_intent"),
                    "relationship_access": components.get("relationship_access"),
                    "internal_readiness": components.get("internal_readiness"),
                    "engagement_momentum": components.get("engagement_momentum"),
                    "data_confidence": components.get("data_confidence"),
                    "explanation": explanation,
                }
            ],
        )

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def write_signal(self, signal: Signal) -> None:
        self._bq.insert_rows(
            "signals",
            [
                {
                    "observed_date": signal.observed_at.date().isoformat(),
                    "observed_at": signal.observed_at.isoformat(),
                    "salesforce_account_id": signal.account_id,
                    "salesforce_opportunity_id": None,
                    "program": signal.program,
                    "signal_type": signal.signal_type,
                    "external_id": signal.external_id,
                    "strength": int(signal.strength),
                    "confidence": int(signal.confidence),
                    "summary": signal.summary,
                    "source_name": signal.source_name,
                    "source_url": signal.source_url,
                    "raw_hash": signal.raw_hash,
                }
            ],
        )

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------

    def write_audit(
        self,
        entity_type: str,
        entity_id: str,
        field_name: str,
        old_value: Any,
        new_value: Any,
    ) -> None:
        now = datetime.now(timezone.utc)
        self._bq.insert_rows(
            "audit_log",
            [
                {
                    "audit_date": now.date().isoformat(),
                    "event_at": now.isoformat(),
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "field_name": field_name,
                    "old_value": str(old_value) if old_value is not None else "",
                    "new_value": str(new_value) if new_value is not None else "",
                }
            ],
        )

    # ------------------------------------------------------------------
    # Connector runs
    # ------------------------------------------------------------------

    def write_connector_run(
        self,
        connector: str,
        status: str,
        processed_count: int,
        error_count: int,
        error_summary: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        self._bq.insert_rows(
            "connector_runs",
            [
                {
                    "run_date": now.date().isoformat(),
                    "run_at": now.isoformat(),
                    "connector": connector,
                    "status": status,
                    "processed_count": processed_count,
                    "error_count": error_count,
                    "error_summary": error_summary,
                }
            ],
        )

    def write_opportunity_intake(
        self,
        row_id: str,
        source_url: str,
        organization: str,
        program: str,
        opportunity_type: str,
        process_status: str,
        salesforce_opportunity_id: str,
        error: str = "",
    ) -> None:
        now = datetime.now(timezone.utc)
        self._bq.insert_rows(
            "opportunity_intake",
            [
                {
                    "intake_date": now.date().isoformat(),
                    "row_id": row_id,
                    "source_url": source_url,
                    "organization": organization,
                    "program": program,
                    "opportunity_type": opportunity_type,
                    "process_status": process_status,
                    "salesforce_opportunity_id": salesforce_opportunity_id,
                    "last_processed": now.isoformat(),
                    "error": error,
                }
            ],
        )
