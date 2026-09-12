class MailchimpConnector:
    def __init__(self, api_key: str, server_prefix: str) -> None:
        if not api_key or not server_prefix:
            raise ValueError("Mailchimp credentials are required")
        self.api_key = api_key
        self.server_prefix = server_prefix

    @staticmethod
    def normalize_campaign(campaign: dict) -> dict:
        return {
            "campaign": campaign.get("id"),
            "send_date": campaign.get("send_time"),
            "subject": campaign.get("settings", {}).get("subject_line"),
            "opens": campaign.get("report_summary", {}).get("opens", 0),
            "clicks": campaign.get("report_summary", {}).get("clicks", 0),
            "unsubscribes": campaign.get("report_summary", {}).get("unsubscribed", 0),
            "tags": campaign.get("tags", []),
            "url": campaign.get("archive_url"),
        }
