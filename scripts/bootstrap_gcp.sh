#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?PROJECT_ID is required}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-fundops-intelligence}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-fundops-intelligence-sa}"
SA_EMAIL="${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com"
SCHEDULER_JOB="${SCHEDULER_JOB:-fundops-daily}"
SCHEDULE="${SCHEDULE:-0 12 * * *}"  # 12:00 UTC daily

echo "=== Enabling APIs ==="
for api in \
  run.googleapis.com \
  cloudscheduler.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  bigquery.googleapis.com \
  cloudbuild.googleapis.com; do
  gcloud services enable "$api" --project "$PROJECT_ID"
done

echo "=== Artifact Registry ==="
gcloud artifacts repositories describe "$REPO" --location "$REGION" --project "$PROJECT_ID" >/dev/null 2>&1 || \
  gcloud artifacts repositories create "$REPO" \
    --repository-format docker --location "$REGION" --project "$PROJECT_ID"

echo "=== Service account ==="
gcloud iam service-accounts describe "$SA_EMAIL" --project "$PROJECT_ID" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "$SERVICE_ACCOUNT" \
    --display-name "FundOps Intelligence" --project "$PROJECT_ID"

echo "=== IAM bindings ==="
for role in \
  roles/bigquery.dataEditor \
  roles/bigquery.jobUser \
  roles/secretmanager.secretAccessor \
  roles/logging.logWriter \
  roles/run.invoker; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member "serviceAccount:${SA_EMAIL}" \
    --role "$role" \
    --condition None \
    --quiet
done

echo "=== BigQuery dataset ==="
bq show --project_id="$PROJECT_ID" fundops >/dev/null 2>&1 || \
  bq mk --location=US --dataset "${PROJECT_ID}:fundops"

echo "=== BigQuery tables (idempotent) ==="
bq query --project_id="$PROJECT_ID" --use_legacy_sql=false < app/sql/fundops_tables.sql

echo "=== Cloud Scheduler ==="
# Scheduler invokes the Cloud Run job via the Jobs API.
JOB_NAME="${JOB:-fundops-intelligence-job}"
JOB_URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run"
gcloud scheduler jobs describe "$SCHEDULER_JOB" --location="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1 && \
  gcloud scheduler jobs update http "$SCHEDULER_JOB" \
    --location="$REGION" \
    --schedule="$SCHEDULE" \
    --uri="$JOB_URI" \
    --http-method=POST \
    --oauth-service-account-email="$SA_EMAIL" \
    --project="$PROJECT_ID" || \
  gcloud scheduler jobs create http "$SCHEDULER_JOB" \
    --location="$REGION" \
    --schedule="$SCHEDULE" \
    --uri="$JOB_URI" \
    --http-method=POST \
    --oauth-service-account-email="$SA_EMAIL" \
    --project="$PROJECT_ID"

echo "=== Bootstrap complete ==="
echo "Next: PROJECT_ID=$PROJECT_ID ./scripts/create_secrets.sh"
