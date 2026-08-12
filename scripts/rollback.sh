#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-fundops-intelligence}"
JOB_NAME="${JOB_NAME:-fundops-intelligence-job}"
PREVIOUS_SERVICE_REVISION="${PREVIOUS_SERVICE_REVISION:-}"
PREVIOUS_JOB_IMAGE="${PREVIOUS_JOB_IMAGE:-}"

if [[ -n "${PREVIOUS_SERVICE_REVISION}" ]]; then
  gcloud run services update-traffic "${SERVICE_NAME}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --to-revisions "${PREVIOUS_SERVICE_REVISION}=100"
fi

if [[ -n "${PREVIOUS_JOB_IMAGE}" ]]; then
  gcloud run jobs update "${JOB_NAME}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --image "${PREVIOUS_JOB_IMAGE}"
fi

