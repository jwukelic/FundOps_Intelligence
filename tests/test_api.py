from fastapi.testclient import TestClient

from app.main import create_app
from app.models import PipelineSummary


def test_health_and_manual_trigger_endpoints(monkeypatch):
    def fake_build_runtime(settings):
        class EmptyWarehouse:
            def ensure_tables(self):
                return None

            def get_sync_state(self, connector_name):
                return None

            def set_sync_state(self, connector_name, watermark):
                return None

            def append_connector_run(self, payload):
                return None

            def upsert_signal(self, signal):
                return True

            def list_opportunities(self):
                return []

            def list_signals_for_entity(self, entity_key):
                return []

            def upsert_score(self, scorecard):
                return None

            def list_content(self, entity_key):
                return []

            def append_audit(self, event):
                return None

            def get_ai_cache(self, input_hash):
                return None

            def put_ai_cache(self, input_hash, payload):
                return None

            def upsert_content(self, content):
                return None

            def upsert_opportunity_intake(self, opportunity):
                return None

        class NoopIntelligence:
            def generate(self, entity_key, scorecard, signals, contents):
                raise AssertionError("No entity should be scored in this empty test.")

        return EmptyWarehouse(), [], NoopIntelligence(), None

    monkeypatch.setattr("app.main.build_runtime", fake_build_runtime)
    app = create_app()
    client = TestClient(app)

    health = client.get("/health")
    manual = client.post("/run/manual")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert manual.status_code == 200
    assert manual.json() == {
        "connector_status": {},
        "signals_processed": 0,
        "entities_scored": 0,
        "opportunities_upserted": 0,
        "tasks_created_or_updated": 0,
        "ai_cache_hits": 0,
    }
