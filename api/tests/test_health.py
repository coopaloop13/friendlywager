async def test_health_ok(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


async def test_no_graphiql_when_secure(session):
    import httpx

    from app.config import Settings
    from app.main import create_app

    app = create_app(Settings(database_url="x", session_secret="s" * 32, invite_code="invite-code",
                              sync_secret="s" * 16, cookie_secure=True))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/graphql", headers={"Accept": "text/html"})
    assert "graphiql" not in r.text.lower() and "<html" not in r.text.lower()


async def test_graphiql_in_dev(client):
    r = await client.get("/graphql", headers={"Accept": "text/html"})
    assert "graphiql" in r.text.lower()
