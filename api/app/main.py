import hmac
import logging
from datetime import timedelta

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock, SystemClock
from app.config import Settings
from app.db import get_session
from app.gql.schema import make_graphql_router
from app.models import LeagueState
from app.notify import Notifier, get_notifier
from app.reminders import send_reminders, send_results
from app.sync.espn import ScoreboardClient, get_scoreboard_client
from app.sync.service import IDLE, quiet_until, sync_league

log = logging.getLogger(__name__)
STALE_AFTER = IDLE + timedelta(minutes=30)  # the longest rest between syncs, then six missed 5-minute crons
MAX_BODY = 16 * 1024  # the largest page query is under 1 KB
# The store apps load from these origins and call the API directly with a bearer token (never the cookie).
APP_ORIGINS = ["capacitor://localhost", "https://localhost"]

def create_app(settings: Settings | None = None, clock: Clock | None = None) -> FastAPI:
    app = FastAPI()
    app.state.settings = settings or Settings()
    app.state.clock = clock or SystemClock()
    app.state.quiet_until = None  # in memory only: a fresh container always syncs once
    # visible in the Worker logs after each container start: says whether reminders really go out
    log.warning("push reminders: %s", "Firebase" if app.state.settings.fcm_service_account else "log only")

    app.add_middleware(
        CORSMiddleware, allow_origins=APP_ORIGINS, allow_methods=["POST"], allow_headers=["authorization", "content-type"]
    )

    @app.middleware("http")
    async def cap_body(request: Request, call_next):
        # ponytail: trusts Content-Length; a chunked body skips this. Count bytes on receive if that is abused.
        length = request.headers.get("content-length", "0")
        if not length.isdigit() or int(length) > MAX_BODY:
            return JSONResponse({"errors": [{"message": "Request too large", "extensions": {"code": "INVALID"}}]}, 413)
        return await call_next(request)

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
        notifier: Notifier = Depends(get_notifier),
    ):
        expected = request.app.state.settings.sync_secret.encode()
        if not hmac.compare_digest(x_sync_secret.encode(), expected):
            raise HTTPException(401, "bad sync secret")
        # Between games the cron must not touch Postgres: each query keeps the Neon compute awake (and billed).
        now, quiet = request.app.state.clock.now(), request.app.state.quiet_until
        if quiet and now < quiet:
            return {"quiet_until": quiet.isoformat()}
        request.app.state.quiet_until = None
        counts: dict[str, int | None] = {}
        for lg in ("nfl", "cfb"):  # one transaction per league: a feed failure in one must not discard the other
            try:
                counts[lg] = await sync_league(session, espn, lg, request.app.state.clock)
                await session.commit()
            except Exception:
                await session.rollback()
                log.exception("sync failed for %s", lg)
                counts[lg] = None
        try:  # reminders ride the same cron; a push failure must not report the sync as failed
            await send_reminders(session, notifier, request.app.state.clock)
            await session.commit()
        except Exception:
            await session.rollback()
            log.exception("reminders failed")
        try:  # after the scores are committed: tell friends how the games that just ended went
            await send_results(session, notifier, request.app.state.clock)
            await session.commit()
        except Exception:
            await session.rollback()
            log.exception("result pushes failed")
        if None in counts.values():  # a failed league is retried on the next cron
            return JSONResponse(counts, 502)
        try:
            request.app.state.quiet_until = await quiet_until(session, now)
        except Exception:
            await session.rollback()
            log.exception("could not plan the next sync")
        return counts

    # no public GraphiQL in prod
    app.include_router(make_graphql_router(ide=not app.state.settings.cookie_secure), prefix="/graphql")
    return app
