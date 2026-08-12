from __future__ import annotations

from dataclasses import asdict

from fastapi import Depends, FastAPI, Header, HTTPException

from app.config import Settings, get_settings
from app.dependencies import build_runtime
from app.logging_utils import configure_logging
from app.pipeline import PipelineRunner


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.enable_cloud_logging)
    app = FastAPI(title="FundOps Intelligence", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/run/manual")
    def run_manual(
        x_fundops_token: str | None = Header(default=None),
        current_settings: Settings = Depends(get_settings),
    ) -> dict:
        token_required = current_settings.manual_trigger_token_secret
        warehouse, connectors, intelligence, salesforce_writer = build_runtime(current_settings)
        if token_required:
            from app.secrets import GoogleSecretManagerProvider

            token = GoogleSecretManagerProvider(current_settings.gcp_project_id).get(token_required)
            if token and x_fundops_token != token:
                raise HTTPException(status_code=401, detail="Invalid manual trigger token.")
        runner = PipelineRunner(current_settings, warehouse, connectors, intelligence, salesforce_writer)
        return asdict(runner.run())

    return app


app = create_app()
