from sqlalchemy import and_, case, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock
from app.models import Game, LeagueState
from app.sync.espn import GameData, ScoreboardClient, WeekKey, parse_scoreboard

TOP_25 = 25


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
    old = Game.__table__.c.kickoff_at
    cols["kickoff_at"] = case(
        (and_(old <= now, stmt.excluded.kickoff_at > old), old), else_=stmt.excluded.kickoff_at
    )
    await session.execute(
        stmt.on_conflict_do_update(index_elements=["league", "external_id"], set_=cols)
    )
    return len(rows)


async def sync_league(session: AsyncSession, client: ScoreboardClient, league: str, clock: Clock) -> int:
    """Upsert the current week (and the previous one on rollover). Never commits."""
    payload = await client.fetch(league)
    week = (payload.get("week") or {}).get("number")
    if payload["season"]["type"] not in (2, 3) or week is None:
        return 0  # preseason/offseason: nothing to load, leave LeagueState alone
    now = clock.now()
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
        league=league, season=key.season, season_type=key.season_type, week=key.week
    )
    await session.execute(
        state.on_conflict_do_update(
            index_elements=["league"],
            set_={c: state.excluded[c] for c in ("season", "season_type", "week")},
        )
    )
    return n
