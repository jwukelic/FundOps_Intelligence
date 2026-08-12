import pytest

from app.connectors.google_ads import GoogleAdsConnector
from app.connectors.hootsuite import HootsuiteConnector
from app.connectors.mailchimp import MailchimpConnector


def test_mailchimp_auth_and_normalization():
    c = MailchimpConnector(api_key="k", server_prefix="us1")
    row = c.normalize_campaign({"id": "abc", "settings": {"subject_line": "Hello"}, "report_summary": {"opens": 1, "clicks": 2}})
    assert row["campaign"] == "abc"
    assert row["opens"] == 1


def test_google_ads_auth_and_normalization():
    c = GoogleAdsConnector(developer_token="t", customer_id="1")
    row = c.normalize_row({"campaign": "C", "spend": "10.5", "impressions": "3", "clicks": "1"})
    assert row["spend"] == 10.5
    assert row["impressions"] == 3


def test_hootsuite_auth_and_normalization():
    c = HootsuiteConnector(token="tok")
    row = c.normalize_metric({"network": "LinkedIn", "impressions": "10"})
    assert row["network"] == "LinkedIn"
    assert row["impressions"] == 10


def test_auth_failures():
    with pytest.raises(ValueError):
        MailchimpConnector(api_key="", server_prefix="us1")
    with pytest.raises(ValueError):
        GoogleAdsConnector(developer_token="", customer_id="1")
    with pytest.raises(ValueError):
        HootsuiteConnector(token="")
