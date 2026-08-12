from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from app.config import Settings
from app.connectors.google_sheets import GoogleSheetsConnector
from app.connectors.salesforce import SalesforceConnector
from app.models import PipelineResult, ScoreComponents, Signal
from app.scoring import score_priority
from app.services.audit import build_audit_entry
from app.services.intelligence import build_account_summary, recommend_next_action
from app.services.signal_normalization import deduplicate_signals, signal_hash

if TYPE_CHECKING:
    from app.services.bigquery_writer import BigQueryWriter


def run_pipeline(
    settings: Settings,
    salesforce: SalesforceConnector,
    sheets: GoogleSheetsConnector,
    bq_writer: BigQueryWriter | None = None,
) -> PipelineResult:
    result = PipelineResult()
    accounts = salesforce.query_enabled_accounts(limit=settings.fundops_max_accounts)
    result.processed_accounts = len(accounts)
    for account in accounts:
        account_id = account["Id"]
        program = account.get("FundOps_Primary_Program__c", "Unknown")
        components = ScoreComponents(
            mission_and_program_fit=80,
            funding_capacity=55,
            timing_and_current_intent=60,
            relationship_access=40,
            internal_readiness=65,
            engagement_momentum=50,
            data_confidence=70,
            eligibility_gate=True,
        )
        score, priority, component_scores = score_priority(components)
        next_action = recommend_next_action(components)
        summary = build_account_summary(program, score, priority, ["decision-maker unknown"])

        old_score = account.get("FundOps_Score__c")
        salesforce.upsert_account_fields(
            account_id,
            {
                "FundOps_Score__c": score,
                "FundOps_Priority__c": priority,
                "FundOps_Summary__c": summary,
                "FundOps_Next_Action__c": next_action,
                "FundOps_Data_Confidence__c": round(components.data_confidence / 100, 4),
                "FundOps_Last_Refresh__c": SalesforceConnector.utc_now(),
                "FundOps_Last_Error__c": "",
            },
        )

        now = datetime.now(timezone.utc)
        raw_hash = signal_hash([account_id, program, str(score), next_action, now.strftime("%Y-%m-%d")])
        signal = Signal(
            external_id=f"{account_id}-priority-{now.strftime('%Y%m%d')}",
            account_id=account_id,
            program=program,
            signal_type="PriorityScore",
            strength=score,
            confidence=components.data_confidence,
            summary=f"Priority {priority} from deterministic score.",
            source_name="FundOps Scoring",
            source_url="internal://fundops/scoring",
            observed_at=now,
            raw_hash=raw_hash,
        )
        for deduped in deduplicate_signals([signal]):
            salesforce.upsert_signal(deduped)
            if bq_writer is not None:
                bq_writer.write_signal(deduped)

        due = (now + timedelta(days=5)).date().isoformat()
        salesforce.upsert_task(
            account_id=account_id,
            action_type=next_action,
            why=f"Score={score}, priority={priority}",
            due_date=due,
            source_url="internal://fundops/scoring",
        )

        audit = build_audit_entry("Account", account_id, "FundOps_Score__c", old_score, score)
        if bq_writer is not None:
            bq_writer.write_score(
                account_id=account_id,
                program=program,
                score=score,
                priority=priority,
                components=component_scores,
                explanation=summary,
            )
            bq_writer.write_audit(
                audit["entity_type"],
                audit["entity_id"],
                audit["field_name"],
                audit["old_value"],
                audit["new_value"],
            )

        result.scored_accounts += 1
        result.created_or_updated_tasks += 1
        result.details[account_id] = {
            "score": score,
            "priority": priority,
            "component_scores": component_scores,
            "next_action": next_action,
        }

    for row in sheets.list_new_or_changed_intake_rows():
        external_id = f"opp-{hash(row.url)}"
        salesforce.upsert_opportunity(
            external_id,
            {
                "Name": row.organization,
                "FundOps_Program__c": row.program,
                "FundOps_Opportunity_Type__c": row.opportunity_type,
                "FundOps_Eligibility__c": "Unknown",
                "FundOps_Source_URL__c": row.url,
                "FundOps_Score__c": 50,
                "FundOps_Summary__c": "Intake processed. Add approved evidence and rerun for full brief.",
                "FundOps_Next_Action__c": "Research missing eligibility information",
            },
        )
        sheets.mark_processed(row.row_id, external_id)
        result.processed_opportunities += 1

    if bq_writer is not None:
        bq_writer.write_connector_run(
            connector="pipeline",
            status="success" if not result.errors else "partial_failure",
            processed_count=result.scored_accounts + result.processed_opportunities,
            error_count=len(result.errors),
            error_summary="; ".join(result.errors),
        )

    return result
