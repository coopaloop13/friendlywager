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
    email_from: str = "signin@sportspicks.cc"
    email_from_name: str = "Friendly Wager"
