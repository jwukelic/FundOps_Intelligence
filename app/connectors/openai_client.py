from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

from openai import OpenAI

if TYPE_CHECKING:
    from app.services.bigquery_cache import BigQueryAICache


class OpenAIClient:
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5-mini",
        bq_cache: BigQueryAICache | None = None,
    ) -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self._bq_cache = bq_cache
        self._local_cache: dict[str, dict[str, Any]] = {}

    @staticmethod
    def cache_key(prompt: str, content_hash: str) -> str:
        return hashlib.sha256(f"{prompt}|{content_hash}".encode("utf-8")).hexdigest()

    def summarize_opportunity(self, source_url: str, content: str, content_hash: str) -> dict[str, Any]:
        prompt = "Extract opportunity fields with concise summary, next_action, eligibility, confidence, and sources."
        key = self.cache_key(prompt, content_hash)

        if key in self._local_cache:
            return self._local_cache[key]

        if self._bq_cache is not None:
            cached = self._bq_cache.get(key)
            if cached is not None:
                self._local_cache[key] = cached
                return cached

        completion = self.client.responses.create(
            model=self.model,
            temperature=0,
            max_output_tokens=500,
            input=[
                {"role": "system", "content": "You must return strict JSON with source URLs."},
                {"role": "user", "content": f"URL: {source_url}\nContent:\n{content[:8000]}"},
            ],
        )
        output_text = completion.output_text or "{}"
        parsed = json.loads(output_text)
        self._local_cache[key] = parsed
        if self._bq_cache is not None:
            self._bq_cache.put(key, content_hash, self.model, parsed)
        return parsed
