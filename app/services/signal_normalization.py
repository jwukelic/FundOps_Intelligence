import hashlib
from typing import Iterable

from app.models import Signal


def signal_hash(parts: list[str]) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def deduplicate_signals(signals: Iterable[Signal]) -> list[Signal]:
    deduped: dict[str, Signal] = {}
    for signal in signals:
        key = signal.external_id or signal.raw_hash
        if not key:
            key = signal_hash([
                signal.account_id,
                signal.program,
                signal.signal_type,
                signal.source_url,
                signal.summary.strip(),
            ])
        existing = deduped.get(key)
        if existing is None or signal.observed_at > existing.observed_at:
            deduped[key] = signal
    return list(deduped.values())
