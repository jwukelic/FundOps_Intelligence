# Setup Production

## 1. Bootstrap GCP

```bash
chmod +x scripts/*.sh
PROJECT_ID=your-project \
REGION=us-central1 \
REPOSITORY=fundops-intelligence \
DATASET=fundops \
JOB_NAME=fundops-intelligence-job \
SERVICE_NAME=fundops-intelligence \
SCHEDULER_JOB_NAME=fundops-daily-sync \
SCHEDULER_SA=scheduler-invoker@your-project.iam.gserviceaccount.com \
scripts/bootstrap_gcp.sh
```

## 2. Create placeholder secrets

```bash
PROJECT_ID=your-project scripts/create_secrets.sh
```

Replace placeholder values with real secret versions using `gcloud secrets versions add`.

## 3. Deploy Salesforce metadata

```bash
sf org login web --alias fundops-prod
SALESFORCE_ALIAS=fundops-prod scripts/deploy_salesforce.sh
```

## 4. Deploy service + job

```bash
PROJECT_ID=your-project REGION=us-central1 scripts/deploy.sh
```

## 5. Run smoke test

```bash
SERVICE_URL="$(gcloud run services describe fundops-intelligence --project your-project --region us-central1 --format='value(status.url)')"
MANUAL_TRIGGER_TOKEN="$(gcloud secrets versions access latest --secret fundops-manual-trigger-token --project your-project)"
SERVICE_URL="$SERVICE_URL" MANUAL_TRIGGER_TOKEN="$MANUAL_TRIGGER_TOKEN" scripts/smoke_test.sh
```

