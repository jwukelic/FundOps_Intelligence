# Decisions

- Use one Python 3.12 FastAPI codebase for local, Cloud Run service, and Cloud Run job.
- Use deterministic scoring for explainability and low cost.
- Keep marketing connectors read-only and disabled by default until credentials exist.
- Use idempotent upserts and external IDs for Signals, Opportunities, and Tasks.
- Assume single-user Salesforce operation (Julie only) with one permission set.
- IRS 990 connector queries `bigquery-public-data.irs_990` cross-project; requires `FUNDOPS_PROJECT_ID` and `FUNDOPS_IRS990_ENABLED=true`. Name-based LIKE match is the default; populate `FundOps_IRS_EIN__c` on an Account for precise EIN lookup.
- Salesforce connector uses `simple-salesforce` in production (credentials via Secret Manager env vars). Falls back to in-memory store when credentials are absent (tests / local dev).
- Google Sheets and Drive connectors use `google-api-python-client` with Application Default Credentials (ADC). No extra credentials needed on Cloud Run — the service account must be shared on the intake sheet and approved Drive folder.
- `RUN_MODE=job` switches the container from a long-running service to a single-execution job entrypoint (`python -m app.main`). Both modes share the same image and `_execute_pipeline()` function.
- Tasks don't support upsert by external ID in Salesforce; the connector queries for an open matching task before creating a new one (query-then-upsert pattern).
