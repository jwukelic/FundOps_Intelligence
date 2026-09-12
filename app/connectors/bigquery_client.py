from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InMemoryBigQueryStore:
    """In-memory store for unit testing without real BigQuery credentials."""

    tables: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def insert(self, table_id: str, rows: list[dict[str, Any]]) -> None:
        self.tables.setdefault(table_id, []).extend(rows)

    def query_table(self, table_id: str) -> list[dict[str, Any]]:
        return list(self.tables.get(table_id, []))


class BigQueryClient:
    """Thin wrapper around google-cloud-bigquery with optional in-memory mock.

    Pass ``store`` to use the in-memory mock (tests / local dev).
    Leave ``store=None`` to use a real BigQuery client (production).
    """

    def __init__(
        self,
        project_id: str,
        dataset: str = "fundops",
        store: InMemoryBigQueryStore | None = None,
    ) -> None:
        self.project_id = project_id
        self.dataset = dataset
        self._store = store
        self._client: Any = None

        if store is None:
            from google.cloud import bigquery  # type: ignore[import-untyped]

            self._client = bigquery.Client(project=project_id)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def insert_rows(self, table_id: str, rows: list[dict[str, Any]]) -> list[dict]:
        """Stream ``rows`` into ``{dataset}.{table_id}``.

        Returns a list of row error dicts (empty list means success).
        """
        if self._store is not None:
            self._store.insert(table_id, rows)
            return []

        table_ref = f"{self.project_id}.{self.dataset}.{table_id}"
        errors: list[dict] = self._client.insert_rows_json(table_ref, rows)
        return errors

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def query(self, sql: str) -> list[dict[str, Any]]:
        """Run ``sql`` and return rows as plain dicts."""
        if self._store is not None:
            return []

        job = self._client.query(sql)
        return [dict(row) for row in job.result()]
