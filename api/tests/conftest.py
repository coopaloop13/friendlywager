from datetime import datetime

import httpx
import pytest

from app.main import create_app


class FixedClock:
    def __init__(self, dt: datetime):
        self.dt = dt

    def now(self) -> datetime:
        return self.dt


@pytest.fixture
async def client():
    app = create_app()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c
