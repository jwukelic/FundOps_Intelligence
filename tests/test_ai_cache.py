from app.models import ContentRecord, ScoreCard, SignalRecord
from app.services.intelligence import IntelligenceService
from app.storage import InMemoryWarehouse


class CountingModel:
    def __init__(self):
        self.calls = 0

    def generate(self, payload):
        self.calls += 1
        return {
            "summary": "Cached summary",
            "inferred_data": True,
            "supporting_sources": payload["supporting_sources"],
            "recommended_actions": [],
        }


def test_openai_cache_skips_repeat_generation():
    warehouse = InMemoryWarehouse()
    model = CountingModel()
    service = IntelligenceService(warehouse=warehouse, model=model)
    scorecard = ScoreCard("acme", "account", 88.0, "High", ["reason"], ["source-1"])
    signals = [SignalRecord("salesforce", "account", "Acme", "intent", 90, summary="A")]
    content = [ContentRecord("doc-1", "google_drive", "acme", "Memo", "Approved memo", True)]

    first = service.generate("acme", scorecard, signals, content)
    second = service.generate("acme", scorecard, signals, content)

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert model.calls == 1

