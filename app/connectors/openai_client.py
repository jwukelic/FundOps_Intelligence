import hashlib
import json
from typing import Any

from openai import OpenAI


class OpenAIClient:
    def __init__(self, api_key: str, model: str = "gpt-5-mini") -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.cache: dict[str, dict[str, Any]] = {}

    @staticmethod
    def cache_key(prompt: str, content_hash: str) -> str:
        return hashlib.sha256(f"{prompt}|{content_hash}".encode("utf-8")).hexdigest()

    def summarize_opportunity(self, source_url: str, content: str, content_hash: str) -> dict[str, Any]:
        prompt = "Extract opportunity fields with concise summary, next_action, eligibility, confidence, and sources."
        key = self.cache_key(prompt, content_hash)
        if key in self.cache:
            return self.cache[key]

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
        self.cache[key] = parsed
        return parsed
