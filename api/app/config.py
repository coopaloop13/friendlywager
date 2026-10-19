from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    session_secret: str
    invite_code: str
    sync_secret: str
    cookie_secure: bool = False
