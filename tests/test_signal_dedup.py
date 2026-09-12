from datetime import datetime, timedelta, timezone

from app.models import Signal
from app.services.signal_normalization import deduplicate_signals


def test_signal_dedup_keeps_latest_for_same_external_id():
    now = datetime.now(timezone.utc)
    a = Signal("x", "001", "Believe in Me", "Priority", 50, 60, "old", "FundOps", "u", now, "h1")
    b = Signal("x", "001", "Believe in Me", "Priority", 90, 90, "new", "FundOps", "u", now + timedelta(minutes=1), "h2")
    out = deduplicate_signals([a, b])
    assert len(out) == 1
    assert out[0].summary == "new"
