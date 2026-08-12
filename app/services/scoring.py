from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from app.models import ScoreCard, SignalRecord


CATEGORY_WEIGHTS = {
    "intent": 0.4,
    "engagement": 0.3,
    "fit": 0.2,
    "timing": 0.1,
}


def score_entity(entity_key: str, entity_type: str, signals: list[SignalRecord]) -> ScoreCard:
    buckets: dict[str, float] = defaultdict(float)
    supporting_sources: list[str] = []
    now = datetime.now(UTC)
    for signal in signals:
        buckets[signal.signal_type] += signal.score
        if signal.source_url:
            supporting_sources.append(signal.source_url)
        elif signal.source_id:
            supporting_sources.append(signal.source_id)
    freshness_bonus = 10.0 if any(signal.observed_at >= now - timedelta(days=30) for signal in signals) else 0.0
    weighted_score = sum(min(buckets[name] * weight, weight * 100) for name, weight in CATEGORY_WEIGHTS.items())
    total_score = round(min(weighted_score + freshness_bonus, 100.0), 2)
    priority = "High" if total_score >= 80 else "Medium" if total_score >= 55 else "Low"
    reasons = [
        f"Intent contribution: {round(buckets['intent'] * CATEGORY_WEIGHTS['intent'], 2)}",
        f"Engagement contribution: {round(buckets['engagement'] * CATEGORY_WEIGHTS['engagement'], 2)}",
        f"Fit contribution: {round(buckets['fit'] * CATEGORY_WEIGHTS['fit'], 2)}",
        f"Timing contribution: {round(buckets['timing'] * CATEGORY_WEIGHTS['timing'], 2)}",
        f"Freshness bonus: {freshness_bonus}",
    ]
    return ScoreCard(
        entity_key=entity_key,
        entity_type=entity_type,
        total_score=total_score,
        priority=priority,
        reasons=reasons,
        supporting_sources=sorted(set(supporting_sources)),
    )

