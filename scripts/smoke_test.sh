#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:?BASE_URL is required}"

curl -fsS "$BASE_URL/health" >/dev/null
curl -fsS -X POST "$BASE_URL/run" -H 'Content-Type: application/json' >/dev/null

echo "Smoke test passed"
