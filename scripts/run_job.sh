#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?PROJECT_ID is required}"
REGION="${REGION:-us-central1}"
JOB="${JOB:-fundops-intelligence-job}"

gcloud run jobs execute "$JOB" --project "$PROJECT_ID" --region "$REGION" --wait
