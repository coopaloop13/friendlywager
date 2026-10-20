import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app import picks
from app.errors import Invalid, Locked, NotFound
from app.models import Game, LeagueState, Pick
from app.sync.espn import WeekKey
from test_auth import code, gql
from test_friends import make_user

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
SAVE = "mutation($g:ID!,$h:Int!,$a:Int!){savePick(gameId:$g,home:$h,away:$a){home away}}"
DELETE = "mutation($g:ID!){deletePick(gameId:$g)}"
WEEK = """query($s:Int!){week(league:NFL,season:$s,seasonType:2,week:1){
  league season seasonType week
  games{id homeName awayAbbr homeLogo awayLogo kickoffAt status spread locked myPick{home away}}}}"""
CURRENT = "{ currentWeek(league:NFL){ season week games{ id } } }"


@pytest.fixture
def now(clock):
    clock.dt = NOW
    return NOW


async def mkgame(session, kickoff, ext="1", **kw):
    g = Game(
        league="nfl", season=2026, season_type=2, week=1, external_id=ext,
        home_name="Home", home_abbr="HOM", away_name="Away", away_abbr="AWY",
        kickoff_at=kickoff, status="scheduled", **kw,
    )
    session.add(g)
    await session.commit()  # the app rolls back leftovers after each operation
    session.expunge(g)
    return g


async def mkuser(client):
    h, uid = await make_user(client, "josh")
    return h, uuid.UUID(uid)


async def test_save_pick_before_kickoff(client, session, now):
    h, _ = await mkuser(client)
    g = await mkgame(session, now + timedelta(hours=1))
    _, r = await gql(client, SAVE, {"g": str(g.id), "h": 24, "a": 17}, h)
    assert r["data"]["savePick"] == {"home": 24, "away": 17}


async def test_edit_pick_before_kickoff_overwrites(client, session, now):
    h, uid = await mkuser(client)
    g = await mkgame(session, now + timedelta(hours=1))
    await gql(client, SAVE, {"g": str(g.id), "h": 24, "a": 17}, h)
    await gql(client, SAVE, {"g": str(g.id), "h": 10, "a": 20}, h)
    rows = (await session.scalars(select(Pick))).all()
    assert [(p.pred_home, p.pred_away) for p in rows] == [(10, 20)]


async def test_save_pick_at_kickoff_locked(client, session, now):
    h, _ = await mkuser(client)
    g = await mkgame(session, now)
    _, r = await gql(client, SAVE, {"g": str(g.id), "h": 24, "a": 17}, h)
    assert code(r) == "LOCKED"


async def test_save_pick_non_scheduled_locked(client, session, clock, now):
    h, uid = await mkuser(client)
    g = await mkgame(session, now + timedelta(hours=1))
    await session.execute(update(Game).where(Game.id == g.id).values(status="postponed"))
    await session.commit()
    with pytest.raises(Locked):
        await picks.save_pick(session, clock, uid, g.id, 1, 2)


async def test_delete_pick_after_kickoff_locked(client, session, clock, now):
    h, uid = await mkuser(client)
    g = await mkgame(session, now + timedelta(hours=1))
    await gql(client, SAVE, {"g": str(g.id), "h": 24, "a": 17}, h)
    _, ok = await gql(client, DELETE, {"g": str(g.id)}, h)
    assert ok["data"]["deletePick"] is True
    await gql(client, SAVE, {"g": str(g.id), "h": 24, "a": 17}, h)
    clock.dt = now + timedelta(hours=2)
    _, r = await gql(client, DELETE, {"g": str(g.id)}, h)
    assert code(r) == "LOCKED"
    assert await session.get(Pick, (uid, g.id)) is not None


@pytest.mark.parametrize("home,away", [(10, 10), (-1, 3), (3, 201)])
async def test_tie_pick_invalid(client, session, now, home, away):
    h, _ = await mkuser(client)
    g = await mkgame(session, now + timedelta(hours=1))
    _, r = await gql(client, SAVE, {"g": str(g.id), "h": home, "a": away}, h)
    assert code(r) == "INVALID"


async def test_unknown_and_malformed_game_not_found(client, now):
    h, _ = await mkuser(client)
    for gid in (str(uuid.uuid4()), "nope"):
        _, r = await gql(client, SAVE, {"g": gid, "h": 1, "a": 2}, h)
        assert code(r) == "NOT_FOUND"


async def test_kickoff_moved_later_reopens(client, session, clock, now):
    h, _ = await mkuser(client)
    g = await mkgame(session, now + timedelta(hours=1))
    clock.dt = now + timedelta(hours=2)
    _, r = await gql(client, SAVE, {"g": str(g.id), "h": 3, "a": 1}, h)
    assert code(r) == "LOCKED"
    await session.execute(update(Game).where(Game.id == g.id).values(kickoff_at=now + timedelta(days=1)))
    await session.commit()
    _, r = await gql(client, SAVE, {"g": str(g.id), "h": 3, "a": 1}, h)
    assert r["data"]["savePick"] == {"home": 3, "away": 1}


async def test_week_view_shows_my_pick_and_spread(client, session, now):
    h, _ = await mkuser(client)
    h2, _ = await make_user(client, "maria")
    g2 = await mkgame(session, now + timedelta(hours=5), ext="2", spread_text="HOM -3", home_logo="https://x/hom.png")
    g1 = await mkgame(session, now - timedelta(hours=1), ext="1")
    await gql(client, SAVE, {"g": str(g2.id), "h": 24, "a": 17}, h)
    _, r = await gql(client, WEEK, {"s": 2026}, h)
    w = r["data"]["week"]
    assert (w["league"], w["season"], w["seasonType"], w["week"]) == ("NFL", 2026, 2, 1)
    first, second = w["games"]
    assert first["id"] == str(g1.id) and first["locked"] is True and first["myPick"] is None
    assert second["spread"] == "HOM -3" and second["locked"] is False
    assert (second["homeLogo"], second["awayLogo"]) == ("https://x/hom.png", None)
    assert second["myPick"] == {"home": 24, "away": 17}
    _, r2 = await gql(client, WEEK, {"s": 2026}, h2)
    assert r2["data"]["week"]["games"][1]["myPick"] is None


async def test_current_week(client, session, now):
    h, _ = await mkuser(client)
    _, r = await gql(client, CURRENT, headers=h)
    assert r["data"]["currentWeek"] is None
    g = await mkgame(session, now)
    session.add(LeagueState(league="nfl", season=2026, season_type=2, week=1))
    await session.commit()
    _, r = await gql(client, CURRENT, headers=h)
    assert r["data"]["currentWeek"] == {"season": 2026, "week": 1, "games": [{"id": str(g.id)}]}
    assert await picks.current_week(session, "cfb") is None
    assert await picks.current_week(session, "nfl") == WeekKey("nfl", 2026, 2, 1)


async def test_picks_require_login(client, session, now):
    g = await mkgame(session, now + timedelta(hours=1))
    for q, v in [(SAVE, {"g": str(g.id), "h": 2, "a": 1}), (DELETE, {"g": str(g.id)}),
                 (WEEK, {"s": 2026}), (CURRENT, None)]:
        _, r = await gql(client, q, v)
        assert code(r) == "UNAUTHENTICATED"
