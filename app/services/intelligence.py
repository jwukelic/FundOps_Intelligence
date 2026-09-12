from app.models import ScoreComponents


def build_account_summary(program: str, score: int, priority: str, unknowns: list[str]) -> str:
    unknown_text = "Unknowns: " + ", ".join(unknowns) if unknowns else "Unknowns: none flagged"
    return (
        f"Program: {program}. Priority score {score} ({priority}). "
        "Verified facts and observed behaviors are weighted above inference. "
        f"{unknown_text}"
    )


def recommend_next_action(components: ScoreComponents) -> str:
    if not components.eligibility_gate:
        return "Close as ineligible"
    if components.relationship_access < 50:
        return "Request a board introduction"
    if components.timing_and_current_intent < 45:
        return "Research missing eligibility information"
    if components.mission_and_program_fit >= 75:
        return "Schedule a discovery meeting"
    return "Monitor for the next funding cycle"
