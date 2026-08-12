from __future__ import annotations

import hashlib
import json

from app.models import SignalRecord


def signal_hash(signal: SignalRecord) -> str:
    payload = {
        "connector": signal.connector,
        "entity_type": signal.entity_type,
        "entity_key": signal.entity_key,
        "signal_type": signal.signal_type,
        "external_id": signal.external_id,
        "source_id": signal.source_id,
        "summary": signal.summary,
        "metadata": signal.metadata,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def normalize_signals(signals: list[SignalRecord]) -> list[SignalRecord]:
    deduped: dict[str, SignalRecord] = {}
    for signal in signals:
        raw_hash = signal.raw_hash or signal_hash(signal)
        signal.raw_hash = raw_hash
        signal.signal_id = signal.signal_id or f"{signal.connector}:{signal.external_id or raw_hash}"
        dedupe_key = signal.external_id or raw_hash
        if dedupe_key not in deduped:
            deduped[dedupe_key] = signal
    return list(deduped.values())

