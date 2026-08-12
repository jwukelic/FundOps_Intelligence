from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    fundops_env: str = "production"
    fundops_project_id: str = ""
    fundops_bigquery_dataset: str = "fundops"
    fundops_max_accounts: int = 5
    fundops_openai_model: str = "gpt-5-mini"
    fundops_connector_salesforce_enabled: bool = True
    fundops_connector_drive_enabled: bool = True
    fundops_connector_sheets_enabled: bool = True
    fundops_connector_mailchimp_enabled: bool = False
    fundops_connector_google_ads_enabled: bool = False
    fundops_connector_hootsuite_enabled: bool = False
    fundops_intake_sheet_id: str = ""
    fundops_approved_drive_folder_id: str = ""
    fundops_app_secret: str = ""


def get_settings() -> Settings:
    return Settings()
