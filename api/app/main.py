import hmac

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock, SystemClock
from app.config import Settings
from app.db import get_session
from app.gql.schema import graphql_router
from app.sync.espn import ScoreboardClient, get_scoreboard_client
from app.sync.service import sync_league


def create_app(settings: Settings | None = None, clock: Clock | None = None) -> FastAPI:
    app = FastAPI()
    app.state.settings = settings or Settings()
    app.state.clock = clock or SystemClock()

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.post("/internal/sync")
    async def sync(
        request: Request,
        x_sync_secret: str = Header(""),
        session: AsyncSession = Depends(get_session),
        espn: ScoreboardClient = Depends(get_scoreboard_client),
    ):
        expected = request.app.state.settings.sync_secret.encode()
        if not hmac.compare_digest(x_sync_secret.encode(), expected):
            raise HTTPException(401, "bad sync secret")
        counts = {lg: await sync_league(session, espn, lg) for lg in ("nfl", "cfb")}
        await session.commit()  # one transaction for both leagues
        return counts

    app.include_router(graphql_router, prefix="/graphql")
    return app
