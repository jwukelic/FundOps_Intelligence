# Setup Production

1. Configure project and APIs:
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
4. Deploy Salesforce metadata:
```bash
SF_TARGET_ORG=<prod-org-alias> ./scripts/deploy_salesforce.sh
```
5. Deploy Cloud Run service + job:
```bash
PROJECT_ID=<gcp-project> REGION=us-central1 ./scripts/deploy.sh
```
6. Create scheduler (daily UTC 12:00):
```bash
gcloud scheduler jobs create http fundops-daily --location=us-central1 --schedule='0 12 * * *' --uri='<cloud-run-job-trigger-url>' --http-method=POST
```
7. Run smoke test:
```bash
BASE_URL=<cloud-run-service-url> ./scripts/smoke_test.sh
```

Connector setup:
- Salesforce: connected app/oauth + username/auth secrets.
- Google Workspace: intake sheet ID and approved folder ID env values.
- Mailchimp/Google Ads/Hootsuite: leave disabled until secrets exist.
- OpenAI: set `fundops-openai-api-key` and model env.
