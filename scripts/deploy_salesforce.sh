#!/usr/bin/env bash
set -euo pipefail

sf project deploy start --source-dir salesforce/main/default --target-org "${SF_TARGET_ORG:?SF_TARGET_ORG is required}"
