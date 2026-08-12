#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-us-central1}"
REPOSITORY="${REPOSITORY:-fundops-intelligence}"
SERVICE_NAME="${SERVICE_NAME:-fundops-intelligence}"
JOB_NAME="${JOB_NAME:-fundops-intelligence-job}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
IMAGE_URI="${IMAGE_URI:-${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/fundops-intelligence:${IMAGE_TAG}}"
MANUAL_TRIGGER_TOKEN_SECRET="${MANUAL_TRIGGER_TOKEN_SECRET:-fundops-manual-trigger-token}"

gcloud builds submit --project "${PROJECT_ID}" --tag "${IMAGE_URI}" .

COMMON_ENV_VARS="APP_ENV=production,GCP_PROJECT_ID=${PROJECT_ID},GCP_REGION=${REGION},BQ_DATASET=fundops,OPENAI_MODEL=gpt-4.1-mini,OPENAI_TEMPERATURE=0.0,OPENAI_MAX_OUTPUT_TOKENS=800,MAX_RECORDS_PER_CONNECTOR=5,FIRST_RUN_CAP=5"
COMMON_SECRETS="MANUAL_TRIGGER_TOKEN_SECRET=${MANUAL_TRIGGER_TOKEN_SECRET},OPENAI_API_KEY_SECRET=fundops-openai-api-key,SALESFORCE_BASE_URL_SECRET=fundops-salesforce-base-url,SALESFORCE_CLIENT_ID_SECRET=fundops-salesforce-client-id,SALESFORCE_CLIENT_SECRET_SECRET=fundops-salesforce-client-secret,SALESFORCE_USERNAME_SECRET=fundops-salesforce-username,SALESFORCE_PASSWORD_SECRET=fundops-salesforce-password,SALESFORCE_SECURITY_TOKEN_SECRET=fundops-salesforce-security-token,MAILCHIMP_API_KEY_SECRET=fundops-mailchimp-api-key,MAILCHIMP_SERVER_PREFIX_SECRET=fundops-mailchimp-server-prefix,GOOGLE_ADS_DEVELOPER_TOKEN_SECRET=fundops-google-ads-developer-token,HOOTSUITE_API_TOKEN_SECRET=fundops-hootsuite-api-token"

gcloud run deploy "${SERVICE_NAME}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --image "${IMAGE_URI}" \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars "${COMMON_ENV_VARS},RUN_MODE=service,ENABLE_CONNECTOR_MAILCHIMP=false,ENABLE_CONNECTOR_GOOGLE_ADS=false,ENABLE_CONNECTOR_HOOTSUITE=false,ENABLE_CONNECTOR_PUBLIC_URLS=false" \
  --update-env-vars "ENABLE_CONNECTOR_SALESFORCE=true,ENABLE_CONNECTOR_GOOGLE_DRIVE=true,ENABLE_CONNECTOR_GOOGLE_SHEETS=true" \
  --set-secrets "${COMMON_SECRETS}"

if gcloud run jobs describe "${JOB_NAME}" --project "${PROJECT_ID}" --region "${REGION}" >/dev/null 2>&1; then
  gcloud run jobs update "${JOB_NAME}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --image "${IMAGE_URI}" \
    --set-env-vars "${COMMON_ENV_VARS},RUN_MODE=job,ENABLE_CONNECTOR_MAILCHIMP=false,ENABLE_CONNECTOR_GOOGLE_ADS=false,ENABLE_CONNECTOR_HOOTSUITE=false,ENABLE_CONNECTOR_PUBLIC_URLS=false,ENABLE_CONNECTOR_SALESFORCE=true,ENABLE_CONNECTOR_GOOGLE_DRIVE=true,ENABLE_CONNECTOR_GOOGLE_SHEETS=true" \
    --set-secrets "${COMMON_SECRETS}"
else
  gcloud run jobs create "${JOB_NAME}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --image "${IMAGE_URI}" \
    --set-env-vars "${COMMON_ENV_VARS},RUN_MODE=job,ENABLE_CONNECTOR_MAILCHIMP=false,ENABLE_CONNECTOR_GOOGLE_ADS=false,ENABLE_CONNECTOR_HOOTSUITE=false,ENABLE_CONNECTOR_PUBLIC_URLS=false,ENABLE_CONNECTOR_SALESFORCE=true,ENABLE_CONNECTOR_GOOGLE_DRIVE=true,ENABLE_CONNECTOR_GOOGLE_SHEETS=true" \
    --set-secrets "${COMMON_SECRETS}"
fi

echo "${IMAGE_URI}"

