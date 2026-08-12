from __future__ import annotations

from typing import Any

import httpx

from app.models import ConnectorResult, SignalRecord

# Google Ads REST API base URL (uses REST query interface, no gRPC dependency)
_GAQL_URL = "https://googleads.googleapis.com/v17/customers/{customer_id}/googleAds:searchStream"

# Lightweight GAQL that retrieves campaign performance we can turn into signals.
# Filtered to ENABLED campaigns only; date range driven by watermark when available.
_GAQL_TEMPLATE = """
SELECT
  customer.descriptive_name,
  campaign.id,
  campaign.name,
  campaign.status,
  metrics.impressions,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions,
  segments.date
FROM campaign
WHERE campaign.status = 'ENABLED'
  AND segments.date DURING {date_range}
ORDER BY segments.date DESC
LIMIT {limit}
"""


def _campaign_score(impressions: int, clicks: int, conversions: float) -> float:
    """Heuristic score in [0, 100] based on click-through and conversion signal."""
    if impressions == 0:
        return 0.0
    ctr = clicks / impressions
    # weight CTR heavily; each conversion adds a small bonus capped at 30
    raw = min(ctr * 200, 70.0) + min(conversions * 3, 30.0)
    return round(min(raw, 100.0), 2)


class GoogleAdsConnector:
    """Read-only Google Ads connector using the REST/GAQL search stream API.

    Authentication uses a pre-obtained OAuth2 access token passed in via
    *oauth_token*.  The login customer ID (*login_customer_id*) is required
    when accessing a sub-account under a manager account (MCC).
    """

    name = "google_ads"

    def __init__(
        self,
        customer_id: str,
        developer_token: str,
        enabled: bool,
        oauth_token: str = "",
        login_customer_id: str = "",
        transport: Any = None,
    ) -> None:
        self.customer_id = customer_id.replace("-", "")  # normalise dashes
        self.developer_token = developer_token
        self.oauth_token = oauth_token
        self.login_customer_id = login_customer_id.replace("-", "")
        self.enabled = enabled and bool(customer_id and developer_token and oauth_token)
        self._transport = transport  # injectable for testing

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": "Bearer " + self.oauth_token,
            "developer-token": self.developer_token,
            "Content-Type": "application/json",
        }
        if self.login_customer_id:
            headers["login-customer-id"] = self.login_customer_id
        return headers

    def fetch(self, *, max_records: int, watermark: str | None) -> ConnectorResult:
        if not self.enabled:
            return ConnectorResult()

        # Derive date range: use watermark date when available, else last 30 days
        if watermark:
            # watermark is an ISO timestamp; take just the date part
            since = watermark[:10]
            date_range = f"'{since}' AND '{since}'"  # single-day catch-up per run
        else:
            date_range = "LAST_30_DAYS"

        gaql = _GAQL_TEMPLATE.format(date_range=date_range, limit=max_records).strip()
        url = _GAQL_URL.format(customer_id=self.customer_id)

        if self._transport is not None:
            response_obj = self._transport.request("POST", url, headers=self._headers(), json={"query": gaql})
            batches = response_obj.json() if callable(getattr(response_obj, "json", None)) else response_obj
        else:
            resp = httpx.post(url, headers=self._headers(), json={"query": gaql}, timeout=30.0)
            resp.raise_for_status()
            batches = resp.json()

        # searchStream returns a list of batch result objects
        if isinstance(batches, dict):
            batches = [batches]

        signals: list[SignalRecord] = []
        seen_campaign_dates: set[str] = set()
        for batch in batches:
            for row in batch.get("results", []):
                campaign = row.get("campaign", {})
                metrics = row.get("metrics", {})
                segment = row.get("segments", {})
                customer = row.get("customer", {})

                campaign_id = campaign.get("id", "")
                campaign_name = campaign.get("name", "")
                seg_date = segment.get("date", "")
                dedup_key = f"{campaign_id}:{seg_date}"
                if dedup_key in seen_campaign_dates:
                    continue
                seen_campaign_dates.add(dedup_key)

                impressions = int(metrics.get("impressions", 0))
                clicks = int(metrics.get("clicks", 0))
                conversions = float(metrics.get("conversions", 0.0))
                cost_micros = int(metrics.get("costMicros", 0))

                score = _campaign_score(impressions, clicks, conversions)
                account_name = customer.get("descriptiveName", "general")

                signals.append(
                    SignalRecord(
                        connector=self.name,
                        entity_type="account",
                        entity_key=account_name,
                        signal_type="engagement",
                        score=score,
                        external_id=f"gads:{campaign_id}:{seg_date}",
                        source_id=str(campaign_id),
                        summary=(
                            f"Google Ads campaign '{campaign_name}' on {seg_date}: "
                            f"{impressions:,} impressions, {clicks:,} clicks, "
                            f"{conversions} conversions"
                        ),
                        metadata={
                            "campaign_id": campaign_id,
                            "campaign_name": campaign_name,
                            "impressions": impressions,
                            "clicks": clicks,
                            "conversions": conversions,
                            "cost_micros": cost_micros,
                            "date": seg_date,
                        },
                    )
                )

        return ConnectorResult(signals=signals[:max_records])


