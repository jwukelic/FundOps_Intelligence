from __future__ import annotations

from google.auth import default

from app.config import Settings
from app.connectors.google_ads import GoogleAdsConnector
from app.connectors.google_drive import GoogleDriveConnector
from app.connectors.google_sheets import GoogleSheetsConnector
from app.connectors.hootsuite import HootsuiteConnector
from app.connectors.mailchimp import MailchimpConnector
from app.connectors.openai_client import OpenAIJSONModel
from app.connectors.public_urls import PublicURLConnector
from app.connectors.salesforce import SalesforceConnector, SalesforceCredentials
from app.secrets import GoogleSecretManagerProvider
from app.services.intelligence import FallbackAIModel, IntelligenceService
from app.storage import BigQueryWarehouse


def build_runtime(settings: Settings):
    secret_provider = GoogleSecretManagerProvider(settings.gcp_project_id)
    credentials = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])[0] if settings.gcp_project_id else None
    warehouse = BigQueryWarehouse(settings.gcp_project_id, settings.bq_dataset)
    salesforce_credentials = None
    if settings.enable_connector_salesforce:
        password_secret_name = settings.salesforce_password_secret
        salesforce_credentials = SalesforceCredentials(
            base_url=secret_provider.get(settings.salesforce_base_url_secret),
            client_id=secret_provider.get(settings.salesforce_client_id_secret),
            client_secret=secret_provider.get(settings.salesforce_client_secret_secret),
            username=secret_provider.get(settings.salesforce_username_secret),
            **{"password": secret_provider.get(password_secret_name)},
            security_token=secret_provider.get(settings.salesforce_security_token_secret),
        )
    connectors = [
        SalesforceConnector(salesforce_credentials, settings.enable_connector_salesforce),
        GoogleDriveConnector(settings.google_drive_folder_id, settings.enable_connector_google_drive, credentials=credentials),
        GoogleSheetsConnector(
            settings.google_sheets_spreadsheet_id,
            settings.google_sheets_range,
            settings.enable_connector_google_sheets,
            credentials=credentials,
        ),
        MailchimpConnector(
            secret_provider.get(settings.mailchimp_api_key_secret),
            secret_provider.get(settings.mailchimp_server_prefix_secret),
            settings.enable_connector_mailchimp,
        ),
        GoogleAdsConnector(
            settings.google_ads_customer_id,
            secret_provider.get(settings.google_ads_developer_token_secret),
            settings.enable_connector_google_ads,
            oauth_token=secret_provider.get(settings.google_ads_oauth_token_secret),
            login_customer_id=settings.google_ads_login_customer_id,
        ),
        HootsuiteConnector(
            secret_provider.get(settings.hootsuite_api_token_secret),
            settings.hootsuite_csv_path,
            settings.enable_connector_hootsuite,
        ),
        PublicURLConnector(
            [url.strip() for url in settings.public_urls.split(",") if url.strip()],
            settings.enable_connector_public_urls,
        ),
    ]
    openai_key = secret_provider.get(settings.openai_api_key_secret)
    model = (
        OpenAIJSONModel(openai_key, settings.openai_model, settings.openai_temperature, settings.openai_max_output_tokens)
        if openai_key
        else FallbackAIModel()
    )
    intelligence = IntelligenceService(warehouse=warehouse, model=model)
    salesforce_writer = connectors[0] if isinstance(connectors[0], SalesforceConnector) and connectors[0].enabled else None
    return warehouse, connectors, intelligence, salesforce_writer
