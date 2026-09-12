class HootsuiteConnector:
    def __init__(self, token: str) -> None:
        if not token:
            raise ValueError("Hootsuite token is required")
        self.token = token

    @staticmethod
    def normalize_metric(metric: dict) -> dict:
        return {
            "network": metric.get("network"),
            "account": metric.get("account"),
            "post": metric.get("post"),
            "published_date": metric.get("published_date"),
            "campaign": metric.get("campaign"),
            "impressions": int(metric.get("impressions", 0)),
            "engagement": int(metric.get("engagement", 0)),
            "clicks": int(metric.get("clicks", 0)),
            "url": metric.get("url"),
        }
