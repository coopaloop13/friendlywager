from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Friendship, Game, Pick, User


def mkuser(handle: str, email: str | None = None) -> User:
    return User(email=email or f"{handle}@x.com", handle=handle, password_hash="h")


async def two_users(session):
    a, b = mkuser("alice"), mkuser("bobby")
    session.add_all([a, b])
    await session.flush()
    return a, b


async def game_and_user(session):
    u = mkuser("alice")
    g = Game(
        league="nfl", season=2026, season_type=2, week=1, external_id="1",
        home_name="H", home_abbr="H", away_name="A", away_abbr="A",
        kickoff_at=datetime.now(UTC), status="scheduled",
    )
    session.add_all([u, g])
    await session.flush()
    return u, g


async def test_handle_must_be_lowercase_pattern(session):
    session.add(mkuser("alice"))
    await session.flush()
    session.add(mkuser("Josh", "josh@x.com"))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_handle_unique(session):
    session.add(mkuser("alice"))
    await session.flush()
    session.add(mkuser("alice", "other@x.com"))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_friendship_pair_unique_either_direction(session):
    a, b = await two_users(session)
    session.add(Friendship(requester_id=a.id, addressee_id=b.id, status="pending"))
    await session.flush()
    session.add(Friendship(requester_id=b.id, addressee_id=a.id, status="pending"))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_friendship_not_self(session):
    a, _ = await two_users(session)
    session.add(Friendship(requester_id=a.id, addressee_id=a.id, status="pending"))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_pick_unique_per_user_game(session):
    u, g = await game_and_user(session)
    session.add(Pick(user_id=u.id, game_id=g.id, pred_home=24, pred_away=17))
    await session.flush()
    session.add(Pick(user_id=u.id, game_id=g.id, pred_home=10, pred_away=3))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_pick_cannot_be_tie(session):
    u, g = await game_and_user(session)
    session.add(Pick(user_id=u.id, game_id=g.id, pred_home=3, pred_away=3))
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.parametrize("home", [-1, 201])
async def test_pick_score_range(session, home):
    u, g = await game_and_user(session)
    session.add(Pick(user_id=u.id, game_id=g.id, pred_home=home, pred_away=7))
    with pytest.raises(IntegrityError):
        await session.flush()
