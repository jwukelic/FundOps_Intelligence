from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from app.config import Settings
from app.connectors.google_drive import GoogleDriveConnector
from app.connectors.google_sheets import GoogleSheetsConnector
from app.connectors.irs990 import Irs990Connector
from app.connectors.salesforce import SalesforceConnector
from app.models import PipelineResult, Signal
from app.scoring import score_priority
from app.services.audit import build_audit_entry
from app.services.intelligence import build_account_summary, recommend_next_action
from app.services.score_from_account import score_from_account
from app.services.signal_normalization import deduplicate_signals, signal_hash

if TYPE_CHECKING:
    from app.services.bigquery_writer import BigQueryWriter


def run_pipeline(
    settings: Settings,
    salesforce: SalesforceConnector,
    sheets: GoogleSheetsConnector,
    bq_writer: BigQueryWriter | None = None,
    drive: GoogleDriveConnector | None = None,
    irs990: Irs990Connector | None = None,
) -> PipelineResult:
    result = PipelineResult()

    # Fetch approved Drive documents once per run (shared across all accounts).
    drive_docs = drive.list_approved_documents() if drive is not None else []

    accounts = salesforce.query_enabled_accounts(limit=settings.fundops_max_accounts)
    result.processed_accounts = len(accounts)

    for account in accounts:
        account_id = account["Id"]
        try:
            _process_account(
                account=account,
                salesforce=salesforce,
                bq_writer=bq_writer,
                drive_docs=drive_docs,
                irs990=irs990,
                result=result,
            )
        except Exception as exc:  # noqa: BLE001
            error_msg = f"Account {account_id}: {exc}"
            result.errors.append(error_msg)
            salesforce.upsert_account_fields(
                account_id,
                {
                    "FundOps_Last_Error__c": str(exc)[:255],
                    "FundOps_Last_Refresh__c": SalesforceConnector.utc_now(),
                },
            )

    for row in sheets.list_new_or_changed_intake_rows():
        try:
            external_id = _opportunity_external_id(row.url)
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
            if bq_writer is not None:
                bq_writer.write_opportunity_intake(
                    row_id=row.row_id,
                    source_url=row.url,
                    organization=row.organization,
                    program=row.program,
                    opportunity_type=row.opportunity_type,
                    process_status="processed",
                    salesforce_opportunity_id=external_id,
                )
            result.processed_opportunities += 1
        except Exception as exc:  # noqa: BLE001
            error_msg = f"Intake row {row.row_id}: {exc}"
            result.errors.append(error_msg)
            sheets.mark_processed(row.row_id, "", error=str(exc)[:255])
            if bq_writer is not None:
                bq_writer.write_opportunity_intake(
                    row_id=row.row_id,
                    source_url=row.url,
                    organization=row.organization,
                    program=row.program,
                    opportunity_type=row.opportunity_type,
                    process_status="error",
                    salesforce_opportunity_id="",
                    error=str(exc)[:255],
                )

    if bq_writer is not None:
        bq_writer.write_connector_run(
            connector="pipeline",
            status="success" if not result.errors else "partial_failure",
            processed_count=result.scored_accounts + result.processed_opportunities,
            error_count=len(result.errors),
            error_summary="; ".join(result.errors),
        )

    return result


def _opportunity_external_id(url: str) -> str:
    return f"opp-{signal_hash([url.strip()])}"


def _process_account(
    account: dict,
    salesforce: SalesforceConnector,
    bq_writer: BigQueryWriter | None,
    drive_docs: list,
    result: PipelineResult,
    irs990: Irs990Connector | None = None,
) -> None:
    account_id = account["Id"]
    program = account.get("FundOps_Primary_Program__c", "Unknown")
    old_score = account.get("FundOps_Score__c")

    # Derive components from stored signals + Drive evidence + IRS 990.
    existing_signals = salesforce.query_signals_for_account(account_id)
    if irs990 is not None:
        for sig_dict in irs990.build_signals(account):
            # Upsert into Salesforce so the signal persists for future runs.
            salesforce.upsert_signal_from_dict(sig_dict)
            existing_signals.append(sig_dict)
    components = score_from_account(account, existing_signals, drive_docs=drive_docs)

    score, priority, component_scores = score_priority(components)
    next_action = recommend_next_action(components)
    unknowns = _collect_unknowns(components)
    summary = build_account_summary(program, score, priority, unknowns)

    fields_to_write = {
        "FundOps_Score__c": score,
        "FundOps_Priority__c": priority,
        "FundOps_Summary__c": summary,
        "FundOps_Next_Action__c": next_action,
        "FundOps_Data_Confidence__c": round(components.data_confidence / 100, 4),
        "FundOps_Last_Refresh__c": SalesforceConnector.utc_now(),
        "FundOps_Last_Error__c": "",
    }
    # Clear refresh-requested flag if it was set.
    if account.get("FundOps_Refresh_Requested__c"):
        fields_to_write["FundOps_Refresh_Requested__c"] = False

    salesforce.upsert_account_fields(account_id, fields_to_write)

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


def _collect_unknowns(components) -> list[str]:
    """Return human-readable labels for components that are below the low-confidence threshold."""
    LOW = 35.0
    labels = {
        "mission_and_program_fit": "mission fit",
        "funding_capacity": "funding capacity",
        "timing_and_current_intent": "timing and intent",
        "relationship_access": "decision-maker unknown",
        "internal_readiness": "internal readiness",
        "engagement_momentum": "engagement momentum",
    }
    unknowns = []
    for attr, label in labels.items():
        if getattr(components, attr, 100) < LOW:
            unknowns.append(label)
    return unknowns or ["none flagged"]
