from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from app.models import ConnectorResult


class Connector(Protocol):
    name: str
    enabled: bool

    def fetch(self, *, max_records: int, watermark: str | None) -> ConnectorResult: ...


def iso_now() -> str:
    return datetime.now(UTC).isoformat()

