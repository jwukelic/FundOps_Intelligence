from app.config import Settings
from app.connectors.google_sheets import GoogleSheetsConnector
from app.connectors.salesforce import InMemorySalesforceStore, SalesforceConnector
from app.models import OpportunityInput
from app.pipeline import _opportunity_external_id, run_pipeline


class StaticSheets(GoogleSheetsConnector):
    def list_new_or_changed_intake_rows(self) -> list[OpportunityInput]:
        return [
            OpportunityInput(
                row_id="1",
                url="https://example.org/opportunities/grant",
                organization="Example Org",
                program="Believe in Me",
                opportunity_type="Grant",
            )
        ]


def test_rerun_does_not_duplicate_tasks_or_signals_or_opportunities():
    store = InMemorySalesforceStore(
        accounts={"001": {"Id": "001", "FundOps_Enabled__c": True, "FundOps_Primary_Program__c": "Believe in Me"}},
        opportunities={},
        tasks={},
        signals={},
    )
    connector = SalesforceConnector(store)
    settings = Settings(fundops_max_accounts=5)
    sheets = StaticSheets()

    run_pipeline(settings, connector, sheets)
    first_counts = (len(store.tasks), len(store.signals), len(store.opportunities))
    run_pipeline(settings, connector, sheets)
    second_counts = (len(store.tasks), len(store.signals), len(store.opportunities))

    assert first_counts == second_counts


def test_opportunity_external_id_is_stable_for_same_url():
    url = "https://example.org/opportunities/grant"

    assert _opportunity_external_id(url) == _opportunity_external_id(url)
    assert _opportunity_external_id(url) == _opportunity_external_id(f" {url} ")
