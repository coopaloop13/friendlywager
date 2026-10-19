from sqlalchemy import func, select

from app.main import create_app
from app.models import Game, LeagueState
from app.sync.espn import WeekKey, get_scoreboard_client
from app.sync.service import sync_league


def ev(id, state="pre", name="STATUS_SCHEDULED", home_rank=99, away_rank=99, hs="0", as_="0"):
    return {
        "id": id, "date": "2026-10-20T00:15Z",
        "status": {"type": {"state": state, "name": name}},
        "competitions": [{"competitors": [
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


async def test_cfb_unranked_new_game_skipped(session):
    n = await sync_league(session, FakeClient(pl(8, ev("1"), ev("2", home_rank=7))), "cfb")
    assert n == 1 and await count(session) == 1


async def test_existing_cfb_game_kept_when_unranked(session):
    await sync_league(session, FakeClient(pl(8, ev("2", home_rank=7))), "cfb")
    await sync_league(session, FakeClient(pl(8, ev("2", "post", "STATUS_FINAL", hs="3", as_="1"))), "cfb")
    g = await session.scalar(select(Game))
    assert g.status == "final" and g.home_rank is None


async def test_sync_updates_final_score(session):
    await sync_league(session, FakeClient(pl(6, ev("1"))), "nfl")
    await sync_league(session, FakeClient(pl(6, ev("1", "post", "STATUS_FINAL", hs="24", as_="17"))), "nfl")
    g = await session.scalar(select(Game))
    assert (g.home_score, g.away_score, g.status) == (24, 17, "final") and await count(session) == 1


async def test_sync_sets_league_state(session):
    await sync_league(session, FakeClient(pl(6, ev("1"))), "nfl")
    s = await session.get(LeagueState, "nfl")
    assert (s.season, s.season_type, s.week) == (2026, 2, 6)


async def test_offseason_skipped_and_state_unchanged(session):
    await sync_league(session, FakeClient(pl(6, ev("1"))), "nfl")
    n = await sync_league(session, FakeClient(pl(1, ev("9"), type=4)), "nfl")
    assert n == 0 and await count(session) == 1
    assert (await session.get(LeagueState, "nfl")).week == 6


async def test_rollover_also_updates_previous_week(session):
    await sync_league(session, FakeClient(pl(6, ev("1", "in", "STATUS_IN_PROGRESS", hs="3"))), "nfl")
    client = FakeClient(pl(7, ev("2")), {6: pl(6, ev("1", "post", "STATUS_FINAL", hs="27", as_="20"))})
    await sync_league(session, client, "nfl")
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
    r = await client.post("/internal/sync", headers={"X-Sync-Secret": "test-sync"})
    assert r.status_code == 200 and r.json() == {"nfl": 1, "cfb": 0}
    assert await count(session) == 1
