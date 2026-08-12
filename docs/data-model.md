# Data Model

## Salesforce
- Account FundOps fields in `salesforce/main/default/objects/Account/fields`.
- Opportunity FundOps fields in `salesforce/main/default/objects/Opportunity/fields`.
- Custom object `FundOps_Signal__c` with external ID and source lineage fields.

## BigQuery
DDL in `app/sql/fundops_tables.sql` creates:
- `signals`, `scores`, `sync_state`, `ai_cache`, `content_index`, `audit_log`, `connector_runs`, `opportunity_intake`.

## External IDs
- Signals: `External_ID__c`.
- Opportunities: `FundOps_External_ID__c`.
- Tasks: deterministic hash of account + action type.

## Scoring
Deterministic weighted score with eligibility gate and tiers:
- Critical 85-100, High 70-84, Medium 50-69, Low 1-49, Not Eligible 0.

ScoreComponents are derived from `FundOps_Signal__c` records via `app/services/score_from_account.py`.
Signal types map to components:

| Signal_Type__c     | ScoreComponent              |
|--------------------|-----------------------------|
| MissionFit         | mission_and_program_fit     |
| FundingCapacity    | funding_capacity            |
| TimingIntent       | timing_and_current_intent   |
| RelationshipAccess | relationship_access         |
| InternalReadiness  | internal_readiness          |
| EngagementMomentum | engagement_momentum         |
| DataConfidence     | data_confidence (override)  |
| *(any other)*      | engagement_momentum         |

Approved Drive documents matching the account's program provide a small boost to
`mission_and_program_fit` and `internal_readiness`.

`data_confidence` is auto-computed as `min(90, 50 + 10 * distinct_source_count)`
unless a `DataConfidence` signal overrides it.
