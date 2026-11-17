from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    session_secret: str = Field(min_length=32)
    sync_secret: str = Field(min_length=16)
    cookie_secure: bool = False
    # Cloudflare Email Service; without both, sign-in codes are only written to the log (local development)
    email_api_token: str | None = None
    cloudflare_account_id: str | None = None
    email_from: str = "signin@pickem.cc"
    email_from_name: str = "Pick'ems"
    # Firebase service account key (the whole JSON file as one string); without it reminders are only logged
    fcm_service_account: str | None = None
