from app.models import ScoreComponents
from app.scoring import score_priority


def test_scoring_formula_and_priority():
    score, priority, _ = score_priority(
        ScoreComponents(
            mission_and_program_fit=90,
            funding_capacity=70,
            timing_and_current_intent=80,
            relationship_access=60,
            internal_readiness=70,
            engagement_momentum=50,
            data_confidence=80,
            eligibility_gate=True,
        )
    )
    assert score == 76
    assert priority == "High"


def test_eligibility_gate_zeroes_score():
    score, priority, _ = score_priority(
        ScoreComponents(20, 20, 20, 20, 20, 20, 20, eligibility_gate=False)
    )
    assert score == 0
    assert priority == "Not Eligible"
