from __future__ import annotations

from app.models import SignalRecord


def canonical_entity_key(signal: SignalRecord) -> str:
    return signal.entity_key.strip().lower()

