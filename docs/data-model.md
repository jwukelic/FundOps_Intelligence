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
