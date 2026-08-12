# Decisions

- Use one Python 3.12 FastAPI codebase for local, Cloud Run service, and Cloud Run job.
- Use deterministic scoring for explainability and low cost.
- Keep marketing connectors read-only and disabled by default until credentials exist.
- Use idempotent upserts and external IDs for Signals, Opportunities, and Tasks.
- Assume single-user Salesforce operation (Julie only) with one permission set.
- IRS 990 connector queries `bigquery-public-data.irs_990` cross-project; requires `FUNDOPS_PROJECT_ID` and `FUNDOPS_IRS990_ENABLED=true`. Name-based LIKE match is the default; populate `FundOps_IRS_EIN__c` on an Account for precise EIN lookup.
