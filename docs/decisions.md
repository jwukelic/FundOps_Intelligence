# Decisions

- Use one FastAPI codebase and one container image for both Cloud Run service and job.
- Keep BigQuery as the only operational store outside Salesforce.
- Use keyword/metadata retrieval over approved content instead of a vector database.
- Keep Salesforce changes minimal: custom fields on Account/Opportunity plus one custom signal object; no Apex or LWC.
- Default to low-cost deterministic AI (`gpt-4.1-mini`, temperature `0.0`) with cache-first behavior.
- Disable non-core marketing connectors by default when credentials are missing.
- Never delete Salesforce records; only upsert FundOps-managed fields and records.

