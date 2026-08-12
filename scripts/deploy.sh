#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?PROJECT_ID is required}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-fundops-intelligence}"
JOB="${JOB:-fundops-intelligence-job}"
REPO="${REPO:-fundops-intelligence}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-fundops-intelligence-sa}"
SA_EMAIL="${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/fundops-intelligence:${IMAGE_TAG:-latest}"

# Secrets to mount as env vars in both the service and job.
# Format: ENV_VAR_NAME=secret-name
SECRET_ENV_MAPPINGS=(
  "SALESFORCE_USERNAME=fundops-salesforce-username"
  "SALESFORCE_AUTH=fundops-salesforce-auth"
  "SALESFORCE_CLIENT_ID=fundops-salesforce-client-id"
  "SALESFORCE_CLIENT_SECRET=fundops-salesforce-client-secret"
  "OPENAI_API_KEY=fundops-openai-api-key"
  "FUNDOPS_APP_SECRET=fundops-app-secret"
)

# Build the --set-secrets flag value (comma-separated).
SECRETS_FLAG=""
for mapping in "${SECRET_ENV_MAPPINGS[@]}"; do
  env_var="${mapping%%=*}"
  secret_name="${mapping##*=}"
  SECRETS_FLAG="${SECRETS_FLAG}${env_var}=${secret_name}:latest,"
done
SECRETS_FLAG="${SECRETS_FLAG%,}"  # strip trailing comma

echo "=== Building image ==="
gcloud builds submit \
  --project "$PROJECT_ID" \
  --tag "$IMAGE" \
  .

echo "=== Deploying Cloud Run service ==="
gcloud run deploy "$SERVICE" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --image "$IMAGE" \
  --service-account "$SA_EMAIL" \
  --min-instances=0 \
  --max-instances=2 \
  --memory=512Mi \
  --timeout=900 \
  --set-secrets "$SECRETS_FLAG" \
  --set-env-vars "FUNDOPS_PROJECT_ID=${PROJECT_ID},FUNDOPS_IRS990_ENABLED=${FUNDOPS_IRS990_ENABLED:-false}" \
  --allow-unauthenticated

echo "=== Deploying Cloud Run job ==="
gcloud run jobs describe "$JOB" --project "$PROJECT_ID" --region "$REGION" >/dev/null 2>&1 && \
  gcloud run jobs update "$JOB" \
    --project "$PROJECT_ID" \
    --region "$REGION" \
    --image "$IMAGE" \
    --service-account "$SA_EMAIL" \
    --memory=512Mi \
    --task-timeout=900 \
    --set-secrets "$SECRETS_FLAG" \
    --set-env-vars "RUN_MODE=job,FUNDOPS_PROJECT_ID=${PROJECT_ID},FUNDOPS_IRS990_ENABLED=${FUNDOPS_IRS990_ENABLED:-false}" || \
  gcloud run jobs create "$JOB" \
    --project "$PROJECT_ID" \
    --region "$REGION" \
    --image "$IMAGE" \
    --service-account "$SA_EMAIL" \
    --memory=512Mi \
    --task-timeout=900 \
    --set-secrets "$SECRETS_FLAG" \
    --set-env-vars "RUN_MODE=job,FUNDOPS_PROJECT_ID=${PROJECT_ID},FUNDOPS_IRS990_ENABLED=${FUNDOPS_IRS990_ENABLED:-false}"

echo "=== Deploy complete ==="
