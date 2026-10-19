from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    session_secret: str = Field(min_length=32)
    invite_code: str
    sync_secret: str = Field(min_length=16)
    cookie_secure: bool = False
