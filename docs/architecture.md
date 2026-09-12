# Architecture

```text
Google Sheets intake + Approved Drive folder + Salesforce + Read-only marketing connectors
                           |
                           v
                    Cloud Run Job (/run)
                           |
                           v
              Deterministic scoring + dedup + AI cache
                           |
               +-----------+-----------+
               |                       |
               v                       v
          BigQuery fundops        Salesforce updates
```

Responsibilities:
- Cloud Run executes incremental idempotent pipeline.
- BigQuery stores provenance, scores, sync state, and audit log.
- Salesforce holds operational priorities, actions, tasks, and signal records.

Privacy boundaries:
- No student/beneficiary-level targeting data.
- Read-only marketing ingestion.
- Inferred content must be labeled inferred.

Low-cost rationale:
- Single image and runtime.
- Cloud Run min instances = 0.
- One scheduled daily run.
- Deterministic scoring (no ML training).
- Cached AI calls on content hash.
