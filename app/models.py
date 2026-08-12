from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class SignalRecord:
    connector: str
    entity_type: str
    entity_key: str
    signal_type: str
    score: float
    external_id: str | None = None
    source_id: str | None = None
    source_url: str | None = None
    summary: str = ""
    raw_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    observed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    raw_hash: str = ""
    signal_id: str = ""


@dataclass(slots=True)
class ContentRecord:
    content_id: str
    connector: str
    entity_key: str
    title: str
    text: str
    approved: bool
    source_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class OpportunityRecord:
    external_id: str
    account_key: str
    name: str
    amount: float | None = None
    stage_name: str = "Prospecting"
    close_date: str | None = None
    source_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class ActionRecommendation:
    action_type: str
    title: str
    details: str
    supporting_sources: list[str]
    due_in_days: int = 3


@dataclass(slots=True)
class IntelligenceBrief:
    summary: str
    inferred_data: bool
    supporting_sources: list[str]
    recommended_actions: list[ActionRecommendation]
    cache_hit: bool = False


@dataclass(slots=True)
class ScoreCard:
    entity_key: str
    entity_type: str
    total_score: float
    priority: str
    reasons: list[str]
    supporting_sources: list[str]


@dataclass(slots=True)
class ConnectorResult:
    signals: list[SignalRecord] = field(default_factory=list)
    content: list[ContentRecord] = field(default_factory=list)
    opportunities: list[OpportunityRecord] = field(default_factory=list)
    public_urls: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PipelineSummary:
    connector_status: dict[str, str]
    signals_processed: int
    entities_scored: int
    opportunities_upserted: int
    tasks_created_or_updated: int
    ai_cache_hits: int


@dataclass(slots=True)
class AuditEvent:
    target_type: str
    target_id: str
    action: str
    before: dict[str, Any]
    after: dict[str, Any]
    changed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

