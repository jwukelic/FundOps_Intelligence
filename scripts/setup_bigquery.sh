#!/usr/bin/env bash
# Create or refresh the fundops BigQuery dataset and all tables.
# Safe to run multiple times (CREATE IF NOT EXISTS semantics).
set -euo pipefail

PROJECT_ID="${PROJECT_ID:?PROJECT_ID is required}"

echo "=== Creating BigQuery dataset ==="
bq show --project_id="$PROJECT_ID" fundops >/dev/null 2>&1 || \
  bq mk --location=US --dataset "${PROJECT_ID}:fundops"

echo "=== Creating tables ==="
bq query --project_id="$PROJECT_ID" --use_legacy_sql=false < app/sql/fundops_tables.sql

echo "=== BigQuery setup complete: ${PROJECT_ID}.fundops ==="
