# ponytail: computed on read; cache per-week results if leaderboard queries get slow
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app import friends
from app.clock import Clock
from app.errors import Forbidden
from app.models import Game, Pick, User
from app.scoring import Score, closeness, game_point, picked_winner, week_result
from app.sync.espn import WeekKey


@dataclass
class MatchupGame:
    game: Game
    mine: Score | None
    theirs: Score | None
    point: Literal["me", "them"] | None


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
class LeaderboardRow:
    user_id: uuid.UUID
    handle: str
    correct_winners: int
    avg_closeness: float | None


def _score(p: Pick | None) -> Score | None:
    return Score(p.pred_home, p.pred_away) if p else None


def _actual(g: Game) -> Score | None:
    """The final score, or None when the game doesn't score yet."""
    if g.status != "final" or g.home_score is None or g.away_score is None:
        return None
    return Score(g.home_score, g.away_score)


def _point(g: Game, mine: Score | None, theirs: Score | None) -> Literal["me", "them"] | None:
    actual = _actual(g)
    if actual is None:
        return None
    return {"a": "me", "b": "them", None: None}[game_point(actual, mine, theirs)]


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
        games.append(MatchupGame(g, mine, theirs, _point(g, mine, theirs) if visible else None))
    return Matchup(
        games,
        sum(mg.point == "me" for mg in games),
        sum(mg.point == "them" for mg in games),
    )


async def head_to_head(
    session: AsyncSession, me: uuid.UUID, friend_id: uuid.UUID, league: str, season: int
) -> HeadToHead:
    await _require_friend(session, me, friend_id)
    rows = await _pair_rows(session, me, friend_id, Game.league == league, Game.season == season)
    weeks: dict[tuple[int, int], list[int]] = {}  # only weeks where someone picked
    pts_for = pts_against = 0
    for g, pa, pb in rows:
        wk = (g.season_type, g.week)
        if pa or pb:
            weeks.setdefault(wk, [0, 0])
        point = _point(g, _score(pa), _score(pb))
        if point == "me":
            pts_for += 1
            weeks[wk][0] += 1
        elif point == "them":
            pts_against += 1
            weeks[wk][1] += 1
    outcomes = [week_result(a, b) for a, b in weeks.values()]
    return HeadToHead(pts_for, pts_against, outcomes.count("a"), outcomes.count("b"), outcomes.count("tie"))


async def leaderboard(session: AsyncSession, me: uuid.UUID, league: str, season: int) -> list[LeaderboardRow]:
    users = [await session.get(User, me), *await friends.list_friends(session, me)]
    q = (
        select(Pick, Game)
        .join(Game, Game.id == Pick.game_id)
        .where(
            Pick.user_id.in_([u.id for u in users]), Game.league == league, Game.season == season,
            Game.status == "final",
        )
    )
    correct: dict[uuid.UUID, list[int]] = defaultdict(list)
    for p, g in (await session.execute(q)).all():
        actual = _actual(g)
        if actual and picked_winner(_score(p), actual):
            correct[p.user_id].append(closeness(_score(p), actual))
    rows = [
        LeaderboardRow(u.id, u.handle, len(correct[u.id]), sum(c) / len(c) if (c := correct[u.id]) else None)
        for u in users
    ]
    rows.sort(key=lambda r: (-r.correct_winners, r.avg_closeness is None, r.avg_closeness or 0, r.handle))
    return rows
