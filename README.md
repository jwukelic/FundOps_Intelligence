# FundOps Intelligence

FundOps Intelligence is a lean, production-first fundraising intelligence MVP built for Cloud Run service + job deployment from one shared Python 3.12 FastAPI container image. It combines Salesforce, BigQuery, Google Drive/Sheets, and low-cost structured AI to produce explainable scores, opportunity updates, deduplicated `[FundOps]` tasks, and auditable reruns.

## Repository Layout

```text
app/                  FastAPI app, pipeline, connectors, SQL
docs/                 Architecture, setup, runbook, decisions, backlog
salesforce/           Metadata for Account, Opportunity, FundOps_Signal__c
scripts/              Idempotent bootstrap, deploy, run, smoke, rollback scripts
tests/                Focused MVP tests
```

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install ".[dev]"
cp .env.example .env
pytest
uvicorn app.main:app --reload
```

## Endpoints

- `GET /health`
- `POST /run/manual`

## Deployment

```bash
chmod +x scripts/*.sh
PROJECT_ID=your-project REGION=us-central1 scripts/bootstrap_gcp.sh
PROJECT_ID=your-project scripts/create_secrets.sh
PROJECT_ID=your-project REGION=us-central1 scripts/deploy.sh
SERVICE_URL="$(gcloud run services describe fundops-intelligence --region us-central1 --format='value(status.url)')"
SERVICE_URL="$SERVICE_URL" scripts/smoke_test.sh
```

See `/docs` for production setup, the lean data model, the runbook, and the explicit assumptions/deferred work.
