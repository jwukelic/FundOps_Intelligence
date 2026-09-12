# Architecture

## Lean runtime

FundOps Intelligence ships one Python 3.12 container image. Cloud Run service mode exposes `/health` and `/run/manual`; Cloud Run job mode executes the same pipeline once by setting `RUN_MODE=job`.

## Vertical slice

1. Read Salesforce, approved Google Drive content, and Google Sheets intake rows.
2. Normalize and deduplicate signals by external ID or raw hash.
3. Store operational state in BigQuery tables under `fundops`.
4. Retrieve approved content with keyword/metadata filtering only.
5. Compute deterministic scores and priority bands.
6. Generate explainable summaries/next actions with cached structured AI or deterministic fallback.
7. Upsert only FundOps-specific Salesforce fields, opportunities, custom signal records, and one active `[FundOps]` task per action type.
8. Write before/after audit rows and connector run outcomes.

## Connector posture

- **Core enabled path:** Salesforce, Google Drive, Google Sheets, BigQuery, OpenAI.
- **Graceful optional connectors:** Mailchimp, Google Ads, Hootsuite, public URLs.
- Optional connectors are disabled by config when credentials are absent; failures are isolated and logged.

