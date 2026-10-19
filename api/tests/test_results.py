import uuid
from datetime import UTC, datetime, timedelta
from itertools import count

import pytest
from sqlalchemy import select, update

from app import results
from app.errors import Forbidden
from app.models import Friendship, Game, Pick, User
from app.sync.espn import WeekKey
from test_auth import code, gql
from test_friends import RESPOND, SEND, make_user

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
W1 = WeekKey("nfl", 2026, 2, 1)
_ext = count()

MATCHUP = """query($f:ID!){matchup(friendId:$f,league:NFL,season:2026,seasonType:2,week:1){
  myPoints theirPoints games{ game{ id locked } mine{home away} theirs{home away} point }}}"""
H2H = """query($f:ID!){headToHead(friendId:$f,league:NFL,season:2026){
  pointsFor pointsAgainst weeksWon weeksLost weeksTied }}"""
BOARD = "{ leaderboard(league:NFL,season:2026){ userId handle correctWinners avgCloseness } }"


@pytest.fixture
def now(clock):
    clock.dt = NOW
    return NOW


async def mkuser(session, handle):
    u = User(email=f"{handle}@x.com", handle=handle, password_hash="x")
    session.add(u)
    await session.commit()
    return u.id


async def befriend(session, a, b, accepted_at=NOW):
    session.add(Friendship(requester_id=a, addressee_id=b, status="accepted", accepted_at=accepted_at))
    await session.commit()


async def mkgame(session, kickoff=NOW - timedelta(days=1), score=None, status=None,
                 season_type=2, week=1, league="nfl"):
    g = Game(
        league=league, season=2026, season_type=season_type, week=week, external_id=str(next(_ext)),
        home_name="Home", home_abbr="HOM", away_name="Away", away_abbr="AWY", kickoff_at=kickoff,
        status=status or ("final" if score else "scheduled"),
        home_score=score[0] if score else None, away_score=score[1] if score else None,
    )
    session.add(g)
    await session.commit()
    return g.id


async def pick(session, user_id, game_id, home, away):
    session.add(Pick(user_id=user_id, game_id=game_id, pred_home=home, pred_away=away))
    await session.commit()


@pytest.fixture
async def pair(session, now):
    me, them = await mkuser(session, "josh"), await mkuser(session, "maria")
    await befriend(session, me, them)
    return me, them


async def test_friend_pick_hidden_before_kickoff(session, clock, pair):
    me, them = pair
    g = await mkgame(session, kickoff=NOW + timedelta(minutes=1))
    await pick(session, me, g, 21, 14)
    await pick(session, them, g, 30, 3)
    m = await results.matchup(session, clock, me, them, W1)
    [mg] = m.games
    assert mg.mine is not None and mg.theirs is None and mg.point is None


async def test_friend_pick_visible_at_kickoff(session, clock, pair):
    me, them = pair
    g = await mkgame(session, kickoff=NOW)
    await pick(session, them, g, 30, 3)
    [mg] = (await results.matchup(session, clock, me, them, W1)).games
    assert (mg.theirs.home, mg.theirs.away) == (30, 3) and mg.mine is None


async def test_matchup_points_follow_scoring(session, clock, pair):
    me, them = pair
    cases = [  # (actual, mine, theirs, expected point)
        ((20, 10), (5, 30), (3, 40), None),          # neither picked the winner
        ((20, 10), (21, 10), (3, 40), "me"),         # only I did
        ((20, 10), (3, 40), (21, 10), "them"),       # only they did
        ((20, 10), (21, 10), (30, 3), "me"),         # both, I'm closer
        ((20, 10), (30, 3), (20, 9), "them"),        # both, they're closer
        ((20, 10), (21, 10), (19, 10), None),        # both, equal closeness: push
        ((20, 10), (21, 10), None, "me"),            # they didn't pick, I'm right
        ((20, 10), None, None, None),                # nobody picked
        ((17, 17), (21, 10), (10, 21), None),        # actual tie
    ]
    ids = []
    for i, (actual, mine, theirs, _) in enumerate(cases):
        g = await mkgame(session, kickoff=NOW - timedelta(hours=len(cases) - i), score=actual)
        ids.append(g)
        if mine:
            await pick(session, me, g, *mine)
        if theirs:
            await pick(session, them, g, *theirs)
    # not final yet: no point even though both picked and kickoff passed
    live = await mkgame(session, kickoff=NOW - timedelta(minutes=5), status="in_progress")
    await pick(session, me, live, 21, 10)
    m = await results.matchup(session, clock, me, them, W1)
    assert [mg.game.id for mg in m.games] == ids + [live]
    assert [mg.point for mg in m.games] == [c[3] for c in cases] + [None]
    assert (m.my_points, m.their_points) == (3, 2)


async def test_matchup_forbidden_for_non_friend(session, clock, now):
    me, stranger = await mkuser(session, "josh"), await mkuser(session, "eve")
    session.add(Friendship(requester_id=me, addressee_id=stranger, status="pending"))
    await session.commit()
    with pytest.raises(Forbidden):
        await results.matchup(session, clock, me, stranger, W1)
    with pytest.raises(Forbidden):
        await results.head_to_head(session, me, stranger, "nfl", 2026)


async def test_matchup_forbidden_after_unfriend(client, session, now):
    a, aid = await make_user(client, "josh")
    b, bid = await make_user(client, "maria")
    await gql(client, SEND, {"h": "maria"}, a)
    fid = await session.scalar(select(Friendship.id))
    await gql(client, RESPOND, {"i": str(fid), "a": True}, b)
    _, ok = await gql(client, MATCHUP, {"f": bid}, a)
    assert ok["data"]["matchup"] == {"myPoints": 0, "theirPoints": 0, "games": []}
    await gql(client, "mutation($u:ID!){removeFriend(userId:$u)}", {"u": bid}, a)
    for q in (MATCHUP, H2H):
        _, r = await gql(client, q, {"f": bid}, a)
        assert code(r) == "FORBIDDEN"
    _, r = await gql(client, MATCHUP, {"f": str(uuid.uuid4())}, a)
    assert code(r) == "FORBIDDEN"


async def test_matchup_reflects_score_correction(session, clock, pair):
    me, them = pair
    g = await mkgame(session, score=(20, 10))
    await pick(session, me, g, 21, 10)
    await pick(session, them, g, 10, 21)
    assert (await results.matchup(session, clock, me, them, W1)).games[0].point == "me"
    await session.execute(update(Game).where(Game.id == g).values(home_score=10, away_score=20))
    await session.commit()
    m = await results.matchup(session, clock, me, them, W1)
    assert m.games[0].point == "them" and (m.my_points, m.their_points) == (0, 1)


async def test_head_to_head_includes_weeks_before_friendship(session, now):
    me, them = await mkuser(session, "josh"), await mkuser(session, "maria")
    g = await mkgame(session, kickoff=NOW - timedelta(days=30), score=(20, 10))
    await pick(session, me, g, 21, 10)
    await befriend(session, me, them, accepted_at=NOW)
    h = await results.head_to_head(session, me, them, "nfl", 2026)
    assert h == results.HeadToHead(points_for=1, points_against=0, weeks_won=1, weeks_lost=0, weeks_tied=0)


async def test_head_to_head_skips_weeks_neither_picked(session, pair):
    me, them = pair
    await mkgame(session, score=(20, 10), week=1)                # nobody picked: skipped
    g2 = await mkgame(session, score=(20, 10), week=2)
    await pick(session, them, g2, 21, 10)                         # they win week 2
    g3 = await mkgame(session, score=(20, 10), season_type=3, week=1)
    await pick(session, me, g3, 21, 10)                           # postseason counts too
    g4 = await mkgame(session, kickoff=NOW + timedelta(days=1), week=3)
    await pick(session, me, g4, 21, 10)                           # picked, unplayed: week 3 tied 0-0
    other = await mkgame(session, score=(20, 10), league="cfb")
    await pick(session, me, other, 21, 10)                        # other league ignored
    h = await results.head_to_head(session, me, them, "nfl", 2026)
    assert h == results.HeadToHead(points_for=1, points_against=1, weeks_won=1, weeks_lost=1, weeks_tied=1)


async def test_head_to_head_tied_week(client, session, now):
    a, aid = await make_user(client, "josh")
    b, bid = await make_user(client, "maria")
    await befriend(session, uuid.UUID(aid), uuid.UUID(bid))
    g1, g2 = await mkgame(session, score=(20, 10)), await mkgame(session, score=(10, 20))
    await pick(session, uuid.UUID(aid), g1, 21, 10)
    await pick(session, uuid.UUID(bid), g2, 10, 21)
    _, r = await gql(client, H2H, {"f": bid}, a)
    assert r["data"]["headToHead"] == {
        "pointsFor": 1, "pointsAgainst": 1, "weeksWon": 0, "weeksLost": 0, "weeksTied": 1}


async def test_leaderboard_ranks_by_correct_then_closeness(client, session, now):
    a, aid = await make_user(client, "josh")
    ids = {"josh": uuid.UUID(aid)}
    for h in ("maria", "bob", "zed", "amy"):
        ids[h] = await mkuser(session, h)
        await befriend(session, ids["josh"], ids[h])
    g1, g2 = await mkgame(session, score=(20, 10)), await mkgame(session, score=(30, 20))
    unplayed = await mkgame(session, kickoff=NOW + timedelta(days=1))
    await pick(session, ids["josh"], g1, 21, 10)     # 1 correct, closeness 1
    await pick(session, ids["josh"], g2, 10, 20)     # wrong
    await pick(session, ids["maria"], g1, 30, 10)    # 2 correct, closeness 10 and 2 -> 6.0
    await pick(session, ids["maria"], g2, 31, 21)
    await pick(session, ids["bob"], g1, 20, 13)      # 1 correct, closeness 3
    await pick(session, ids["bob"], unplayed, 1, 0)  # unplayed doesn't count
    await pick(session, ids["amy"], g1, 10, 20)      # 0 correct -> None
    _, r = await gql(client, BOARD, headers=a)
    rows = r["data"]["leaderboard"]
    assert [(x["handle"], x["correctWinners"], x["avgCloseness"]) for x in rows] == [
        ("maria", 2, 6.0), ("josh", 1, 1.0), ("bob", 1, 3.0), ("amy", 0, None), ("zed", 0, None)]
    assert rows[1]["userId"] == aid


async def test_leaderboard_excludes_non_friends(session, now):
    me, friend, pending, stranger = [await mkuser(session, h) for h in ("josh", "maria", "pete", "eve")]
    await befriend(session, me, friend)
    session.add(Friendship(requester_id=pending, addressee_id=me, status="pending"))
    await session.commit()
    g = await mkgame(session, score=(20, 10))
    for u in (me, friend, pending, stranger):
        await pick(session, u, g, 21, 10)
    rows = await results.leaderboard(session, me, "nfl", 2026)
    assert sorted(r.handle for r in rows) == ["josh", "maria"]


async def test_postponed_game_reports_locked(client, session, now):
    a, aid = await make_user(client, "josh")
    g = await mkgame(session, kickoff=NOW + timedelta(days=1), status="postponed")
    _, r = await gql(client, "{ week(league:NFL,season:2026,seasonType:2,week:1){ games{ id locked } } }",
                     headers=a)
    assert r["data"]["week"]["games"] == [{"id": str(g), "locked": True}]


async def test_results_require_login(client, now):
    for q, v in [(MATCHUP, {"f": str(uuid.uuid4())}), (H2H, {"f": str(uuid.uuid4())}), (BOARD, None)]:
        _, r = await gql(client, q, v)
        assert code(r) == "UNAUTHENTICATED"


async def test_matchup_graphql_hides_then_shows_friend_pick(client, session, clock, now):
    a, aid = await make_user(client, "josh")
    _, bid = await make_user(client, "maria")
    me, them = uuid.UUID(aid), uuid.UUID(bid)
    await befriend(session, me, them)
    g = await mkgame(session, kickoff=NOW + timedelta(hours=1))
    await pick(session, me, g, 21, 10)
    await pick(session, them, g, 30, 3)
    _, r = await gql(client, MATCHUP, {"f": bid}, a)
    assert r["data"]["matchup"]["games"] == [
        {"game": {"id": str(g), "locked": False}, "mine": {"home": 21, "away": 10}, "theirs": None, "point": None}]
    await session.execute(update(Game).where(Game.id == g).values(status="final", home_score=20, away_score=10))
    await session.commit()
    clock.dt = NOW + timedelta(hours=4)
    _, r = await gql(client, MATCHUP, {"f": bid}, a)
    m = r["data"]["matchup"]
    assert m["games"][0]["theirs"] == {"home": 30, "away": 3} and m["games"][0]["point"] == "me"
    assert (m["myPoints"], m["theirPoints"]) == (1, 0)
