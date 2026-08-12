# Runbook

## Manual job run

```bash
PROJECT_ID=your-project REGION=us-central1 scripts/run_job.sh
```

## Manual API trigger

```bash
SERVICE_URL="$(gcloud run services describe fundops-intelligence --project your-project --region us-central1 --format='value(status.url)')"
MANUAL_TRIGGER_TOKEN="$(gcloud secrets versions access latest --secret fundops-manual-trigger-token --project your-project)"
curl -X POST "${SERVICE_URL}/run/manual" -H "x-fundops-token: ${MANUAL_TRIGGER_TOKEN}"
```

## Roll back

```bash
PROJECT_ID=your-project \
REGION=us-central1 \
PREVIOUS_SERVICE_REVISION=fundops-intelligence-00012-abc \
PREVIOUS_JOB_IMAGE=us-central1-docker.pkg.dev/your-project/fundops-intelligence/fundops-intelligence:previous \
scripts/rollback.sh
```

## Safety rules

- Only approved content is indexed.
- Public URL fetches are opt-in and user-provided only.
- No outbound automation is performed.
- Inferred data is explicitly labeled.
- Connector failures are isolated; reruns are safe and idempotent.

