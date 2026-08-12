#!/usr/bin/env bash
set -euo pipefail

: "${SERVICE_URL:?Set SERVICE_URL}"
MANUAL_TRIGGER_TOKEN="${MANUAL_TRIGGER_TOKEN:-}"

curl --fail --silent --show-error "${SERVICE_URL}/health" | tee /tmp/fundops-health.json

if [[ -n "${MANUAL_TRIGGER_TOKEN}" ]]; then
  curl --fail --silent --show-error \
    -X POST "${SERVICE_URL}/run/manual" \
    -H "x-fundops-token: ${MANUAL_TRIGGER_TOKEN}" \
    -H "content-type: application/json" \
    | tee /tmp/fundops-manual-run.json
fi

