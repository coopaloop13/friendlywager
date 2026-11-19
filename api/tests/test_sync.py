from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.db import get_session
from app.main import create_app
from app.models import Game, LeagueState
from app.sync.espn import WeekKey, get_scoreboard_client
from app.sync.service import IDLE, quiet_until, sync_league


def ev(id, state="pre", name="STATUS_SCHEDULED", home_rank=99, away_rank=99, hs="0", as_="0",
       date="2026-10-20T00:15Z", notes=None):
    return {
        "id": id, "date": date,
        "status": {"type": {"state": state, "name": name}},
        "competitions": [{"notes": notes or [], "competitors": [
            {"homeAway": "home", "score": hs, "team": {"displayName": f"H{id}", "abbreviation": "H"},
             "curatedRank": {"current": home_rank}},
            {"homeAway": "away", "score": as_, "team": {"displayName": f"A{id}", "abbreviation": "A"},
             "curatedRank": {"current": away_rank}},
        ]}],
    }


def pl(week, *events, type=2):
    return {"season": {"year": 2026, "type": type}, "week": {"number": week}, "events": list(events)}


class FakeClient:
    def __init__(self, current, weeks=None):
        self.current, self.weeks, self.calls = current, weeks or {}, []

    async def fetch(self, league, key: WeekKey | None = None):
        self.calls.append(key)
        return self.weeks[key.week] if key else self.current


async def count(session):
    return await session.scalar(select(func.count()).select_from(Game))


async def test_cfb_unranked_new_game_skipped(session, clock):
    n = await sync_league(session, FakeClient(pl(8, ev("1"), ev("2", home_rank=7))), "cfb", clock)
    assert n == 1 and await count(session) == 1


async def test_existing_cfb_game_kept_when_unranked(session, clock):
    await sync_league(session, FakeClient(pl(8, ev("2", home_rank=7))), "cfb", clock)
    await sync_league(session, FakeClient(pl(8, ev("2", "post", "STATUS_FINAL", hs="3", as_="1"))), "cfb", clock)
    g = await session.scalar(select(Game))
    assert g.status == "final" and g.home_rank is None


async def test_sync_updates_final_score(session, clock):
    await sync_league(session, FakeClient(pl(6, ev("1"))), "nfl", clock)
    await sync_league(session, FakeClient(pl(6, ev("1", "post", "STATUS_FINAL", hs="24", as_="17"))), "nfl", clock)
    g = await session.scalar(select(Game))
    assert (g.home_score, g.away_score, g.status) == (24, 17, "final") and await count(session) == 1


async def test_sync_sets_league_state(session, clock):
    await sync_league(session, FakeClient(pl(6, ev("1"))), "nfl", clock)
    s = await session.get(LeagueState, "nfl")
    assert (s.season, s.season_type, s.week) == (2026, 2, 6)


async def test_offseason_skipped_and_state_unchanged(session, clock):
    await sync_league(session, FakeClient(pl(6, ev("1"))), "nfl", clock)
    n = await sync_league(session, FakeClient(pl(1, ev("9"), type=4)), "nfl", clock)
    assert n == 0 and await count(session) == 1
    assert (await session.get(LeagueState, "nfl")).week == 6


async def test_preseason_skipped(session, clock):
    n = await sync_league(session, FakeClient(pl(2, ev("9"), type=1)), "nfl", clock)
    assert n == 0 and await count(session) == 0 and await session.get(LeagueState, "nfl") is None


async def test_pro_bowl_excluded(session, clock):
    bowl = ev("8", notes=[{"type": "event", "headline": "Pro Bowl Games"}])
    n = await sync_league(session, FakeClient(pl(4, bowl, ev("9"), type=3)), "nfl", clock)
    assert n == 1 and (await session.scalar(select(Game.external_id))) == "9"


async def test_kickoff_lock_is_one_way(session, clock):
    clock.dt = datetime.fromisoformat("2026-10-21T00:00Z")  # after the 2026-10-20T00:15Z kickoff
    await sync_league(session, FakeClient(pl(6, ev("1"))), "nfl", clock)
    await sync_league(session, FakeClient(pl(6, ev("1", date="2099-01-01T00:00Z"))), "nfl", clock)
    g = await session.scalar(select(Game))
    assert g.kickoff_at == datetime.fromisoformat("2026-10-20T00:15Z")
    assert g.kickoff_at <= clock.now()  # still locked


async def test_feed_kickoff_before_the_season_is_ignored(session, clock):
    clock.dt = datetime.fromisoformat("2026-10-19T00:00Z")  # before kickoff: picks are open
    await sync_league(session, FakeClient(pl(6, ev("1"))), "nfl", clock)
    await sync_league(session, FakeClient(pl(6, ev("1", date="1993-01-31T23:30Z"))), "nfl", clock)
    assert (await session.scalar(select(Game))).kickoff_at == datetime.fromisoformat("2026-10-20T00:15Z")


async def test_stored_kickoff_before_the_season_is_replaced(session, clock):
    clock.dt = datetime.fromisoformat("2026-10-19T00:00Z")
    await sync_league(session, FakeClient(pl(6, ev("1", date="1993-01-31T23:30Z"))), "nfl", clock)
    await sync_league(session, FakeClient(pl(6, ev("1"))), "nfl", clock)
    assert (await session.scalar(select(Game))).kickoff_at == datetime.fromisoformat("2026-10-20T00:15Z")


async def test_future_kickoff_moves_freely(session, clock):
    await sync_league(session, FakeClient(pl(6, ev("1", date="2099-01-01T00:00Z"))), "nfl", clock)
    await sync_league(session, FakeClient(pl(6, ev("1", date="2099-02-01T00:00Z"))), "nfl", clock)
    await sync_league(session, FakeClient(pl(6, ev("1", date="2098-12-01T00:00Z"))), "nfl", clock)
    await sync_league(session, FakeClient(pl(6, ev("1", date="2099-03-01T00:00Z"))), "nfl", clock)
    assert (await session.scalar(select(Game))).kickoff_at == datetime.fromisoformat("2099-03-01T00:00Z")


async def test_rollover_also_updates_previous_week(session, clock):
    await sync_league(session, FakeClient(pl(6, ev("1", "in", "STATUS_IN_PROGRESS", hs="3"))), "nfl", clock)
    client = FakeClient(pl(7, ev("2")), {6: pl(6, ev("1", "post", "STATUS_FINAL", hs="27", as_="20"))})
    await sync_league(session, client, "nfl", clock)
    g1 = await session.scalar(select(Game).where(Game.external_id == "1"))
    assert g1.status == "final" and g1.home_score == 27
    assert client.calls == [None, WeekKey("nfl", 2026, 2, 6)]
    assert (await session.get(LeagueState, "nfl")).week == 7


async def test_internal_sync_requires_secret(client):
    r = await client.post("/internal/sync")
    assert r.status_code == 401
    r = await client.post("/internal/sync", headers={"X-Sync-Secret": "wrong"})
    assert r.status_code == 401


async def test_internal_sync_runs(client, session):
    fake = FakeClient(pl(6, ev("1")))
    client._transport.app.dependency_overrides[get_scoreboard_client] = lambda: fake
    r = await client.post("/internal/sync", headers={"X-Sync-Secret": "test-sync-secret-0123456789"})
    assert r.status_code == 200 and r.json() == {"nfl": 1, "cfb": 0}
    assert await count(session) == 1


class BrokenFor(FakeClient):
    def __init__(self, bad, current):
        super().__init__(current)
        self.bad = bad

    async def fetch(self, league, key: WeekKey | None = None):
        if league == self.bad:
            raise RuntimeError("espn down")
        return await super().fetch(league, key)


async def test_one_league_failing_does_not_discard_the_other(client, session):
    for bad, good in (("cfb", "nfl"), ("nfl", "cfb")):
        fake = BrokenFor(bad, pl(6, ev(f"g-{good}", home_rank=1)))
        client._transport.app.dependency_overrides[get_scoreboard_client] = lambda: fake
        r = await client.post("/internal/sync", headers={"X-Sync-Secret": "test-sync-secret-0123456789"})
        assert r.status_code == 502 and r.json() == {good: 1, bad: None}  # cron sees the failure
        await session.rollback()  # only committed rows count
        assert await session.scalar(select(Game.league).where(Game.external_id == f"g-{good}")) == good


async def test_sync_records_last_synced_at_even_in_offseason(session, clock):
    await sync_league(session, FakeClient(pl(6, ev("1"))), "nfl", clock)
    assert (await session.get(LeagueState, "nfl")).last_synced_at == clock.now()
    clock.dt = datetime.fromisoformat("2027-03-01T00:00Z")
    await sync_league(session, FakeClient(pl(1, type=4)), "nfl", clock)
    state = await session.get(LeagueState, "nfl", populate_existing=True)
    assert state.last_synced_at == clock.now() and state.week == 6


def test_empty_sync_secret_rejected():
    import pytest
    from pydantic import ValidationError

    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(database_url="x", session_secret="s" * 32, sync_secret="")


T0 = datetime.fromisoformat("2026-10-20T00:00Z")


async def kickoffs(session, clock, *events):
    clock.dt = T0
    await sync_league(session, FakeClient(pl(6, *events)), "nfl", clock)
    return await quiet_until(session, T0)


def at(**delta):
    return (T0 + timedelta(**delta)).strftime("%Y-%m-%dT%H:%MZ")


async def test_the_cron_stays_on_the_database_around_a_game(session, clock):
    assert await kickoffs(session, clock, ev("1", "in", "STATUS_IN_PROGRESS", date=at(hours=-3))) == T0
    assert await kickoffs(session, clock, ev("2", date=at(minutes=65))) == T0  # reminders go out an hour ahead
    assert await kickoffs(session, clock, ev("3", date=at(hours=-1))) == T0  # kicked off, feed not caught up


async def test_the_cron_rests_until_an_hour_before_the_next_kickoff(session, clock):
    assert await quiet_until(session, T0) == T0 + IDLE  # no games at all
    assert await kickoffs(session, clock, ev("1", date=at(days=2))) == T0 + IDLE  # still checks the feed hourly
    assert await kickoffs(session, clock, ev("2", date=at(minutes=100))) == T0 + timedelta(minutes=30)


async def test_a_game_the_feed_abandoned_does_not_keep_the_cron_busy(session, clock):
    stuck = (ev("1", "in", "STATUS_IN_PROGRESS", date=at(days=-2)), ev("2", date=at(days=-2)))
    assert await kickoffs(session, clock, *stuck) == T0 + IDLE


async def test_internal_sync_skips_the_database_between_games(client, session, clock):
    clock.dt = T0
    fake = FakeClient(pl(6, ev("1", date=at(days=2))))
    app = client._transport.app
    app.dependency_overrides[get_scoreboard_client] = lambda: fake
    secret = {"X-Sync-Secret": "test-sync-secret-0123456789"}
    assert (await client.post("/internal/sync", headers=secret)).json() == {"nfl": 1, "cfb": 0}
    calls = len(fake.calls)

    real = app.dependency_overrides[get_session]
    app.dependency_overrides[get_session] = lambda: None  # any query would be a 500
    clock.dt = T0 + IDLE - timedelta(minutes=5)
    r = await client.post("/internal/sync", headers=secret)
    assert r.status_code == 200 and r.json() == {"quiet_until": (T0 + IDLE).isoformat()}
    assert len(fake.calls) == calls  # nor the feed
    assert (await client.post("/internal/sync", headers={"X-Sync-Secret": "wrong"})).status_code == 401

    app.dependency_overrides[get_session] = real
    clock.dt = T0 + IDLE
    assert (await client.post("/internal/sync", headers=secret)).json() == {"nfl": 1, "cfb": 0}
