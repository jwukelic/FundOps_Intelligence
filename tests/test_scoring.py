from datetime import UTC, datetime

from app.models import SignalRecord
from app.services.scoring import score_entity


def test_score_formula_is_deterministic_and_explainable():
    signals = [
        SignalRecord("salesforce", "account", "Acme", "intent", 80, observed_at=datetime.now(UTC), summary="Gift interest"),
        SignalRecord("google_sheets", "account", "Acme", "engagement", 60, observed_at=datetime.now(UTC), summary="Intake row"),
        SignalRecord("google_drive", "account", "Acme", "fit", 50, observed_at=datetime.now(UTC), summary="Board memo"),
        SignalRecord("salesforce", "account", "Acme", "timing", 40, observed_at=datetime.now(UTC), summary="Fiscal year end"),
    ]

    scorecard = score_entity("acme", "account", signals)

    assert scorecard.total_score == 74.0
    assert scorecard.priority == "Medium"
    assert len(scorecard.reasons) == 5
