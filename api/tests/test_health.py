async def test_health_ok(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


async def test_health_503_when_a_league_sync_is_stale(client, session, clock):
    from datetime import timedelta

    from app.models import LeagueState

    session.add(LeagueState(league="nfl", season=2026, season_type=2, week=6,
                            last_synced_at=clock.now() - timedelta(minutes=89)))
    session.add(LeagueState(league="cfb", season=2026, season_type=2, week=8,
                            last_synced_at=clock.now() - timedelta(minutes=91)))
    await session.flush()
    r = await client.get("/health")
    assert r.status_code == 503 and r.json() == {"ok": False, "stale": ["cfb"]}


async def test_no_graphiql_when_secure(session):
    import httpx

    from app.config import Settings
    from app.main import create_app

    app = create_app(Settings(database_url="x", session_secret="s" * 32,
                              sync_secret="s" * 16, cookie_secure=True))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/graphql", headers={"Accept": "text/html"})
    assert "graphiql" not in r.text.lower() and "<html" not in r.text.lower()


async def test_graphiql_in_dev(client):
    r = await client.get("/graphql", headers={"Accept": "text/html"})
    assert "graphiql" in r.text.lower()
