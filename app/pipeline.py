from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from app.config import Settings
from app.models import ConnectorResult, PipelineSummary, SignalRecord
from app.services.audit import make_audit_event
from app.services.content_retrieval import retrieve_content
from app.services.entity_resolution import canonical_entity_key
from app.services.intelligence import IntelligenceService
from app.services.normalization import normalize_signals
from app.services.scoring import score_entity


LOGGER = logging.getLogger(__name__)


class PipelineRunner:
    def __init__(
        self,
        settings: Settings,
        warehouse: Any,
        connectors: list[Any],
        intelligence_service: IntelligenceService,
        salesforce_writer: Any | None = None,
    ) -> None:
        self.settings = settings
        self.warehouse = warehouse
        self.connectors = connectors
        self.intelligence_service = intelligence_service
        self.salesforce_writer = salesforce_writer

    def run(self) -> PipelineSummary:
        self.warehouse.ensure_tables()
        connector_status: dict[str, str] = {}
        ai_cache_hits = 0
        opportunities_upserted = 0
        tasks_changed = 0
        all_signals: list[SignalRecord] = []
        for connector in self.connectors:
            if not getattr(connector, "enabled", False):
                connector_status[connector.name] = "disabled"
                continue
            try:
                result = self._retry_fetch(connector)
                connector_status[connector.name] = "ok"
                latest_watermark = self._persist_connector_result(result)
                if latest_watermark:
                    self.warehouse.set_sync_state(connector.name, latest_watermark)
                self.warehouse.append_connector_run(
                    {"connector_name": connector.name, "status": "ok", "ran_at": datetime.now(UTC).isoformat()}
                )
                all_signals.extend(result.signals)
            except Exception as exc:
                connector_status[connector.name] = f"failed: {exc}"
                self.warehouse.append_connector_run(
                    {
                        "connector_name": connector.name,
                        "status": "failed",
                        "error_message": str(exc),
                        "ran_at": datetime.now(UTC).isoformat(),
                    }
                )
                LOGGER.exception("Connector %s failed but pipeline continued.", connector.name)
        grouped = defaultdict(list)
        for signal in normalize_signals(all_signals):
            signal.entity_key = canonical_entity_key(signal)
            if self.warehouse.upsert_signal(signal):
                grouped[(signal.entity_type, signal.entity_key)].append(signal)
            else:
                grouped[(signal.entity_type, signal.entity_key)].append(signal)
        for opportunity in self.warehouse.list_opportunities():
            opportunities_upserted += 1
            grouped[("account", opportunity.account_key.lower())]
        scored_entities = 0
        for (entity_type, entity_key), signals in grouped.items():
            merged_signals = self.warehouse.list_signals_for_entity(entity_key)
            scorecard = score_entity(entity_key=entity_key, entity_type=entity_type, signals=merged_signals)
            self.warehouse.upsert_score(scorecard)
            contents = retrieve_content(entity_key, self.warehouse.list_content(entity_key))
            brief = self.intelligence_service.generate(entity_key, scorecard, merged_signals, contents)
            ai_cache_hits += int(brief.cache_hit)
            if self.salesforce_writer:
                tasks_changed += self._sync_salesforce(entity_type, entity_key, scorecard, brief, merged_signals)
            scored_entities += 1
        return PipelineSummary(
            connector_status=connector_status,
            signals_processed=len(self.warehouse.signals) if hasattr(self.warehouse, "signals") else len(all_signals),
            entities_scored=scored_entities,
            opportunities_upserted=opportunities_upserted,
            tasks_created_or_updated=tasks_changed,
            ai_cache_hits=ai_cache_hits,
        )

    def _retry_fetch(self, connector: Any) -> ConnectorResult:
        watermark = self.warehouse.get_sync_state(connector.name)
        max_records = self.settings.first_run_cap if watermark is None else self.settings.max_records_per_connector
        last_error: Exception | None = None
        for attempt in range(1, self.settings.retry_attempts + 1):
            try:
                return connector.fetch(max_records=max_records, watermark=watermark)
            except Exception as exc:
                last_error = exc
                if attempt == self.settings.retry_attempts:
                    break
                time.sleep(min(self.settings.retry_backoff_seconds * (2 ** (attempt - 1)), 10))
        if last_error:
            raise last_error
        return ConnectorResult()

    def _persist_connector_result(self, result: ConnectorResult) -> str | None:
        latest_watermark: str | None = None
        for signal in normalize_signals(result.signals):
            self.warehouse.upsert_signal(signal)
            latest_watermark = max(filter(None, [latest_watermark, signal.observed_at.isoformat()]), default=None)
        for content in result.content:
            self.warehouse.upsert_content(content)
            latest_watermark = max(filter(None, [latest_watermark, content.updated_at.isoformat()]), default=None)
        for opportunity in result.opportunities:
            self.warehouse.upsert_opportunity_intake(opportunity)
            latest_watermark = max(filter(None, [latest_watermark, opportunity.updated_at.isoformat()]), default=None)
        return latest_watermark

    def _sync_salesforce(self, entity_type: str, entity_key: str, scorecard, brief, signals: list[SignalRecord]) -> int:
        changed_tasks = 0
        if entity_type != "account":
            return changed_tasks
        account_id = next((signal.external_id for signal in signals if signal.connector == "salesforce" and signal.external_id), None)
        if not account_id:
            return changed_tasks
        before = self.salesforce_writer.get_record("Account", account_id)
        self.salesforce_writer.upsert_account(account_id, scorecard, brief)
        after = {
            "FundOps_Score__c": scorecard.total_score,
            "FundOps_Priority__c": scorecard.priority,
            "FundOps_Brief__c": brief.summary,
        }
        self.warehouse.append_audit(make_audit_event("Account", account_id, "update", before, after))
        for action in brief.recommended_actions:
            if self.salesforce_writer.upsert_task(account_id, action):
                changed_tasks += 1
        for signal in signals:
            self.salesforce_writer.upsert_signal_record(account_id, None, signal)
        for opportunity in [item for item in self.warehouse.list_opportunities() if item.account_key.lower() == entity_key]:
            self.salesforce_writer.upsert_opportunity(opportunity, scorecard, brief)
        return changed_tasks

