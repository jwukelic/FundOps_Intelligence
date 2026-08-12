from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.models import ActionRecommendation, ConnectorResult, IntelligenceBrief, OpportunityRecord, ScoreCard, SignalRecord


class Transport(Protocol):
    def request(self, method: str, url: str, **kwargs: Any) -> Any: ...


@dataclass(slots=True)
class SalesforceCredentials:
    base_url: str
    client_id: str
    client_secret: str
    username: str
    password: str
    security_token: str


class HttpxTransport:
    def __init__(self) -> None:
        self.client = httpx.Client(timeout=30.0)

    def request(self, method: str, url: str, **kwargs: Any) -> Any:
        response = self.client.request(method, url, **kwargs)
        response.raise_for_status()
        return response


class SalesforceConnector:
    name = "salesforce"

    def __init__(self, credentials: SalesforceCredentials | None, enabled: bool, transport: Transport | None = None) -> None:
        self.credentials = credentials
        self.enabled = enabled and credentials is not None
        self.transport = transport or HttpxTransport()
        self._access_token: str | None = None
        self._instance_url: str | None = None

    def authenticate(self) -> tuple[str, str]:
        if not self.credentials:
            raise ValueError("Salesforce credentials are required.")
        if self._access_token and self._instance_url:
            return self._access_token, self._instance_url
        response = self.transport.request(
            "POST",
            f"{self.credentials.base_url}/services/oauth2/token",
            data={
                "grant_type": "password",
                "client_id": self.credentials.client_id,
                "client_secret": self.credentials.client_secret,
                "username": self.credentials.username,
                "password": f"{self.credentials.password}{self.credentials.security_token}",
            },
        )
        payload = response.json()
        self._access_token = payload["access_token"]
        self._instance_url = payload["instance_url"]
        return self._access_token, self._instance_url

    def _headers(self) -> dict[str, str]:
        token, _ = self.authenticate()
        return {"Authorization": "Bearer " + token, "Content-Type": "application/json"}

    def _api_url(self, path: str) -> str:
        _, instance_url = self.authenticate()
        return f"{instance_url}{path}"

    def fetch(self, *, max_records: int, watermark: str | None) -> ConnectorResult:
        if not self.enabled:
            return ConnectorResult()
        modified_filter = f" AND LastModifiedDate > {watermark}" if watermark else ""
        soql = (
            "SELECT Id, Name, LastModifiedDate, FundOps_External_Id__c "
            f"FROM Account WHERE IsDeleted = false{modified_filter} ORDER BY LastModifiedDate DESC LIMIT {max_records}"
        )
        response = self.transport.request(
            "GET",
            self._api_url("/services/data/v61.0/query"),
            headers=self._headers(),
            params={"q": soql},
        )
        signals = [
            SignalRecord(
                connector=self.name,
                entity_type="account",
                entity_key=row["Name"],
                signal_type="fit",
                score=35.0,
                external_id=row["Id"],
                source_id=row["Id"],
                summary=f"Salesforce account update for {row['Name']}",
                metadata={"last_modified": row["LastModifiedDate"]},
            )
            for row in response.json().get("records", [])
        ]
        return ConnectorResult(signals=signals)

    def get_record(self, sobject: str, record_id: str) -> dict[str, Any]:
        response = self.transport.request("GET", self._api_url(f"/services/data/v61.0/sobjects/{sobject}/{record_id}"), headers=self._headers())
        return response.json()

    def upsert_account(self, account_id: str, scorecard: ScoreCard, brief: IntelligenceBrief) -> None:
        payload = {
            "FundOps_Last_Run_At__c": signal_timestamp(),
            "FundOps_Score__c": scorecard.total_score,
            "FundOps_Priority__c": scorecard.priority,
            "FundOps_Brief__c": brief.summary[:32768],
        }
        self.transport.request(
            "PATCH",
            self._api_url(f"/services/data/v61.0/sobjects/Account/{account_id}"),
            headers=self._headers(),
            json={key: value for key, value in payload.items() if value is not None},
        )

    def upsert_opportunity(self, opportunity: OpportunityRecord, scorecard: ScoreCard, brief: IntelligenceBrief) -> None:
        payload = {
            "Name": opportunity.name,
            "StageName": opportunity.stage_name,
            "Amount": opportunity.amount,
            "CloseDate": opportunity.close_date,
            "FundOps_External_Id__c": opportunity.external_id,
            "FundOps_Last_Run_At__c": signal_timestamp(),
            "FundOps_Score__c": scorecard.total_score,
            "FundOps_Priority__c": scorecard.priority,
            "FundOps_Brief__c": brief.summary[:32768],
            "FundOps_Next_Action__c": "; ".join(action.title for action in brief.recommended_actions)[:32768],
            "FundOps_Inferred_Data__c": brief.inferred_data,
        }
        self.transport.request(
            "PATCH",
            self._api_url(f"/services/data/v61.0/sobjects/Opportunity/FundOps_External_Id__c/{opportunity.external_id}"),
            headers=self._headers(),
            json={key: value for key, value in payload.items() if value is not None},
        )

    def upsert_signal_record(self, account_id: str | None, opportunity_id: str | None, signal: SignalRecord) -> None:
        payload = {
            "FundOps_External_Id__c": signal.signal_id,
            "Account__c": account_id,
            "Opportunity__c": opportunity_id,
            "Signal_Type__c": signal.signal_type,
            "Source_System__c": signal.connector,
            "Source_URL__c": signal.source_url,
            "Score_Contribution__c": signal.score,
            "Explanation__c": signal.summary[:32768],
            "Raw_Hash__c": signal.raw_hash,
        }
        self.transport.request(
            "PATCH",
            self._api_url(f"/services/data/v61.0/sobjects/FundOps_Signal__c/FundOps_External_Id__c/{signal.signal_id}"),
            headers=self._headers(),
            json={key: value for key, value in payload.items() if value is not None},
        )

    def upsert_task(self, what_id: str, action: ActionRecommendation) -> bool:
        subject = f"[FundOps] {action.title}"
        safe_subject = subject.replace("'", "\\'")
        soql = (
            "SELECT Id, Status FROM Task "
            f"WHERE WhatId = '{what_id}' AND Subject = '{safe_subject}' AND Status != 'Completed' LIMIT 1"
        )
        response = self.transport.request(
            "GET",
            self._api_url("/services/data/v61.0/query"),
            headers=self._headers(),
            params={"q": soql},
        )
        records = response.json().get("records", [])
        payload = {"WhatId": what_id, "Subject": subject, "Description": action.details[:32000], "Status": "Not Started"}
        if records:
            self.transport.request(
                "PATCH",
                self._api_url(f"/services/data/v61.0/sobjects/Task/{records[0]['Id']}"),
                headers=self._headers(),
                json=payload,
            )
            return False
        self.transport.request("POST", self._api_url("/services/data/v61.0/sobjects/Task"), headers=self._headers(), json=payload)
        return True


def signal_timestamp() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
