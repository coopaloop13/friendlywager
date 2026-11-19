from datetime import datetime, timedelta

from sqlalchemy import and_, case, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock
from app.models import Game, LeagueState
from app.reminders import WINDOW
from app.sync.espn import GameData, ScoreboardClient, WeekKey, parse_scoreboard

TOP_25 = 25
IDLE = timedelta(hours=1)  # with no game near, the cron still reads the feed this often (new games, spreads)
LEAD = WINDOW + timedelta(minutes=10)  # be back before the "picks lock soon" reminders are due
OVERDUE = timedelta(hours=8)  # a game still unfinished this long after kickoff was dropped by the feed


def _wanted(league: str, g: GameData, existing: set[str]) -> bool:
    if league != "cfb" or g.external_id in existing:
        return True
    return any(r is not None and r <= TOP_25 for r in (g.home_rank, g.away_rank))


async def _upsert(session: AsyncSession, league: str, games: list[GameData], now) -> int:
    ids = [g.external_id for g in games]
    existing = set(
        await session.scalars(
            select(Game.external_id).where(Game.league == league, Game.external_id.in_(ids))
        )
    )
    rows = [vars(g) for g in games if _wanted(league, g, existing)]
    if not rows:
        return 0
    stmt = insert(Game).values([{**r, "updated_at": now} for r in rows])
    cols = {c: stmt.excluded[c] for c in [*rows[0], "updated_at"] if c not in ("league", "external_id")}
    # One-way lock: once stored kickoff has passed it may move earlier, never later
    # (picks are already revealed). Earlier-or-equal moves and future kickoffs update freely.
    # A kickoff dated before the season's own year is feed junk (the feed once sent 1993 for every
    # game): never taken from the feed, and replaced by the next real date if one got stored.
    old, new = Game.__table__.c.kickoff_at, stmt.excluded.kickoff_at
    season_start = func.make_timestamptz(Game.__table__.c.season, 1, 1, 0, 0, 0, "UTC")
    cols["kickoff_at"] = case(
        (new < season_start, old),
        (and_(old <= now, new > old, old >= season_start), old),
        else_=new,
    )
    await session.execute(
        stmt.on_conflict_do_update(index_elements=["league", "external_id"], set_=cols)
    )
    return len(rows)


async def sync_league(session: AsyncSession, client: ScoreboardClient, league: str, clock: Clock) -> int:
    """Upsert the current week (and the previous one on rollover). Never commits."""
    payload = await client.fetch(league)
    week = (payload.get("week") or {}).get("number")
    now = clock.now()
    if payload["season"]["type"] not in (2, 3) or week is None:
        # preseason/offseason: nothing to load; the week stays put, but the feed answered
        await session.execute(update(LeagueState).where(LeagueState.league == league).values(last_synced_at=now))
        return 0
    key, games = parse_scoreboard(league, payload)
    n = await _upsert(session, league, games, now)

    prev = await session.get(LeagueState, league)
    if prev and (prev.season, prev.season_type, prev.week) != (key.season, key.season_type, key.week):
        _, old = parse_scoreboard(
            league,
            await client.fetch(league, WeekKey(league, prev.season, prev.season_type, prev.week)),
        )
        n += await _upsert(session, league, old, now)

    state = insert(LeagueState).values(
        league=league, season=key.season, season_type=key.season_type, week=key.week, last_synced_at=now
    )
    await session.execute(
        state.on_conflict_do_update(
            index_elements=["league"],
            set_={c: state.excluded[c] for c in ("season", "season_type", "week", "last_synced_at")},
        )
    )
    return n


async def quiet_until(session: AsyncSession, now: datetime) -> datetime:
    """When the cron next has work in the database: `now` around a game, else up to IDLE away.

    The cron skips the database until then, so the Neon compute can suspend between games.
    """
    unfinished = Game.status.in_(("scheduled", "in_progress"))
    if await session.scalar(
        select(Game.id).where(unfinished, Game.kickoff_at > now - OVERDUE, Game.kickoff_at <= now + LEAD).limit(1)
    ):
        return now
    upcoming = await session.scalar(select(func.min(Game.kickoff_at)).where(unfinished, Game.kickoff_at > now))
    return min(now + IDLE, upcoming - LEAD) if upcoming else now + IDLE
