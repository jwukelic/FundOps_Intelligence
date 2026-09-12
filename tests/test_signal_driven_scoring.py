"""Tests for the signal-driven score_from_account service and the new pipeline behaviors:
- data-driven ScoreComponents
- per-account error isolation
- FundOps_Refresh_Requested__c reset
- Drive document boost
"""
from __future__ import annotations

from app.connectors.google_drive import DriveDocument
from app.models import ScoreComponents
from app.services.score_from_account import score_from_account, _DEFAULTS


# ---------------------------------------------------------------------------
# score_from_account — no signals
# ---------------------------------------------------------------------------

def test_score_from_account_no_signals_uses_defaults():
    account = {"Id": "001", "FundOps_Primary_Program__c": "Believe in Me"}
    result = score_from_account(account, signals=[])
    assert result.mission_and_program_fit == _DEFAULTS["mission_and_program_fit"]
    assert result.funding_capacity == _DEFAULTS["funding_capacity"]
    assert result.relationship_access == _DEFAULTS["relationship_access"]
    assert result.eligibility_gate is True


def test_score_from_account_no_signals_confidence_is_fifty():
    result = score_from_account({}, signals=[])
    assert result.data_confidence == 50.0


# ---------------------------------------------------------------------------
# score_from_account — with typed signals
# ---------------------------------------------------------------------------

def _make_signal(signal_type: str, strength: float, source: str = "FundOps") -> dict:
    return {
        "Signal_Type__c": signal_type,
        "Strength__c": strength,
        "Source_Name__c": source,
        "Account__c": "001",
    }


def test_score_from_account_mission_fit_signal():
    sigs = [_make_signal("MissionFit", 90)]
    result = score_from_account({}, signals=sigs)
    assert result.mission_and_program_fit == 90.0


def test_score_from_account_averages_multiple_same_type():
    sigs = [_make_signal("MissionFit", 60), _make_signal("MissionFit", 80)]
    result = score_from_account({}, signals=sigs)
    assert result.mission_and_program_fit == 70.0


def test_score_from_account_unknown_type_maps_to_engagement():
    sigs = [_make_signal("SomeOtherType", 77)]
    result = score_from_account({}, signals=sigs)
    assert result.engagement_momentum == 77.0


def test_score_from_account_explicit_data_confidence_signal():
    sigs = [_make_signal("DataConfidence", 85)]
    result = score_from_account({}, signals=sigs)
    assert result.data_confidence == 85.0


def test_score_from_account_confidence_scales_with_sources():
    sigs = [
        _make_signal("MissionFit", 70, source="Drive"),
        _make_signal("FundingCapacity", 60, source="Mailchimp"),
        _make_signal("RelationshipAccess", 50, source="GoogleAds"),
    ]
    result = score_from_account({}, signals=sigs)
    # 3 distinct sources → 50 + 3*10 = 80
    assert result.data_confidence == 80.0


# ---------------------------------------------------------------------------
# score_from_account — Drive document boost
# ---------------------------------------------------------------------------

def _make_doc(program: str) -> DriveDocument:
    return DriveDocument(
        file_id="f1",
        file_name="grant.pdf",
        program=program,
        modified_time="2026-01-01",
        source_url="https://drive.google.com/file/f1",
        text_hash="abc",
        extracted_text="",
        approval_status="approved",
    )


def test_drive_doc_boosts_mission_fit_for_matching_program():
    account = {"Id": "001", "FundOps_Primary_Program__c": "Believe in Me"}
    before = score_from_account(account, signals=[])
    after = score_from_account(account, signals=[], drive_docs=[_make_doc("Believe in Me")])
    assert after.mission_and_program_fit > before.mission_and_program_fit


def test_drive_doc_no_boost_for_non_matching_program():
    account = {"Id": "001", "FundOps_Primary_Program__c": "Believe in Me"}
    before = score_from_account(account, signals=[])
    after = score_from_account(account, signals=[], drive_docs=[_make_doc("Some Other Program")])
    assert after.mission_and_program_fit == before.mission_and_program_fit


def test_unapproved_drive_doc_gives_no_boost():
    account = {"Id": "001", "FundOps_Primary_Program__c": "Believe in Me"}
    doc = _make_doc("Believe in Me")
    doc.approval_status = "pending"
    before = score_from_account(account, signals=[])
    after = score_from_account(account, signals=[], drive_docs=[doc])
    assert after.mission_and_program_fit == before.mission_and_program_fit


# ---------------------------------------------------------------------------
# Pipeline — per-account error isolation
# ---------------------------------------------------------------------------

def test_pipeline_error_in_one_account_does_not_abort_others():
    """An account whose signal query raises should be recorded in errors while
    other accounts are still processed."""
    from app.config import Settings
    from app.connectors.google_sheets import GoogleSheetsConnector
    from app.connectors.salesforce import InMemorySalesforceStore, SalesforceConnector
    from app.pipeline import run_pipeline

    store = InMemorySalesforceStore(
        accounts={
            "bad": {"Id": "bad", "FundOps_Enabled__c": True},
            "good": {"Id": "good", "FundOps_Enabled__c": True, "FundOps_Primary_Program__c": "iLevelUP"},
        },
        opportunities={},
        tasks={},
        signals={},
    )

    class BrokenConnector(SalesforceConnector):
        def query_signals_for_account(self, account_id: str):
            if account_id == "bad":
                raise RuntimeError("simulated SF error")
            return super().query_signals_for_account(account_id)

    connector = BrokenConnector(store)
    result = run_pipeline(
        settings=Settings(fundops_max_accounts=10),
        salesforce=connector,
        sheets=GoogleSheetsConnector(),
    )

    # "good" account should have been scored successfully
    assert result.scored_accounts == 1
    # "bad" account error should be captured
    assert len(result.errors) == 1
    assert "bad" in result.errors[0]
    # error is written to SF
    assert store.accounts["bad"].get("FundOps_Last_Error__c") == "simulated SF error"


# ---------------------------------------------------------------------------
# Pipeline — FundOps_Refresh_Requested__c is reset after processing
# ---------------------------------------------------------------------------

def test_pipeline_clears_refresh_requested_flag():
    from app.config import Settings
    from app.connectors.google_sheets import GoogleSheetsConnector
    from app.connectors.salesforce import InMemorySalesforceStore, SalesforceConnector
    from app.pipeline import run_pipeline

    store = InMemorySalesforceStore(
        accounts={
            "001": {
                "Id": "001",
                "FundOps_Enabled__c": True,
                "FundOps_Primary_Program__c": "Cougs 4 Kids",
                "FundOps_Refresh_Requested__c": True,
            }
        },
        opportunities={},
        tasks={},
        signals={},
    )
    run_pipeline(
        settings=Settings(fundops_max_accounts=5),
        salesforce=SalesforceConnector(store),
        sheets=GoogleSheetsConnector(),
    )
    assert store.accounts["001"].get("FundOps_Refresh_Requested__c") is False


# ---------------------------------------------------------------------------
# Pipeline — Drive docs feed into score via pipeline
# ---------------------------------------------------------------------------

def test_pipeline_with_drive_docs_changes_score():
    from app.config import Settings
    from app.connectors.google_drive import GoogleDriveConnector
    from app.connectors.google_sheets import GoogleSheetsConnector
    from app.connectors.salesforce import InMemorySalesforceStore, SalesforceConnector
    from app.pipeline import run_pipeline

    class StaticDrive(GoogleDriveConnector):
        def list_approved_documents(self):
            return [_make_doc("Believe in Me")]

    store_no_docs = InMemorySalesforceStore(
        accounts={"001": {"Id": "001", "FundOps_Enabled__c": True, "FundOps_Primary_Program__c": "Believe in Me"}},
        opportunities={},
        tasks={},
        signals={},
    )
    store_with_docs = InMemorySalesforceStore(
        accounts={"001": {"Id": "001", "FundOps_Enabled__c": True, "FundOps_Primary_Program__c": "Believe in Me"}},
        opportunities={},
        tasks={},
        signals={},
    )

    run_pipeline(Settings(fundops_max_accounts=5), SalesforceConnector(store_no_docs), GoogleSheetsConnector())
    run_pipeline(Settings(fundops_max_accounts=5), SalesforceConnector(store_with_docs), GoogleSheetsConnector(), drive=StaticDrive())

    score_no_docs = store_no_docs.accounts["001"]["FundOps_Score__c"]
    score_with_docs = store_with_docs.accounts["001"]["FundOps_Score__c"]
    # Drive boost should nudge the score upward
    assert score_with_docs >= score_no_docs


# ---------------------------------------------------------------------------
# Pipeline — signal-driven scores vary by account
# ---------------------------------------------------------------------------

def test_pipeline_signal_driven_scores_differ_by_signal_data():
    """Two accounts with different pre-seeded signals should receive different scores."""
    from datetime import datetime, timezone
    from app.config import Settings
    from app.connectors.google_sheets import GoogleSheetsConnector
    from app.connectors.salesforce import InMemorySalesforceStore, SalesforceConnector
    from app.pipeline import run_pipeline

    now = datetime.now(timezone.utc)
    store = InMemorySalesforceStore(
        accounts={
            "high": {"Id": "high", "FundOps_Enabled__c": True, "FundOps_Primary_Program__c": "iLevelUP"},
            "low": {"Id": "low", "FundOps_Enabled__c": True, "FundOps_Primary_Program__c": "iLevelUP"},
        },
        opportunities={},
        tasks={},
        signals={
            "high-mf": {
                "External_ID__c": "high-mf",
                "Account__c": "high",
                "Signal_Type__c": "MissionFit",
                "Strength__c": 95,
                "Source_Name__c": "Drive",
                "Confidence__c": 80,
            },
            "high-fc": {
                "External_ID__c": "high-fc",
                "Account__c": "high",
                "Signal_Type__c": "FundingCapacity",
                "Strength__c": 90,
                "Source_Name__c": "IRS990",
                "Confidence__c": 80,
            },
            "low-mf": {
                "External_ID__c": "low-mf",
                "Account__c": "low",
                "Signal_Type__c": "MissionFit",
                "Strength__c": 20,
                "Source_Name__c": "Drive",
                "Confidence__c": 40,
            },
        },
    )

    run_pipeline(Settings(fundops_max_accounts=10), SalesforceConnector(store), GoogleSheetsConnector())

    assert store.accounts["high"]["FundOps_Score__c"] > store.accounts["low"]["FundOps_Score__c"]
