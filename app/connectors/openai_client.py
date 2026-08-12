from __future__ import annotations

from typing import Any

from openai import OpenAI


class OpenAIJSONModel:
    def __init__(self, api_key: str, model: str, temperature: float, max_output_tokens: int) -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.client.responses.create(
            model=self.model,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "Return strict JSON with summary, inferred_data, supporting_sources, and recommended_actions.",
                        }
                    ],
                },
                {"role": "user", "content": [{"type": "input_text", "text": str(payload)}]},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "fundops_intelligence",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "summary": {"type": "string"},
                            "inferred_data": {"type": "boolean"},
                            "supporting_sources": {"type": "array", "items": {"type": "string"}},
                            "recommended_actions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "action_type": {"type": "string"},
                                        "title": {"type": "string"},
                                        "details": {"type": "string"},
                                        "supporting_sources": {"type": "array", "items": {"type": "string"}},
                                        "due_in_days": {"type": "integer"},
                                    },
                                    "required": ["action_type", "title", "details", "supporting_sources", "due_in_days"],
                                    "additionalProperties": False,
                                },
                            },
                        },
                        "required": ["summary", "inferred_data", "supporting_sources", "recommended_actions"],
                        "additionalProperties": False,
                    },
                }
            },
        )
        return response.output_parsed

