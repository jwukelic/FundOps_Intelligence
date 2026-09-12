from __future__ import annotations

import uvicorn

from app.config import get_settings
from app.dependencies import build_runtime
from app.main import app
from app.pipeline import PipelineRunner


def main() -> None:
    settings = get_settings()
    if settings.run_mode == "job":
        warehouse, connectors, intelligence, salesforce_writer = build_runtime(settings)
        PipelineRunner(settings, warehouse, connectors, intelligence, salesforce_writer).run()
        return
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()

