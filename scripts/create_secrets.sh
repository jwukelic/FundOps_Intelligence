#!/usr/bin/env bash
set -euo pipefail

: "${PROJECT_ID:?Set PROJECT_ID}"

SECRETS=(
  fundops-manual-trigger-token
  fundops-openai-api-key
  fundops-salesforce-base-url
  fundops-salesforce-client-id
  fundops-salesforce-client-secret
  fundops-salesforce-username
  fundops-salesforce-password
  fundops-salesforce-security-token
  fundops-mailchimp-api-key
  fundops-mailchimp-server-prefix
  fundops-google-ads-developer-token
  fundops-google-ads-oauth-token
  fundops-hootsuite-api-token
)

for secret in "${SECRETS[@]}"; do
  if gcloud secrets describe "${secret}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    echo "Secret exists: ${secret}"
  else
    printf 'replace-me\n' | gcloud secrets create "${secret}" \
      --project "${PROJECT_ID}" \
      --replication-policy automatic \
      --data-file=-
    echo "Created placeholder secret: ${secret}"
  fi
done

