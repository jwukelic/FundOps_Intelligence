from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.connectors.bigquery_client import BigQueryClient


class BigQueryAICache:
    """Persistent AI call cache backed by the BigQuery ``fundops.ai_cache`` table.

    On a cache hit the parsed JSON dict is returned immediately, saving an
    OpenAI API call.  On a miss the caller is responsible for making the API
    call and then calling :meth:`put` so the result is stored for future runs.
    """

    def __init__(self, bq: BigQueryClient) -> None:
        self._bq = bq

    def get(self, cache_key: str) -> dict[str, Any] | None:
        """Return the cached output for *cache_key*, or ``None`` on a miss."""
        if self._bq._store is not None:
            # In-memory path: scan the in-memory store directly.
            rows = self._bq._store.query_table("ai_cache")
            matches = [r for r in rows if r.get("cache_key") == cache_key]
            if not matches:
                return None
            latest = max(matches, key=lambda r: r.get("created_at", ""))
            return json.loads(latest["output_json"])

        safe_key = cache_key.replace("'", "''")
        sql = f"""
            SELECT output_json
            FROM `{self._bq.project_id}.{self._bq.dataset}.ai_cache`
            WHERE cache_key = '{safe_key}'
            ORDER BY created_at DESC
            LIMIT 1
        """
        rows = self._bq.query(sql)
        if not rows:
            return None
        return json.loads(rows[0]["output_json"])

    def put(self, cache_key: str, input_hash: str, model: str, output: dict[str, Any]) -> None:
        """Persist *output* in the cache table under *cache_key*."""
        now = datetime.now(timezone.utc)
        self._bq.insert_rows(
            "ai_cache",
            [
                {
                    "cache_date": now.date().isoformat(),
                    "cache_key": cache_key,
                    "input_hash": input_hash,
                    "model": model,
                    "output_json": json.dumps(output),
                    "created_at": now.isoformat(),
                }
            ],
        )
