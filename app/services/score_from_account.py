"""score_from_account — derive ScoreComponents from observed data.

Signal-type to component mapping
---------------------------------
The following ``Signal_Type__c`` values are recognized and used to populate
the corresponding ScoreComponent when signals are present.  Any type not in
this map contributes to ``engagement_momentum`` as a catch-all for observed
activity.

  MissionFit          → mission_and_program_fit
  FundingCapacity     → funding_capacity
  TimingIntent        → timing_and_current_intent
  RelationshipAccess  → relationship_access
  InternalReadiness   → internal_readiness
  EngagementMomentum  → engagement_momentum
  DataConfidence      → data_confidence  (overrides the auto-computed value)

Any type not in the map contributes to ``engagement_momentum``.

Default component values
------------------------
When no signals are available for a component the following defaults are used
so the pipeline can still produce a meaningful (conservative) score:

  mission_and_program_fit      50
  funding_capacity             40
  timing_and_current_intent    40
  relationship_access          30
  internal_readiness           50
  engagement_momentum          30

Data confidence is computed automatically as a function of how many distinct
signal sources exist (capped at 90).  Passing an explicit ``DataConfidence``
signal overrides this value.
"""

from __future__ import annotations

from app.connectors.google_drive import DriveDocument
from app.models import ScoreComponents


_SIGNAL_TYPE_TO_COMPONENT: dict[str, str] = {
    "MissionFit": "mission_and_program_fit",
    "FundingCapacity": "funding_capacity",
    "TimingIntent": "timing_and_current_intent",
    "RelationshipAccess": "relationship_access",
    "InternalReadiness": "internal_readiness",
    "EngagementMomentum": "engagement_momentum",
    "DataConfidence": "data_confidence",
}

_DEFAULTS: dict[str, float] = {
    "mission_and_program_fit": 50.0,
    "funding_capacity": 40.0,
    "timing_and_current_intent": 40.0,
    "relationship_access": 30.0,
    "internal_readiness": 50.0,
    "engagement_momentum": 30.0,
}

# Drive documents act as weak positive signals for these components when
# their content is available.
_DRIVE_BOOST = 5.0


def score_from_account(
    account: dict,
    signals: list[dict],
    drive_docs: list[DriveDocument] | None = None,
) -> ScoreComponents:
    """Compute ScoreComponents for *account* given its *signals* and optional *drive_docs*.

    The algorithm:
    1. Group signal strengths by mapped component name; average each group.
    2. For components without signals use ``_DEFAULTS``.
    3. Apply a small boost for each approved Drive document that mentions the
       account's program (capped to avoid overweighting thin evidence).
    4. Compute ``data_confidence`` from number of distinct source names, unless
       a ``DataConfidence`` signal overrides it.
    5. Apply ``eligibility_gate`` based on the Salesforce Eligibility field if
       present (Opportunity flow), defaulting to ``True``.
    """
    # ------------------------------------------------------------------
    # Aggregate signals by component
    # ------------------------------------------------------------------
    buckets: dict[str, list[float]] = {}
    explicit_confidence: float | None = None

    for sig in signals:
        raw_type = sig.get("Signal_Type__c", "")
        component = _SIGNAL_TYPE_TO_COMPONENT.get(raw_type)
        if raw_type == "DataConfidence":
            explicit_confidence = float(sig.get("Strength__c", 50))
            continue
        if component is None:
            component = "engagement_momentum"
        buckets.setdefault(component, []).append(float(sig.get("Strength__c", 50)))

    # Average each bucket
    component_values: dict[str, float] = {}
    for comp, strengths in buckets.items():
        component_values[comp] = sum(strengths) / len(strengths)

    # Fill in defaults for any missing component
    for comp, default in _DEFAULTS.items():
        if comp not in component_values:
            component_values[comp] = default

    # ------------------------------------------------------------------
    # Drive document boost
    # ------------------------------------------------------------------
    if drive_docs:
        program = account.get("FundOps_Primary_Program__c", "")
        for doc in drive_docs:
            if doc.approval_status != "approved":
                continue
            if program and program.lower() in doc.program.lower():
                for comp in (
                    "mission_and_program_fit",
                    "internal_readiness",
                    "data_confidence" if explicit_confidence is None else "__skip__",
                ):
                    if comp == "__skip__":
                        continue
                    component_values[comp] = min(100.0, component_values.get(comp, _DEFAULTS.get(comp, 50.0)) + _DRIVE_BOOST)

    # ------------------------------------------------------------------
    # Data confidence
    # ------------------------------------------------------------------
    if explicit_confidence is not None:
        data_confidence = explicit_confidence
    else:
        distinct_sources = len({s.get("Source_Name__c", "") for s in signals if s.get("Source_Name__c")})
        # 50 base + 10 per distinct source, capped at 90
        data_confidence = min(90.0, 50.0 + distinct_sources * 10.0)

    return ScoreComponents(
        mission_and_program_fit=component_values["mission_and_program_fit"],
        funding_capacity=component_values["funding_capacity"],
        timing_and_current_intent=component_values["timing_and_current_intent"],
        relationship_access=component_values["relationship_access"],
        internal_readiness=component_values["internal_readiness"],
        engagement_momentum=component_values["engagement_momentum"],
        data_confidence=data_confidence,
        eligibility_gate=True,
    )
