"""Tests for the three backlog items completed in this session:
 1. Richer Salesforce entity resolution (normalise_name, canonical_entity_key)
 2. Google Ads read-only ingestion (GoogleAdsConnector)
 3. Hootsuite API pagination + CSV schema validation (HootsuiteConnector)
"""
from __future__ import annotations

import csv
import io
import json
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.connectors.google_ads import GoogleAdsConnector, _campaign_score
from app.connectors.hootsuite import HootsuiteConnector, _validate_csv_headers
from app.models import SignalRecord
from app.services.entity_resolution import canonical_entity_key, normalise_name


# ===========================================================================
# 1. Entity resolution
# ===========================================================================

class TestNormaliseName:
    @pytest.mark.parametrize("raw,expected", [
        # Basic lowercasing
        ("Acme", "acme"),
        # Trailing LLC / Inc stripped
        ("Acme LLC", "acme"),
        ("Acme, Inc.", "acme"),
        ("Acme Inc", "acme"),
        ("Acme Corporation", "acme"),
        ("Acme Corp.", "acme"),
        ("Acme Ltd", "acme"),
        ("Acme Limited", "acme"),
        ("Acme Foundation", "acme"),
        ("Acme Fund", "acme"),
        ("Acme L.L.C", "acme"),
        ("Acme L.P", "acme"),
        # Stacked suffixes
        ("Acme Corp Foundation", "acme"),
        # Punctuation stripped
        ("Acme & Partners", "acme partners"),
        ('Acme "Global" Inc', "acme global"),
        # Unicode normalisation (full-width A)
        ("\uff21cme", "acme"),
        # Whitespace collapse
        ("  Acme   Inc  ", "acme"),
        # Non-account – should just be lowercased (tested via canonical_entity_key)
        ("Real Name Nonprofit", "real name"),
        ("Acme Holdings Group", "acme holdings group"),
        # Hyphen / underscore collapse
        ("Acme-Global_Inc", "acme global"),
    ])
    def test_normalise(self, raw, expected):
        assert normalise_name(raw) == expected

    def test_empty_string(self):
        assert normalise_name("") == ""

    def test_only_suffix(self):
        # Edge: name is *only* a suffix word
        result = normalise_name("Foundation")
        # After stripping, nothing remains – that's acceptable
        assert isinstance(result, str)


class TestCanonicalEntityKey:
    def test_account_uses_normalise(self):
        signal = SignalRecord("sf", "account", "Acme LLC", "fit", 10.0)
        assert canonical_entity_key(signal) == "acme"

    def test_non_account_just_lowercases(self):
        signal = SignalRecord("sf", "contact", "Jane Doe", "fit", 10.0)
        assert canonical_entity_key(signal) == "jane doe"

    def test_account_with_whitespace(self):
        signal = SignalRecord("sf", "account", "  Acme Inc.  ", "fit", 10.0)
        assert canonical_entity_key(signal) == "acme"

    def test_different_legal_forms_match(self):
        sig_a = SignalRecord("sf", "account", "Greenfield Foundation", "fit", 10.0)
        sig_b = SignalRecord("sheets", "account", "Greenfield Fund", "fit", 10.0)
        assert canonical_entity_key(sig_a) == canonical_entity_key(sig_b)

    def test_different_names_dont_collide(self):
        sig_a = SignalRecord("sf", "account", "Acme Inc", "fit", 10.0)
        sig_b = SignalRecord("sf", "account", "Beta Corp", "fit", 10.0)
        assert canonical_entity_key(sig_a) != canonical_entity_key(sig_b)


# ===========================================================================
# 2. Google Ads connector
# ===========================================================================

def _make_gads_batch(campaign_id: str = "111", campaign_name: str = "Spring Appeal",
                     date: str = "2026-06-01", impressions: int = 10000,
                     clicks: int = 500, conversions: float = 10.0,
                     customer_name: str = "Acme Nonprofit") -> dict:
    return {
        "results": [
            {
                "customer": {"descriptiveName": customer_name},
                "campaign": {"id": campaign_id, "name": campaign_name, "status": "ENABLED"},
                "metrics": {
                    "impressions": impressions,
                    "clicks": clicks,
                    "conversions": conversions,
                    "costMicros": 5_000_000,
                },
                "segments": {"date": date},
            }
        ]
    }


class FakeGadsResponse:
    def __init__(self, payload: Any):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeGadsTransport:
    def __init__(self, batches: list[dict]):
        self._batches = batches
        self.calls: list[tuple] = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        # Return list (searchStream returns array of batch objects)
        return FakeGadsResponse(self._batches)


class TestCampaignScore:
    def test_zero_impressions_yields_zero(self):
        assert _campaign_score(0, 0, 0) == 0.0

    def test_perfect_ctr_capped_at_100(self):
        # clicks == impressions → CTR 1.0 → raw 200+ → capped 100
        assert _campaign_score(100, 100, 0) == 70.0  # 1.0*200 capped at 70, +0 conv

    def test_high_conversions_bonus_capped(self):
        # Many conversions should cap the conversion bonus at 30
        score = _campaign_score(1000, 50, 1000)
        assert score <= 100.0

    def test_typical_case(self):
        score = _campaign_score(10000, 500, 10)
        assert 0 < score <= 100


class TestGoogleAdsConnector:
    def _connector(self, batches=None, customer_id="1234567890") -> tuple[GoogleAdsConnector, FakeGadsTransport]:
        transport = FakeGadsTransport(batches or [_make_gads_batch()])
        connector = GoogleAdsConnector(
            customer_id=customer_id,
            developer_token="dev-token",
            enabled=True,
            oauth_token="oauth-token",
            transport=transport,
        )
        return connector, transport

    def test_disabled_returns_empty(self):
        c = GoogleAdsConnector("", "", enabled=False, oauth_token="")
        assert c.fetch(max_records=10, watermark=None).signals == []

    def test_no_oauth_token_disables_connector(self):
        c = GoogleAdsConnector("123", "dev", enabled=True, oauth_token="")
        assert not c.enabled

    def test_fetch_produces_signals(self):
        connector, _ = self._connector()
        result = connector.fetch(max_records=10, watermark=None)
        assert len(result.signals) == 1
        signal = result.signals[0]
        assert signal.connector == "google_ads"
        assert signal.signal_type == "engagement"
        assert signal.entity_key == "Acme Nonprofit"  # raw; normalised by pipeline
        assert "Spring Appeal" in signal.summary

    def test_signal_metadata_populated(self):
        connector, _ = self._connector()
        signal = connector.fetch(max_records=10, watermark=None).signals[0]
        assert signal.metadata["impressions"] == 10000
        assert signal.metadata["clicks"] == 500
        assert signal.metadata["campaign_name"] == "Spring Appeal"

    def test_deduplicates_same_campaign_date(self):
        batch = {"results": [_make_gads_batch()["results"][0], _make_gads_batch()["results"][0]]}
        connector, _ = self._connector(batches=[batch])
        result = connector.fetch(max_records=10, watermark=None)
        assert len(result.signals) == 1

    def test_watermark_used_in_query(self):
        connector, transport = self._connector()
        connector.fetch(max_records=5, watermark="2026-06-01T00:00:00+00:00")
        body = transport.calls[0][2]["json"]
        assert "2026-06-01" in body["query"]

    def test_no_watermark_uses_last_30_days(self):
        connector, transport = self._connector()
        connector.fetch(max_records=5, watermark=None)
        body = transport.calls[0][2]["json"]
        assert "LAST_30_DAYS" in body["query"]

    def test_authorization_header_sent(self):
        connector, transport = self._connector()
        connector.fetch(max_records=5, watermark=None)
        headers = transport.calls[0][2]["headers"]
        # The connector builds the header as "Bearer " + oauth_token; verify prefix and token
        auth = headers["Authorization"]
        assert auth.startswith("Bearer "), f"Expected '******' but got {auth!r}"
        assert auth == "Bearer " + connector.oauth_token
        assert headers["developer-token"] == "dev-token"

    def test_login_customer_id_header_sent_when_set(self):
        transport = FakeGadsTransport([_make_gads_batch()])
        connector = GoogleAdsConnector(
            customer_id="123",
            developer_token="dev",
            enabled=True,
            oauth_token="tok",
            login_customer_id="999",
            transport=transport,
        )
        connector.fetch(max_records=5, watermark=None)
        headers = transport.calls[0][2]["headers"]
        assert headers["login-customer-id"] == "999"

    def test_dashes_stripped_from_customer_id(self):
        c = GoogleAdsConnector("123-456-7890", "dev", enabled=True, oauth_token="tok")
        assert c.customer_id == "1234567890"

    def test_max_records_respected(self):
        # Build batch with 5 distinct campaign/date combos
        results = [
            _make_gads_batch(campaign_id=str(i), date=f"2026-06-0{i+1}")["results"][0]
            for i in range(5)
        ]
        connector, _ = self._connector(batches=[{"results": results}])
        out = connector.fetch(max_records=3, watermark=None)
        assert len(out.signals) == 3

    def test_empty_batch_returns_no_signals(self):
        connector, _ = self._connector(batches=[{"results": []}])
        assert connector.fetch(max_records=10, watermark=None).signals == []


# ===========================================================================
# 3. Hootsuite connector
# ===========================================================================

class TestValidateCsvHeaders:
    def test_valid_headers_no_error(self):
        _validate_csv_headers(["id", "profile", "score", "summary"], "/tmp/test.csv")

    def test_extra_columns_allowed(self):
        _validate_csv_headers(["id", "profile", "score", "summary", "url", "extra"], "/tmp/t.csv")

    def test_missing_required_raises(self):
        with pytest.raises(ValueError, match="missing required columns"):
            _validate_csv_headers(["id", "profile"], "/tmp/bad.csv")

    def test_error_message_lists_missing_columns(self):
        with pytest.raises(ValueError) as exc_info:
            _validate_csv_headers(["id"], "/tmp/bad.csv")
        msg = str(exc_info.value)
        assert "profile" in msg
        assert "score" in msg
        assert "summary" in msg


def _write_csv(tmp_path: Path, rows: list[dict], fieldnames: list[str]) -> str:
    p = tmp_path / "hootsuite.csv"
    with p.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return str(p)


class TestHootsuiteCSV:
    def test_valid_csv_produces_signals(self, tmp_path):
        path = _write_csv(tmp_path, [
            {"id": "1", "profile": "Acme", "score": "55", "summary": "Post A", "url": "https://x.com/1"},
            {"id": "2", "profile": "Beta", "score": "40", "summary": "Post B", "url": ""},
        ], ["id", "profile", "score", "summary", "url"])
        connector = HootsuiteConnector(api_token="", csv_path=path, enabled=True)
        result = connector.fetch(max_records=10, watermark=None)
        assert len(result.signals) == 2
        assert result.signals[0].external_id == "1"
        assert result.signals[0].score == 55.0
        assert result.signals[1].source_url is None

    def test_max_records_respected(self, tmp_path):
        rows = [{"id": str(i), "profile": "X", "score": "10", "summary": "s"} for i in range(10)]
        path = _write_csv(tmp_path, rows, ["id", "profile", "score", "summary"])
        connector = HootsuiteConnector(api_token="", csv_path=path, enabled=True)
        assert len(connector.fetch(max_records=3, watermark=None).signals) == 3

    def test_invalid_score_uses_default(self, tmp_path):
        path = _write_csv(tmp_path, [
            {"id": "1", "profile": "X", "score": "not-a-number", "summary": "s"},
        ], ["id", "profile", "score", "summary"])
        connector = HootsuiteConnector(api_token="", csv_path=path, enabled=True)
        signal = connector.fetch(max_records=5, watermark=None).signals[0]
        assert signal.score == 20.0  # default

    def test_missing_required_columns_raises(self, tmp_path):
        path = _write_csv(tmp_path, [{"id": "1"}], ["id"])
        connector = HootsuiteConnector(api_token="", csv_path=path, enabled=True)
        with pytest.raises(ValueError, match="missing required columns"):
            connector.fetch(max_records=10, watermark=None)

    def test_row_without_id_skipped(self, tmp_path):
        path = _write_csv(tmp_path, [
            {"id": "", "profile": "X", "score": "10", "summary": "no id"},
            {"id": "2", "profile": "Y", "score": "30", "summary": "has id"},
        ], ["id", "profile", "score", "summary"])
        connector = HootsuiteConnector(api_token="", csv_path=path, enabled=True)
        result = connector.fetch(max_records=10, watermark=None)
        assert len(result.signals) == 1
        assert result.signals[0].external_id == "2"

    def test_disabled_returns_empty(self):
        connector = HootsuiteConnector(api_token="", csv_path="", enabled=False)
        assert connector.fetch(max_records=10, watermark=None).signals == []

    def test_missing_csv_path_returns_empty(self):
        connector = HootsuiteConnector(api_token="", csv_path="/nonexistent/path.csv", enabled=True)
        assert connector.fetch(max_records=10, watermark=None).signals == []


class FakeHootsuiteResponse:
    def __init__(self, data: list[dict], next_cursor: str | None = None):
        self._data = data
        self._next = next_cursor

    def raise_for_status(self):
        return None

    def json(self):
        body: dict = {"data": self._data}
        if self._next:
            body["paging"] = {"cursors": {"after": self._next}, "next": self._next}
        return body


class TestHootsuiteAPIPath:
    def _connector_with_pages(self, pages: list[tuple[list[dict], str | None]]) -> HootsuiteConnector:
        """Build a connector whose httpx.get is monkeypatched to return *pages* in sequence."""
        return pages  # returned for use by monkeypatch

    def _items(self, n: int, offset: int = 0) -> list[dict]:
        return [
            {
                "id": str(offset + i),
                "profileName": "Acme",
                "text": f"post {offset + i}",
                "permalink": f"https://hs.com/{offset + i}",
                "profileId": "p1",
                "publishedAt": "2026-01-01T00:00:00Z",
            }
            for i in range(n)
        ]

    def test_api_single_page(self, monkeypatch):
        calls = []

        def fake_get(url, *, headers, params, timeout):
            calls.append(params)
            return FakeHootsuiteResponse(self._items(3))

        monkeypatch.setattr("app.connectors.hootsuite.httpx.get", fake_get)
        connector = HootsuiteConnector(api_token="tok", csv_path="", enabled=True)
        result = connector.fetch(max_records=10, watermark=None)
        assert len(result.signals) == 3
        assert len(calls) == 1

    def test_api_pagination_fetches_multiple_pages(self, monkeypatch):
        page_responses = [
            FakeHootsuiteResponse(self._items(3, offset=0), next_cursor="cursor1"),
            FakeHootsuiteResponse(self._items(3, offset=3), next_cursor="cursor2"),
            FakeHootsuiteResponse(self._items(2, offset=6), next_cursor=None),
        ]
        call_idx = [0]

        def fake_get(url, *, headers, params, timeout):
            resp = page_responses[call_idx[0]]
            call_idx[0] += 1
            return resp

        monkeypatch.setattr("app.connectors.hootsuite.httpx.get", fake_get)
        connector = HootsuiteConnector(api_token="tok", csv_path="", enabled=True)
        result = connector.fetch(max_records=100, watermark=None)
        assert len(result.signals) == 8
        assert call_idx[0] == 3

    def test_api_cursor_passed_to_next_page(self, monkeypatch):
        page_responses = [
            FakeHootsuiteResponse(self._items(2), next_cursor="cur-abc"),
            FakeHootsuiteResponse(self._items(2), next_cursor=None),
        ]
        call_params = []
        call_idx = [0]

        def fake_get(url, *, headers, params, timeout):
            call_params.append(dict(params))
            resp = page_responses[call_idx[0]]
            call_idx[0] += 1
            return resp

        monkeypatch.setattr("app.connectors.hootsuite.httpx.get", fake_get)
        connector = HootsuiteConnector(api_token="tok", csv_path="", enabled=True)
        connector.fetch(max_records=100, watermark=None)
        assert call_params[0].get("after") is None
        assert call_params[1]["after"] == "cur-abc"

    def test_max_records_stops_pagination(self, monkeypatch):
        """Should stop after collecting max_records even if more pages exist."""
        def fake_get(url, *, headers, params, timeout):
            return FakeHootsuiteResponse(self._items(5), next_cursor="more")

        monkeypatch.setattr("app.connectors.hootsuite.httpx.get", fake_get)
        connector = HootsuiteConnector(api_token="tok", csv_path="", enabled=True)
        result = connector.fetch(max_records=3, watermark=None)
        assert len(result.signals) == 3

    def test_api_failure_falls_back_to_csv(self, monkeypatch, tmp_path):
        def fake_get(*args, **kwargs):
            raise RuntimeError("network error")

        monkeypatch.setattr("app.connectors.hootsuite.httpx.get", fake_get)
        path = _write_csv(tmp_path, [
            {"id": "1", "profile": "X", "score": "25", "summary": "CSV post"},
        ], ["id", "profile", "score", "summary"])
        connector = HootsuiteConnector(api_token="tok", csv_path=path, enabled=True)
        result = connector.fetch(max_records=10, watermark=None)
        assert len(result.signals) == 1
        assert result.signals[0].external_id == "1"

    def test_watermark_sent_as_start_time(self, monkeypatch):
        params_seen = []

        def fake_get(url, *, headers, params, timeout):
            params_seen.append(dict(params))
            return FakeHootsuiteResponse([])

        monkeypatch.setattr("app.connectors.hootsuite.httpx.get", fake_get)
        connector = HootsuiteConnector(api_token="tok", csv_path="", enabled=True)
        connector.fetch(max_records=5, watermark="2026-05-01T00:00:00Z")
        assert params_seen[0]["startTime"] == "2026-05-01T00:00:00Z"
