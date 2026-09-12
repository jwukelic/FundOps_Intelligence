from dataclasses import asdict

from app.models import ScoreComponents


WEIGHTS = {
    "mission_and_program_fit": 0.30,
    "funding_capacity": 0.15,
    "timing_and_current_intent": 0.20,
    "relationship_access": 0.15,
    "internal_readiness": 0.10,
    "engagement_momentum": 0.05,
    "data_confidence": 0.05,
}


def _bounded(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def score_priority(components: ScoreComponents) -> tuple[int, str, dict[str, float]]:
    normalized = {k: _bounded(v) for k, v in asdict(components).items() if k in WEIGHTS}
    if not components.eligibility_gate:
        return 0, "Not Eligible", normalized

    score = round(sum(normalized[k] * WEIGHTS[k] for k in WEIGHTS))
    if score >= 85:
        priority = "Critical"
    elif score >= 70:
        priority = "High"
    elif score >= 50:
        priority = "Medium"
    elif score >= 1:
        priority = "Low"
    else:
        priority = "Not Eligible"
    return int(score), priority, normalized
