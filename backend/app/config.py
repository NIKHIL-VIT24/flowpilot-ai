from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "FlowPilot AI"
    database_url: str = "sqlite:///./flowpilot.db"
    secret_key: str = "CHANGE-ME-IN-PRODUCTION"
    access_token_minutes: int = 120
    frontend_url: str = "http://127.0.0.1:8000"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.4-mini"
    encryption_key: str | None = None
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://127.0.0.1:8000/api/integrations/google/callback"
    google_ads_api_version: str = "v25"
    google_ads_developer_token: str | None = None
    google_ads_login_customer_id: str | None = None
    google_ads_customer_id: str | None = None
    ga4_property_id: str | None = None
    shopify_client_id: str | None = None
    shopify_client_secret: str | None = None
    shopify_redirect_uri: str = "http://127.0.0.1:8000/api/integrations/shopify/callback"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
