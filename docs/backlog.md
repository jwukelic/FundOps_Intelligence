# Backlog

- ~~Add BigQuery-backed persistent AI cache implementation.~~ Done — `app/services/bigquery_cache.py` + `app/connectors/bigquery_client.py`.
- ~~Add richer Salesforce report/dashboard metadata package.~~ Done — `FundOps_Priority_Accounts`, `FundOps_Upcoming_Actions` reports and `FundOps_Pipeline` dashboard added to SF metadata.
- ~~Wire BigQueryWriter into /run endpoint.~~ Done — `app/main.py` constructs `BigQueryWriter` when `FUNDOPS_PROJECT_ID` is set.
- ~~Data-driven ScoreComponents from account signals.~~ Done — `app/services/score_from_account.py` maps `Signal_Type__c` → component; Drive docs provide a boost.
- ~~Per-account error handling.~~ Done — exceptions are caught, written to `FundOps_Last_Error__c`, and recorded in `PipelineResult.errors`.
- ~~Honor FundOps_Refresh_Requested__c.~~ Done — flag is checked and reset to `False` after processing.
- ~~Add optional IRS 990 reuse after confirming existing dataset availability.~~ Done — `app/connectors/irs990.py` queries `bigquery-public-data.irs_990` for FundingCapacity signals; enabled via `FUNDOPS_IRS990_ENABLED=true`.
