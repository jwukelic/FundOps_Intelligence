import logging
import os
import sys

import uvicorn
from fastapi import FastAPI

from app.config import get_settings
from app.connectors.bigquery_client import BigQueryClient
from app.connectors.google_drive import GoogleDriveConnector
from app.connectors.google_sheets import GoogleSheetsConnector
from app.connectors.irs990 import Irs990Connector
from app.connectors.salesforce import SalesforceConnector
from app.pipeline import run_pipeline
from app.services.bigquery_writer import BigQueryWriter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="FundOps Intelligence", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/run")
def run() -> dict:
    return _execute_pipeline()


# ---------------------------------------------------------------------------
# Shared pipeline execution
# ---------------------------------------------------------------------------


def _execute_pipeline() -> dict:
    settings = get_settings()
    salesforce = SalesforceConnector()
    sheets = GoogleSheetsConnector(sheet_id=settings.fundops_intake_sheet_id)
    drive = GoogleDriveConnector(folder_id=settings.fundops_approved_drive_folder_id)
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


# ---------------------------------------------------------------------------
# Cloud Run job entrypoint
# ---------------------------------------------------------------------------


def _run_job() -> None:
    """Execute the pipeline once and exit.  Used as the Cloud Run job command."""
    logger.info("FundOps Intelligence job starting")
    result = _execute_pipeline()
    logger.info("Job complete: %s", result)
    if result["error_count"] > 0:
        logger.warning("Job finished with %d error(s)", result["error_count"])
        sys.exit(1)
    sys.exit(0)


# ---------------------------------------------------------------------------
# Entrypoint dispatcher
# ---------------------------------------------------------------------------


def main() -> None:
    settings = get_settings()
    run_mode = os.environ.get("RUN_MODE", "service").lower()
    if run_mode == "job":
        _run_job()
    else:
        uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
