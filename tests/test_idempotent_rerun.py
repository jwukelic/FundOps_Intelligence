from app.config import Settings
from app.connectors.google_sheets import GoogleSheetsConnector
from app.connectors.salesforce import InMemorySalesforceStore, SalesforceConnector
from app.pipeline import run_pipeline


class StaticSheets(GoogleSheetsConnector):
    pass


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
