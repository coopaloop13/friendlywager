import hmac
import logging
from datetime import timedelta

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock, SystemClock
from app.config import Settings
from app.db import get_session
from app.gql.schema import make_graphql_router
from app.models import LeagueState
from app.sync.espn import ScoreboardClient, get_scoreboard_client
from app.sync.service import sync_league

log = logging.getLogger(__name__)
STALE_AFTER = timedelta(minutes=30)  # six missed 5-minute crons

def create_app(settings: Settings | None = None, clock: Clock | None = None) -> FastAPI:
    app = FastAPI()
    app.state.settings = settings or Settings()
    app.state.clock = clock or SystemClock()

    @app.get("/health")
    async def health(request: Request, session: AsyncSession = Depends(get_session)):
        """200 only when the DB answers and every league synced recently; point an uptime monitor here."""
        cutoff = request.app.state.clock.now() - STALE_AFTER
        stale = list(await session.scalars(
            select(LeagueState.league).where(LeagueState.last_synced_at < cutoff).order_by(LeagueState.league)
        ))
        return JSONResponse({"ok": False, "stale": stale}, 503) if stale else {"ok": True}

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
        counts: dict[str, int | None] = {}
        for lg in ("nfl", "cfb"):  # one transaction per league: a feed failure in one must not discard the other
            try:
                counts[lg] = await sync_league(session, espn, lg, request.app.state.clock)
                await session.commit()
            except Exception:
                await session.rollback()
                log.exception("sync failed for %s", lg)
                counts[lg] = None
        return JSONResponse(counts, 502) if None in counts.values() else counts

    # no public GraphiQL in prod
    app.include_router(make_graphql_router(ide=not app.state.settings.cookie_secure), prefix="/graphql")
    return app
