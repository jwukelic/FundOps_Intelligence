from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "production"
    run_mode: str = "service"
    host: str = "0.0.0.0"
    port: int = 8080

    gcp_project_id: str = ""
    gcp_region: str = "us-central1"
    bq_dataset: str = "fundops"
    artifact_registry_repository: str = "fundops-intelligence"
    cloud_run_service_name: str = "fundops-intelligence"
    cloud_run_job_name: str = "fundops-intelligence-job"
    cloud_scheduler_job_name: str = "fundops-daily-sync"

    enable_cloud_logging: bool = True
    max_records_per_connector: int = 5
    first_run_cap: int = 5
    retry_attempts: int = 3
    retry_backoff_seconds: float = 2.0

    openai_model: str = "gpt-4.1-mini"
    openai_temperature: float = 0.0
    openai_max_output_tokens: int = 800
    openai_api_key_secret: str = ""
    manual_trigger_token_secret: str = ""

    enable_connector_salesforce: bool = False
    salesforce_base_url_secret: str = ""
    salesforce_client_id_secret: str = ""
    salesforce_client_secret_secret: str = ""
    salesforce_username_secret: str = ""
    salesforce_password_secret: str = ""
    salesforce_security_token_secret: str = ""

    enable_connector_google_drive: bool = False
    google_drive_folder_id: str = ""

    enable_connector_google_sheets: bool = False
    google_sheets_spreadsheet_id: str = ""
    google_sheets_range: str = "Opportunity Intake!A:G"

    enable_connector_mailchimp: bool = False
    mailchimp_api_key_secret: str = ""
    mailchimp_server_prefix_secret: str = ""

    enable_connector_google_ads: bool = False
    google_ads_customer_id: str = ""
    google_ads_developer_token_secret: str = ""
    google_ads_login_customer_id: str = ""

    enable_connector_hootsuite: bool = False
    hootsuite_api_token_secret: str = ""
    hootsuite_csv_path: str = ""

    enable_connector_public_urls: bool = False
    public_urls: str = Field(default="", description="Comma-separated allowlisted URLs provided by users.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
