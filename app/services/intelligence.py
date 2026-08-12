from __future__ import annotations

import hashlib
import json
from typing import Any, Protocol

from app.models import ActionRecommendation, ContentRecord, IntelligenceBrief, ScoreCard, SignalRecord


class AIModel(Protocol):
    def generate(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class FallbackAIModel:
    def generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        top_sources = payload["supporting_sources"][:3]
        priority = payload["priority"]
        return {
            "summary": f"{payload['entity_key']} is currently {priority.lower()} priority based on recent approved evidence and operational signals.",
            "inferred_data": True,
            "supporting_sources": top_sources,
            "recommended_actions": [
                {
                    "action_type": "follow_up",
                    "title": "Confirm next funding conversation",
                    "details": f"Use the top evidence sources to confirm the next conversation for {payload['entity_key']}.",
                    "supporting_sources": top_sources,
                    "due_in_days": 3,
                }
            ],
        }


class IntelligenceService:
    def __init__(self, warehouse: Any, model: AIModel | None = None) -> None:
        self.warehouse = warehouse
        self.model = model or FallbackAIModel()

    def generate(self, entity_key: str, scorecard: ScoreCard, signals: list[SignalRecord], contents: list[ContentRecord]) -> IntelligenceBrief:
        payload = {
            "entity_key": entity_key,
            "priority": scorecard.priority,
            "score": scorecard.total_score,
            "reasons": scorecard.reasons,
            "supporting_sources": scorecard.supporting_sources,
            "signals": [
                {"signal_type": signal.signal_type, "summary": signal.summary, "source_id": signal.source_id, "source_url": signal.source_url}
                for signal in signals
            ],
            "content": [
                {"content_id": item.content_id, "title": item.title, "text": item.text[:500], "source_url": item.source_url}
                for item in contents
            ],
        }
        input_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        cached = self.warehouse.get_ai_cache(input_hash)
        if cached:
            return self._from_payload(cached, cache_hit=True)
        response = self.model.generate(payload)
        self.warehouse.put_ai_cache(input_hash, response)
        return self._from_payload(response, cache_hit=False)

    @staticmethod
    def _from_payload(payload: dict[str, Any], *, cache_hit: bool) -> IntelligenceBrief:
        return IntelligenceBrief(
            summary=payload["summary"],
            inferred_data=payload.get("inferred_data", False),
            supporting_sources=payload.get("supporting_sources", []),
            recommended_actions=[
                ActionRecommendation(
                    action_type=item["action_type"],
                    title=item["title"],
                    details=item["details"],
                    supporting_sources=item.get("supporting_sources", []),
                    due_in_days=item.get("due_in_days", 3),
                )
                for item in payload.get("recommended_actions", [])
            ],
            cache_hit=cache_hit,
        )

