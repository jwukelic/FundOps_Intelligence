# Setup Production

1. Configure project, APIs, IAM, and Cloud Scheduler:
```bash
PROJECT_ID=<gcp-project> REGION=us-central1 ./scripts/bootstrap_gcp.sh
```
2. Create secret placeholders:
```bash
PROJECT_ID=<gcp-project> ./scripts/create_secrets.sh
```
3. Populate secrets:
```bash
printf '%s' '<value>' | gcloud secrets versions add <secret-name> --data-file=- --project <gcp-project>
```
   Secrets to populate:
   - `fundops-salesforce-username` — Salesforce login username
   - `fundops-salesforce-auth` — Salesforce password + security token (concatenated)
   - `fundops-salesforce-client-id` — Connected app consumer key
   - `fundops-salesforce-client-secret` — Connected app consumer secret
   - `fundops-openai-api-key` — OpenAI API key
   - `fundops-app-secret` — Random string for request signing (generate with `openssl rand -hex 32`)

4. Create BigQuery dataset and tables (if bootstrap_gcp.sh didn't already):
```bash
PROJECT_ID=<gcp-project> ./scripts/setup_bigquery.sh
```
5. Deploy Salesforce metadata:
```bash
SF_TARGET_ORG=<prod-org-alias> ./scripts/deploy_salesforce.sh
```
   Then assign the `FundOps User` permission set to Julie in Salesforce Setup.

6. Deploy Cloud Run service + job:
```bash
PROJECT_ID=<gcp-project> REGION=us-central1 ./scripts/deploy.sh
```
7. Run smoke test:
```bash
BASE_URL=<cloud-run-service-url> ./scripts/smoke_test.sh
```

Connector setup:
- **Salesforce**: populated via secrets above. The connected app needs `api`, `refresh_token`, `offline_access` OAuth scopes.
- **Google Workspace**: the service account used by Cloud Run is granted Drive (read-only) and Sheets (read/write) access via Google Workspace admin domain-wide delegation or direct sharing of the intake sheet and approved folder with the service account email.
- **Mailchimp / Google Ads / Hootsuite**: leave disabled until credentials exist; set `FUNDOPS_CONNECTOR_*_ENABLED=false`.
- **IRS 990**: free — enable with `FUNDOPS_IRS990_ENABLED=true`. No extra credentials needed.
- **OpenAI**: set `fundops-openai-api-key` secret and optionally override `FUNDOPS_OPENAI_MODEL`.

Google Workspace sharing (one-time):
1. Go to the Google Sheet used for intake → Share → add `<sa-name>@<project>.iam.gserviceaccount.com` as Editor.
2. Go to the approved Drive folder → Share → add the same service account as Viewer.
