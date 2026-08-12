from app.connectors.google_sheets import GoogleSheetsConnector
from app.connectors.salesforce import SalesforceConnector, SalesforceCredentials


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeTransport:
    def __init__(self):
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if url.endswith("/services/oauth2/token"):
            return FakeResponse({"access_token": "token", "instance_url": "https://example.my.salesforce.com"})
        return FakeResponse({"records": []})


def test_salesforce_connector_auth_uses_password_and_security_token():
    transport = FakeTransport()
    connector = SalesforceConnector(
        SalesforceCredentials("https://login.salesforce.com", "client", "secret", "user", "pass", "token"),
        enabled=True,
        transport=transport,
    )

    headers = connector._headers()

    assert headers["Authorization"].startswith("Bearer ")
    assert headers["Authorization"].endswith("token")
    assert transport.calls[0][2]["data"]["password"] == "passtoken"


def test_google_sheets_connector_normalizes_rows(monkeypatch):
    class FakeExecute:
        def execute(self):
            return {"values": [["id", "account", "name", "amount", "stage", "close", "url"], ["opp-1", "Acme", "Gift", "5000", "Qualification", "2026-09-01", "https://sheet"]]}

    class FakeValues:
        def get(self, **kwargs):
            return FakeExecute()

    class FakeSheets:
        def values(self):
            return FakeValues()

    class FakeSpreadsheet:
        def spreadsheets(self):
            return FakeSheets()

    monkeypatch.setattr("app.connectors.google_sheets.build", lambda *args, **kwargs: FakeSpreadsheet())
    connector = GoogleSheetsConnector("sheet-id", "Sheet1!A:G", enabled=True, credentials=object())

    result = connector.fetch(max_records=5, watermark=None)

    assert result.opportunities[0].external_id == "opp-1"
    assert result.signals[0].metadata["stage_name"] == "Qualification"
