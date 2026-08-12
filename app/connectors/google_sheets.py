from app.models import OpportunityInput


class GoogleSheetsConnector:
    def list_new_or_changed_intake_rows(self) -> list[OpportunityInput]:
        return []

    def mark_processed(self, row_id: str, salesforce_opportunity_id: str, error: str = "") -> None:
        _ = (row_id, salesforce_opportunity_id, error)
