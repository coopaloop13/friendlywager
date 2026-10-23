# ponytail: computed on read; cache per-week results if leaderboard queries get slow
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app import friends
from app.clock import Clock
from app.errors import Forbidden
from app.models import Game, Pick
from app.scoring import Score, game_points, week_result
from app.sync.espn import WeekKey


@dataclass
class MatchupGame:
    game: Game
    mine: Score | None
    theirs: Score | None
    my_points: int
    their_points: int


@dataclass
class Matchup:
    games: list[MatchupGame]
    my_points: int
    their_points: int


@dataclass
class HeadToHead:
    points_for: int
    points_against: int
    weeks_won: int
    weeks_lost: int
    weeks_tied: int


@dataclass
class LeaderboardRow(HeadToHead):
    user_id: uuid.UUID
    handle: str


def _score(p: Pick | None) -> Score | None:
    return Score(p.pred_home, p.pred_away) if p else None


def _actual(g: Game) -> Score | None:
    """The final score, or None when the game doesn't score yet."""
    if g.status != "final" or g.home_score is None or g.away_score is None:
        return None
    return Score(g.home_score, g.away_score)


def _points(g: Game, mine: Score | None, theirs: Score | None) -> tuple[int, int]:
    actual = _actual(g)
    return game_points(actual, mine, theirs) if actual else (0, 0)


async def _require_friend(session: AsyncSession, me: uuid.UUID, friend_id: uuid.UUID) -> None:
    if not await friends.are_friends(session, me, friend_id):
        raise Forbidden("Not friends")


async def _pair_rows(session: AsyncSession, me: uuid.UUID, them: uuid.UUID, *where):
    """Every matching game with both players' picks, in one query."""
    pa, pb = aliased(Pick), aliased(Pick)
    q = (
        select(Game, pa, pb)
        .outerjoin(pa, (pa.game_id == Game.id) & (pa.user_id == me))
        .outerjoin(pb, (pb.game_id == Game.id) & (pb.user_id == them))
        .where(*where)
        .order_by(Game.kickoff_at, Game.id)
    )
    return (await session.execute(q)).all()


async def matchup(
    session: AsyncSession, clock: Clock, me: uuid.UUID, friend_id: uuid.UUID, key: WeekKey
) -> Matchup:
    await _require_friend(session, me, friend_id)
    rows = await _pair_rows(
        session, me, friend_id,
        Game.league == key.league, Game.season == key.season,
        Game.season_type == key.season_type, Game.week == key.week,
    )
    now = clock.now()
    games = []
    for g, pa, pb in rows:
        visible = now >= g.kickoff_at  # a friend's pick, or its existence, never shows before kickoff
        mine, theirs = _score(pa), (_score(pb) if visible else None)
        games.append(MatchupGame(g, mine, theirs, *(_points(g, mine, theirs) if visible else (0, 0))))
    return Matchup(games, sum(mg.my_points for mg in games), sum(mg.their_points for mg in games))


async def head_to_head(
    session: AsyncSession, clock: Clock, me: uuid.UUID, friend_id: uuid.UUID, league: str, season: int
) -> HeadToHead:
    await _require_friend(session, me, friend_id)
    rows = await _pair_rows(session, me, friend_id, Game.league == league, Game.season == season)
    now = clock.now()
    # only weeks where someone picked a game that has kicked off; earlier picks must not leak
    weeks: dict[tuple[int, int], list[int]] = {}
    pts_for = pts_against = 0
    for g, pa, pb in rows:
        wk = (g.season_type, g.week)
        if (pa or pb) and now >= g.kickoff_at:
            weeks.setdefault(wk, [0, 0])
        mine, theirs = _points(g, _score(pa), _score(pb))
        pts_for += mine
        pts_against += theirs
        if wk in weeks:
            weeks[wk][0] += mine
            weeks[wk][1] += theirs
    outcomes = [week_result(a, b) for a, b in weeks.values()]
    return HeadToHead(pts_for, pts_against, outcomes.count("a"), outcomes.count("b"), outcomes.count("tie"))


async def leaderboard(
    session: AsyncSession, clock: Clock, me: uuid.UUID, league: str, season: int
) -> list[LeaderboardRow]:
    """My head-to-head record against each friend this season."""
    # ponytail: one query per friend; batch into one if friend lists get long
    rows = [
        LeaderboardRow(**vars(await head_to_head(session, clock, me, u.id, league, season)), user_id=u.id, handle=u.handle)
        for u in await friends.list_friends(session, me)
    ]
    rows.sort(key=lambda r: (-r.weeks_won, r.points_against - r.points_for, r.handle))
    return rows
