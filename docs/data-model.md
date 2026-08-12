# Data Model

## BigQuery dataset: `fundops`

- `signals` — partitioned by `observed_at`, clustered by connector/entity.
- `scores` — current deterministic scorecards per entity.
- `sync_state` — per-connector watermarks.
- `ai_cache` — input hash to response JSON cache.
- `content_index` — approved evidence only, keyword/metadata retrieval.
- `audit_log` — before/after field changes and failure events.
- `connector_runs` — connector status and error isolation trail.
- `opportunity_intake` — Google Sheets intake staging/upsert source.

## Salesforce metadata

### Account custom fields
- `FundOps_External_Id__c`
- `FundOps_Last_Run_At__c`
- `FundOps_Score__c`
- `FundOps_Priority__c`
- `FundOps_Brief__c`

### Opportunity custom fields
- `FundOps_External_Id__c`
- `FundOps_Last_Run_At__c`
- `FundOps_Score__c`
- `FundOps_Priority__c`
- `FundOps_Brief__c`
- `FundOps_Next_Action__c`
- `FundOps_Inferred_Data__c`

### Custom object
- `FundOps_Signal__c` with external ID, Account/Opportunity lookups, source metadata, score contribution, explanation, and raw hash.

