# FundOps Intelligence

FundOps Intelligence is a production-first fundraising intelligence MVP for Believe in Me, Cougs 4 Kids, and iLevelUP. It runs a daily idempotent pipeline that scores FundOps-enabled Salesforce Accounts, writes explainable priorities, creates deduplicated `[FundOps]` tasks, and processes URL-based opportunity intake.

## Architecture (MVP)
- FastAPI app (`app/main.py`) runs on Cloud Run service and Cloud Run job from one image.
- BigQuery dataset `fundops` stores signals, scores, cache, intake, and audit history.
- Salesforce is the system of action with custom FundOps fields and `FundOps_Signal__c`.
- Google Sheets intake rows create/update opportunities via external IDs.

## Prerequisites
- Python 3.12
- `gcloud` CLI authenticated to production project
- Salesforce CLI (`sf`) authenticated to production org

## Fast production deployment
```bash
PROJECT_ID=<gcp-project> REGION=us-central1 ./scripts/bootstrap_gcp.sh
PROJECT_ID=<gcp-project> ./scripts/create_secrets.sh
SF_TARGET_ORG=<your-sf-alias> ./scripts/deploy_salesforce.sh
PROJECT_ID=<gcp-project> REGION=us-central1 ./scripts/deploy.sh
```

## Run the daily job manually
```bash
PROJECT_ID=<gcp-project> REGION=us-central1 ./scripts/run_job.sh
```

## Where Julie sees results in Salesforce
- Account fields: `FundOps Score`, `FundOps Priority`, `FundOps Summary`, `FundOps Next Action`, `FundOps Data Confidence`.
- Related list: `FundOps Signals`.
- Tasks: subjects prefixed with `[FundOps]`.

## Troubleshooting
```bash
pytest -q
BASE_URL=<cloud-run-url> ./scripts/smoke_test.sh
PROJECT_ID=<gcp-project> REGION=us-central1 SERVICE=fundops-intelligence REVISION=<previous-revision> ./scripts/rollback.sh
```
