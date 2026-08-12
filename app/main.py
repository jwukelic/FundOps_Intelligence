from fastapi import FastAPI

from app.config import get_settings
from app.connectors.google_sheets import GoogleSheetsConnector
from app.connectors.salesforce import SalesforceConnector
from app.pipeline import run_pipeline

app = FastAPI(title="FundOps Intelligence", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/run")
def run() -> dict:
    settings = get_settings()
    salesforce = SalesforceConnector()
    sheets = GoogleSheetsConnector()
    result = run_pipeline(settings=settings, salesforce=salesforce, sheets=sheets)
    return {
        "processed_accounts": result.processed_accounts,
        "scored_accounts": result.scored_accounts,
        "created_or_updated_tasks": result.created_or_updated_tasks,
        "processed_opportunities": result.processed_opportunities,
        "errors": result.errors,
    }
