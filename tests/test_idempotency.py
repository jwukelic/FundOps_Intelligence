from app.config import Settings
from app.models import ActionRecommendation, ConnectorResult, ContentRecord, IntelligenceBrief, OpportunityRecord, ScoreCard, SignalRecord
from app.pipeline import PipelineRunner
from app.services.intelligence import IntelligenceService
from app.storage import InMemoryWarehouse


class StaticConnector:
    def __init__(self, name, result):
        self.name = name
        self.result = result
        self.enabled = True

    def fetch(self, *, max_records, watermark):
        return self.result


class StubModel:
    def generate(self, payload):
        return {
            "summary": "Use the approved memo",
            "inferred_data": True,
            "supporting_sources": payload["supporting_sources"],
            "recommended_actions": [
                {
                    "action_type": "follow_up",
                    "title": "Confirm next meeting",
                    "details": "Reach out to confirm the next meeting.",
                    "supporting_sources": payload["supporting_sources"],
                    "due_in_days": 2,
                }
            ],
        }


class FakeSalesforceWriter:
    def __init__(self):
        self.tasks = {}
        self.signal_ids = set()
        self.opportunity_ids = set()

    def get_record(self, sobject, record_id):
        return {"Id": record_id}

    def upsert_account(self, account_id, scorecard, brief):
        return None

    def upsert_task(self, what_id, action: ActionRecommendation):
        key = (what_id, action.action_type)
        created = key not in self.tasks
        self.tasks[key] = action.title
        return created

    def upsert_signal_record(self, account_id, opportunity_id, signal):
        self.signal_ids.add(signal.signal_id)

    def upsert_opportunity(self, opportunity, scorecard, brief):
        self.opportunity_ids.add(opportunity.external_id)


def test_rerun_is_idempotent_for_signals_opportunities_and_tasks():
    warehouse = InMemoryWarehouse()
    intelligence = IntelligenceService(warehouse=warehouse, model=StubModel())
    salesforce = FakeSalesforceWriter()
    connector_result = ConnectorResult(
        signals=[
            SignalRecord("salesforce", "account", "Acme", "fit", 35, external_id="001", summary="SF account"),
            SignalRecord("google_sheets", "account", "Acme", "intent", 75, external_id="opp-1:intake", summary="Intake"),
        ],
        content=[ContentRecord("drive-1", "google_drive", "acme", "Memo", "Approved memo", True, source_url="https://drive")],
        opportunities=[OpportunityRecord("opp-1", "Acme", "Gift", 5000, "Prospecting", "2026-09-01")],
    )
    settings = Settings(enable_cloud_logging=False, retry_backoff_seconds=0.0)
    runner = PipelineRunner(settings, warehouse, [StaticConnector("seed", connector_result)], intelligence, salesforce)

    first = runner.run()
    second = runner.run()

    assert first.entities_scored == second.entities_scored == 1
    assert len(warehouse.signals) == 2
    assert len(warehouse.opportunity_intake) == 1
    assert len(salesforce.tasks) == 1

