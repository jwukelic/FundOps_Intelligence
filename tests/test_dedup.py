from app.models import SignalRecord
from app.services.normalization import normalize_signals


def test_signal_dedup_prefers_external_id_then_hash():
    one = SignalRecord("google_sheets", "account", "Acme", "intent", 50, external_id="opp-1", summary="A")
    two = SignalRecord("google_sheets", "account", "Acme", "intent", 50, external_id="opp-1", summary="A newer")
    three = SignalRecord("google_drive", "account", "Acme", "fit", 20, summary="B")
    four = SignalRecord("google_drive", "account", "Acme", "fit", 20, summary="B")

    normalized = normalize_signals([one, two, three, four])

    assert len(normalized) == 2
    assert {signal.connector for signal in normalized} == {"google_sheets", "google_drive"}

