from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.models import Signal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory store (tests / local dev without Salesforce credentials)
# ---------------------------------------------------------------------------


@dataclass
class InMemorySalesforceStore:
    accounts: dict[str, dict[str, Any]]
    opportunities: dict[str, dict[str, Any]]
    tasks: dict[str, dict[str, Any]]
    signals: dict[str, dict[str, Any]]


# ---------------------------------------------------------------------------
# Connector
# ---------------------------------------------------------------------------

_ACCOUNT_FIELDS = (
    "Id, Name, FundOps_Enabled__c, FundOps_Primary_Program__c, "
    "FundOps_Score__c, FundOps_Priority__c, FundOps_Refresh_Requested__c, "
    "FundOps_IRS_EIN__c"
)

_SIGNAL_FIELDS = (
    "Id, External_ID__c, Account__c, Program__c, Signal_Type__c, "
    "Observed_At__c, Observation_Type__c, Strength__c, Confidence__c, "
    "Summary__c, Source_Name__c, Source_URL__c, Raw_Hash__c"
)


class SalesforceConnector:
    """Minimal connector designed for safe upsert behavior in production.

    When *store* is provided (tests / local dev) all operations run
    against the in-memory store.  In production the constructor calls
    ``_connect()`` which authenticates via the environment variables:

      SALESFORCE_USERNAME, SALESFORCE_AUTH (password+token),
      SALESFORCE_CLIENT_ID, SALESFORCE_CLIENT_SECRET,
      SALESFORCE_INSTANCE_URL (optional override)

    These variables are populated from Secret Manager at deploy time.
    """

    def __init__(self, store: InMemorySalesforceStore | None = None) -> None:
        self._store = store
        self._sf: Any = None  # simple_salesforce.Salesforce instance
        if store is None:
            self._connect()

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        username = os.environ.get("SALESFORCE_USERNAME", "")
        password_and_token = os.environ.get("SALESFORCE_AUTH", "")
        client_id = os.environ.get("SALESFORCE_CLIENT_ID", "")
        client_secret = os.environ.get("SALESFORCE_CLIENT_SECRET", "")
        instance_url = os.environ.get("SALESFORCE_INSTANCE_URL", "")

        if not username or not password_and_token:
            logger.warning("Salesforce credentials not set — using in-memory store.")
            self._store = InMemorySalesforceStore(accounts={}, opportunities={}, tasks={}, signals={})
            return

        try:
            from simple_salesforce import Salesforce  # type: ignore[import-untyped]

            kwargs: dict[str, Any] = {
                "username": username,
                "password": password_and_token,
                "consumer_key": client_id,
                "consumer_secret": client_secret,
            }
            if instance_url:
                kwargs["instance_url"] = instance_url
                kwargs["session_id"] = ""
            self._sf = Salesforce(**kwargs)
            logger.info("Salesforce connected to %s", self._sf.sf_instance)
        except Exception as exc:  # noqa: BLE001
            logger.error("Salesforce connection failed: %s — falling back to in-memory store.", exc)
            self._store = InMemorySalesforceStore(accounts={}, opportunities={}, tasks={}, signals={})

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def query_enabled_accounts(self, limit: int = 5) -> list[dict[str, Any]]:
        if self._store is not None:
            enabled = [a for a in self._store.accounts.values() if a.get("FundOps_Enabled__c")]
            return enabled[:limit]
        soql = (
            f"SELECT {_ACCOUNT_FIELDS} FROM Account "
            f"WHERE FundOps_Enabled__c = true "
            f"ORDER BY FundOps_Score__c DESC NULLS LAST "
            f"LIMIT {limit}"
        )
        result = self._sf.query(soql)
        return [dict(r) for r in result["records"]]

    def query_signals_for_account(self, account_id: str) -> list[dict[str, Any]]:
        if self._store is not None:
            return [s for s in self._store.signals.values() if s.get("Account__c") == account_id]
        safe_id = account_id.replace("'", "")
        soql = (
            f"SELECT {_SIGNAL_FIELDS} FROM FundOps_Signal__c "
            f"WHERE Account__c = '{safe_id}' "
            f"ORDER BY Observed_At__c DESC LIMIT 200"
        )
        result = self._sf.query(soql)
        return [dict(r) for r in result["records"]]

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def upsert_account_fields(self, account_id: str, fields: dict[str, Any]) -> None:
        if self._store is not None:
            account = self._store.accounts.setdefault(account_id, {"Id": account_id})
            account.update(fields)
            return
        self._sf.Account.update(account_id, fields)

    def upsert_signal(self, signal: Signal) -> None:
        payload = {
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
        if self._store is not None:
            self._store.signals[signal.external_id] = payload
            return
        self._sf.FundOps_Signal__c.upsert(f"External_ID__c/{signal.external_id}", payload)

    def upsert_signal_from_dict(self, signal_dict: dict[str, Any]) -> None:
        """Upsert a signal provided as a raw field-name dict (e.g. from IRS 990)."""
        external_id = signal_dict.get("External_ID__c", signal_dict.get("Raw_Hash__c", ""))
        if self._store is not None:
            self._store.signals[external_id] = signal_dict
            return
        self._sf.FundOps_Signal__c.upsert(f"External_ID__c/{external_id}", signal_dict)

    def upsert_task(self, account_id: str, action_type: str, why: str, due_date: str, source_url: str) -> None:
        external_id = hashlib.sha256(f"{account_id}|{action_type}".encode("utf-8")).hexdigest()
        payload = {
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
        if self._store is not None:
            self._store.tasks[external_id] = {"External_ID__c": external_id, **payload}
            return
        # Tasks don't support upsert by external ID natively; query-then-create/update.
        safe_subject = f"[FundOps] {action_type}".replace("'", "''")
        safe_id = account_id.replace("'", "")
        result = self._sf.query(
            f"SELECT Id FROM Task WHERE WhatId = '{safe_id}' "
            f"AND Subject = '{safe_subject}' AND Status != 'Completed' LIMIT 1"
        )
        if result["records"]:
            task_id = result["records"][0]["Id"]
            self._sf.Task.update(task_id, {k: v for k, v in payload.items() if k != "WhatId"})
        else:
            self._sf.Task.create(payload)

    def upsert_opportunity(self, external_id: str, payload: dict[str, Any]) -> None:
        if self._store is not None:
            record = self._store.opportunities.setdefault(external_id, {"FundOps_External_ID__c": external_id})
            record.update(payload)
            return
        self._sf.Opportunity.upsert(
            f"FundOps_External_ID__c/{external_id}",
            {"StageName": "Prospecting", "CloseDate": "2099-12-31", **payload},
        )

    @staticmethod
    def utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # Backwards-compat alias used by tests
    # ------------------------------------------------------------------

    @property
    def store(self) -> InMemorySalesforceStore:
        """Return the in-memory store (only valid in test/dev mode)."""
        if self._store is None:
            raise RuntimeError("store is only available in in-memory mode")
        return self._store

    @store.setter
    def store(self, value: InMemorySalesforceStore) -> None:
        self._store = value
