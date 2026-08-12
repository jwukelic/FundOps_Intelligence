from fastapi import FastAPI

from app.config import get_settings
from app.connectors.bigquery_client import BigQueryClient
from app.connectors.google_drive import GoogleDriveConnector
from app.connectors.google_sheets import GoogleSheetsConnector
from app.connectors.irs990 import Irs990Connector
from app.connectors.salesforce import SalesforceConnector
from app.pipeline import run_pipeline
from app.services.bigquery_writer import BigQueryWriter

app = FastAPI(title="FundOps Intelligence", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/run")
def run() -> dict:
    settings = get_settings()
    salesforce = SalesforceConnector()
    sheets = GoogleSheetsConnector()
    drive = GoogleDriveConnector()
    bq_writer: BigQueryWriter | None = None
    irs990: Irs990Connector | None = None
    if settings.fundops_project_id:
        bq = BigQueryClient(
            project_id=settings.fundops_project_id,
            dataset=settings.fundops_bigquery_dataset,
        )
        bq_writer = BigQueryWriter(bq)
        if settings.fundops_irs990_enabled:
            irs990 = Irs990Connector(bq)
    result = run_pipeline(
        settings=settings,
        salesforce=salesforce,
        sheets=sheets,
        bq_writer=bq_writer,
        drive=drive,
        irs990=irs990,
    )
    return {
        "processed_accounts": result.processed_accounts,
        "scored_accounts": result.scored_accounts,
        "created_or_updated_tasks": result.created_or_updated_tasks,
        "processed_opportunities": result.processed_opportunities,
        "error_count": len(result.errors),
    }
