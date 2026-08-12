class GoogleAdsConnector:
    def __init__(self, developer_token: str, customer_id: str) -> None:
        if not developer_token or not customer_id:
            raise ValueError("Google Ads credentials are required")
        self.developer_token = developer_token
        self.customer_id = customer_id

    @staticmethod
    def normalize_row(row: dict) -> dict:
        return {
            "campaign": row.get("campaign"),
            "ad_group": row.get("ad_group"),
            "date": row.get("date"),
            "spend": float(row.get("spend", 0)),
            "impressions": int(row.get("impressions", 0)),
            "clicks": int(row.get("clicks", 0)),
            "conversions": float(row.get("conversions", 0)),
            "conversion_value": float(row.get("conversion_value", 0)),
        }
