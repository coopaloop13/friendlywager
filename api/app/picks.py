import uuid
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock
from app.errors import Invalid, Locked, NotFound
from app.models import Game, LeagueState, Pick
from app.sync.espn import WeekKey


def is_locked(game: Game, now: datetime) -> bool:
    return now >= game.kickoff_at


async def _open_game(session: AsyncSession, clock: Clock, game_id: uuid.UUID) -> Game:
    game = await session.get(Game, game_id)
    if game is None:
        raise NotFound("No such game")
    if is_locked(game, clock.now()) or game.status != "scheduled":
        raise Locked("Picks are locked for this game")
    return game


async def save_pick(
    session: AsyncSession, clock: Clock, user_id: uuid.UUID, game_id: uuid.UUID, home: int, away: int
) -> Pick:
    if not (0 <= home <= 200 and 0 <= away <= 200):
        raise Invalid("Scores must be between 0 and 200")
    if home == away:
        raise Invalid("Picks can't be a tie")
    await _open_game(session, clock, game_id)
    stmt = insert(Pick).values(user_id=user_id, game_id=game_id, pred_home=home, pred_away=away)
    stmt = stmt.on_conflict_do_update(
        index_elements=["user_id", "game_id"],
        set_={"pred_home": home, "pred_away": away, "updated_at": clock.now()},
    ).returning(Pick)
    pick = (await session.execute(stmt.execution_options(populate_existing=True))).scalar_one()
    return pick


async def delete_pick(session: AsyncSession, clock: Clock, user_id: uuid.UUID, game_id: uuid.UUID) -> None:
    await _open_game(session, clock, game_id)
    await session.execute(delete(Pick).where(Pick.user_id == user_id, Pick.game_id == game_id))


async def current_week(session: AsyncSession, league: str) -> WeekKey | None:
    s = await session.get(LeagueState, league)
    return WeekKey(s.league, s.season, s.season_type, s.week) if s else None


async def week_games(session: AsyncSession, user_id: uuid.UUID, key: WeekKey) -> list[tuple[Game, Pick | None]]:
    q = (
        select(Game, Pick)
        .outerjoin(Pick, (Pick.game_id == Game.id) & (Pick.user_id == user_id))
        .where(
            Game.league == key.league, Game.season == key.season,
            Game.season_type == key.season_type, Game.week == key.week,
        )
        .order_by(Game.kickoff_at, Game.id)
    )
    return [(g, p) for g, p in (await session.execute(q)).all()]
