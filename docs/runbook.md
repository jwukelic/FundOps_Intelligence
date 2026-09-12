# Runbook

- Daily operation: Cloud Scheduler invokes Cloud Run job.
- Manual refresh: run `scripts/run_job.sh`.
- Opportunity intake: add URL row to FundOps intake sheet and rerun.
- Review recommendations: Account FundOps fields + `[FundOps]` tasks + FundOps Signals.
- Generate brief/draft: requested via intake metadata and approved documents only.
- Connector failure recovery: disable failing connector env and rerun; others continue.
- Rotate secrets: add a new Secret Manager version and redeploy.
- Rollback: use `scripts/rollback.sh` with previous revision.
- Duplicate prevention: external IDs + upsert + action-type task hash.
- Pause scheduler: `gcloud scheduler jobs pause fundops-daily --location=us-central1`.
