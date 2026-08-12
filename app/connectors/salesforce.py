from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.models import Signal


@dataclass
class InMemorySalesforceStore:
    accounts: dict[str, dict[str, Any]]
    opportunities: dict[str, dict[str, Any]]
    tasks: dict[str, dict[str, Any]]
    signals: dict[str, dict[str, Any]]


class SalesforceConnector:
    """Minimal connector designed for safe upsert behavior in production."""

    def __init__(self, store: InMemorySalesforceStore | None = None) -> None:
        self.store = store or InMemorySalesforceStore(accounts={}, opportunities={}, tasks={}, signals={})

    def query_enabled_accounts(self, limit: int = 5) -> list[dict[str, Any]]:
        enabled = [a for a in self.store.accounts.values() if a.get("FundOps_Enabled__c")]
        return enabled[:limit]

    def upsert_account_fields(self, account_id: str, fields: dict[str, Any]) -> None:
        account = self.store.accounts.setdefault(account_id, {"Id": account_id})
        account.update(fields)

    def upsert_signal(self, signal: Signal) -> None:
        self.store.signals[signal.external_id] = {
            "External_ID__c": signal.external_id,
            "Account__c": signal.account_id,
            "Program__c": signal.program,
            "Signal_Type__c": signal.signal_type,
            "Observed_At__c": signal.observed_at.isoformat(),
            "Observation_Type__c": "Observed",
            "Strength__c": signal.strength,
            "Confidence__c": signal.confidence,
            "Summary__c": signal.summary,
            "Source_Name__c": signal.source_name,
            "Source_URL__c": signal.source_url,
            "Raw_Hash__c": signal.raw_hash,
        }

    def upsert_task(self, account_id: str, action_type: str, why: str, due_date: str, source_url: str) -> None:
        external_id = hashlib.sha256(f"{account_id}|{action_type}".encode("utf-8")).hexdigest()
        self.store.tasks[external_id] = {
            "External_ID__c": external_id,
            "WhatId": account_id,
            "Subject": f"[FundOps] {action_type}",
            "Description": (
                f"Why: {why}\nSupporting evidence: {source_url}\n"
                f"Suggested due date: {due_date}\nSuggested talking points: review mission fit and eligibility"
            ),
            "Status": "Not Started",
            "Priority": "Normal",
            "ActivityDate": due_date,
        }

    def upsert_opportunity(self, external_id: str, payload: dict[str, Any]) -> None:
        record = self.store.opportunities.setdefault(external_id, {"FundOps_External_ID__c": external_id})
        record.update(payload)

    @staticmethod
    def utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
