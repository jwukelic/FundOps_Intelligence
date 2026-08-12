from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class ScoreComponents:
    mission_and_program_fit: float
    funding_capacity: float
    timing_and_current_intent: float
    relationship_access: float
    internal_readiness: float
    engagement_momentum: float
    data_confidence: float
    eligibility_gate: bool = True


@dataclass(slots=True)
class Signal:
    external_id: str
    account_id: str
    program: str
    signal_type: str
    strength: float
    confidence: float
    summary: str
    source_name: str
    source_url: str
    observed_at: datetime
    raw_hash: str


@dataclass(slots=True)
class OpportunityInput:
    url: str
    organization: str
    program: str
    opportunity_type: str
    notes: str = ""
    row_id: str = ""


@dataclass(slots=True)
class PipelineResult:
    processed_accounts: int = 0
    scored_accounts: int = 0
    created_or_updated_tasks: int = 0
    processed_opportunities: int = 0
    errors: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
