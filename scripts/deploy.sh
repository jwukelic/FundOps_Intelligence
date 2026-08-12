#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?PROJECT_ID is required}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-fundops-intelligence}"
JOB="${JOB:-fundops-intelligence-job}"
REPO="${REPO:-fundops-intelligence}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/fundops-intelligence:${IMAGE_TAG:-latest}"


gcloud builds submit --project "$PROJECT_ID" --tag "$IMAGE" .

gcloud run deploy "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --image "$IMAGE" --min-instances=0 --allow-unauthenticated

gcloud run jobs describe "$JOB" --project "$PROJECT_ID" --region "$REGION" >/dev/null 2>&1 &&
  gcloud run jobs update "$JOB" --project "$PROJECT_ID" --region "$REGION" --image "$IMAGE" ||
  gcloud run jobs create "$JOB" --project "$PROJECT_ID" --region "$REGION" --image "$IMAGE"
