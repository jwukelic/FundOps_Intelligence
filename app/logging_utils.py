from __future__ import annotations

import logging

from google.cloud import logging as cloud_logging


def configure_logging(enable_cloud_logging: bool) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if not enable_cloud_logging:
        return
    try:
        client = cloud_logging.Client()
        client.setup_logging()
    except Exception:
        logging.getLogger(__name__).warning("Cloud logging setup failed; using standard logging.")

