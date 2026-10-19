import os
from datetime import UTC, datetime

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import Settings
from app.db import get_session
from app.main import create_app

TEST_DATABASE_URL = os.environ["TEST_DATABASE_URL"]
TEST_SECRET = "test-secret-0123456789-0123456789-abcdef"
TABLES = "users, friendships, games, picks, league_state"


class FixedClock:
    def __init__(self, dt: datetime):
        self.dt = dt

    def now(self) -> datetime:
        return self.dt


@pytest.fixture(scope="session")
def migrated():
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(cfg, "head")


@pytest.fixture
async def session(migrated):
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        yield s
        await s.rollback()
        await s.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
        await s.commit()
    await engine.dispose()


@pytest.fixture
def clock():
    return FixedClock(datetime.now(UTC))


@pytest.fixture
async def client(session, clock):
    settings = Settings(
        database_url=TEST_DATABASE_URL,
        session_secret=TEST_SECRET,
        invite_code="test-invite",
        sync_secret="test-sync-secret-0123456789",
        cookie_secure=False,
    )
    app = create_app(settings, clock)

    async def _session():
        yield session

    app.dependency_overrides[get_session] = _session
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c
