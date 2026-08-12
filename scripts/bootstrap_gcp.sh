#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-us-central1}"
DATASET="${DATASET:-fundops}"
REPOSITORY="${REPOSITORY:-fundops-intelligence}"
SERVICE_NAME="${SERVICE_NAME:-fundops-intelligence}"
JOB_NAME="${JOB_NAME:-fundops-intelligence-job}"
SCHEDULER_JOB_NAME="${SCHEDULER_JOB_NAME:-fundops-daily-sync}"
SCHEDULER_SA="${SCHEDULER_SA:-}"
CRON_SCHEDULE="${CRON_SCHEDULE:-0 13 * * *}"

gcloud services enable artifactregistry.googleapis.com run.googleapis.com cloudscheduler.googleapis.com \
  secretmanager.googleapis.com bigquery.googleapis.com logging.googleapis.com cloudbuild.googleapis.com \
  --project "${PROJECT_ID}"

gcloud artifacts repositories describe "${REPOSITORY}" --location "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1 || \
  gcloud artifacts repositories create "${REPOSITORY}" \
    --repository-format docker \
    --location "${REGION}" \
    --description "FundOps Intelligence images" \
    --project "${PROJECT_ID}"

bq --project_id="${PROJECT_ID}" ls -d "${PROJECT_ID}:${DATASET}" >/dev/null 2>&1 || \
  bq --project_id="${PROJECT_ID}" mk --dataset --location="${REGION}" "${PROJECT_ID}:${DATASET}"

if [[ -n "${SCHEDULER_SA}" ]]; then
  JOB_URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run"
  if gcloud scheduler jobs describe "${SCHEDULER_JOB_NAME}" --location "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud scheduler jobs update http "${SCHEDULER_JOB_NAME}" \
      --location "${REGION}" \
      --schedule "${CRON_SCHEDULE}" \
      --uri "${JOB_URI}" \
      --http-method POST \
      --oauth-service-account-email "${SCHEDULER_SA}" \
      --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform" \
      --project "${PROJECT_ID}"
  else
    gcloud scheduler jobs create http "${SCHEDULER_JOB_NAME}" \
      --location "${REGION}" \
      --schedule "${CRON_SCHEDULE}" \
      --uri "${JOB_URI}" \
      --http-method POST \
      --oauth-service-account-email "${SCHEDULER_SA}" \
      --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform" \
      --project "${PROJECT_ID}"
  fi
fi

echo "Bootstrap complete for ${PROJECT_ID}."

