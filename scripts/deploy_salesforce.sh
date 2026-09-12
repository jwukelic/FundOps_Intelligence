#!/usr/bin/env bash
set -euo pipefail

: "${SALESFORCE_ALIAS:?Set SALESFORCE_ALIAS to an authenticated sf org alias}"

sf project deploy start \
  --target-org "${SALESFORCE_ALIAS}" \
  --source-dir salesforce/main/default \
  --ignore-conflicts

