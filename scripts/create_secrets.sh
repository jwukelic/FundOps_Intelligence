#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?PROJECT_ID is required}"

secrets=(
  fundops-salesforce-client-id
  fundops-salesforce-client-secret
  fundops-salesforce-username
  fundops-salesforce-auth
  fundops-mailchimp-api-key
  fundops-mailchimp-server-prefix
  fundops-google-ads-developer-token
  fundops-google-ads-customer-id
  fundops-google-ads-login-customer-id
  fundops-google-oauth-client
  fundops-hootsuite-token
  fundops-openai-api-key
  fundops-app-secret
)

for name in "${secrets[@]}"; do
  gcloud secrets describe "$name" --project "$PROJECT_ID" >/dev/null 2>&1 || \
    gcloud secrets create "$name" --replication-policy=automatic --project "$PROJECT_ID"
done

echo "Populate secrets with: printf '%s' 'value' | gcloud secrets versions add SECRET_NAME --data-file=- --project $PROJECT_ID"
