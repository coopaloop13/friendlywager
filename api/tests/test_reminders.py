from datetime import timedelta

from sqlalchemy import event, select, update

from app.models import DeviceToken, Game
from app.notify import get_notifier
from app.reminders import send_reminders
from test_auth import code, gql
from test_friends import make_user
from test_picks import SAVE, mkgame, now  # noqa: F401  (now is a fixture)
from test_sync import FakeClient, pl

# the exact strings web/src/lib/push.ts sends
REGISTER = "mutation($token: String!, $platform: String!) { registerDevice(token: $token, platform: $platform) }"
UNREGISTER = "mutation($token: String!) { unregisterDevice(token: $token) }"


class FakeNotifier:
    def __init__(self, dead=()):
        self.sent, self.dead = [], set(dead)

    async def send(self, tokens, title, body):
        self.sent.append((sorted(tokens), title, body))
        return [t for t in tokens if t in self.dead]


async def device(client, handle="josh", token="tok-josh", platform="ios"):
    h, _ = await make_user(client, handle)
    _, r = await gql(client, REGISTER, {"token": token, "platform": platform}, h)
    assert r["data"]["registerDevice"] is True, r
    return h


async def run(session, clock, notifier=None):
    notifier = notifier or FakeNotifier()
    n = await send_reminders(session, notifier, clock)
    await session.commit()
    return n, notifier


async def test_register_needs_login_and_a_known_platform(client):
    assert code((await gql(client, REGISTER, {"token": "t", "platform": "ios"}))[1]) == "UNAUTHENTICATED"
    h, _ = await make_user(client, "josh")
    assert code((await gql(client, REGISTER, {"token": "t", "platform": "windows"}, h))[1]) == "INVALID"
    assert code((await gql(client, REGISTER, {"token": "", "platform": "ios"}, h))[1]) == "INVALID"


async def test_a_device_belongs_to_whoever_signed_in_on_it_last(client, session):
    await device(client, "josh", "phone")
    b = await device(client, "maria", "phone", "android")
    rows = (await session.scalars(select(DeviceToken))).all()
    assert len(rows) == 1 and rows[0].platform == "android"
    _, r = await gql(client, UNREGISTER, {"token": "phone"}, b)
    assert r["data"]["unregisterDevice"] is True
    assert (await session.scalars(select(DeviceToken))).all() == []


async def test_reminds_once_when_an_unpicked_game_locks_within_the_hour(client, session, clock, now):
    await device(client)
    await mkgame(session, now + timedelta(minutes=30))
    await mkgame(session, now + timedelta(minutes=45), ext="2")
    n, notifier = await run(session, clock)
    assert n == 1
    tokens, title, body = notifier.sent[0]
    assert tokens == ["tok-josh"] and title and "2 games" in body
    assert (await run(session, clock))[0] == 0  # the cron runs every 5 minutes; one reminder is enough


async def test_reminds_again_for_a_later_slate(client, session, clock, now):
    await device(client)
    await mkgame(session, now + timedelta(minutes=30))
    await run(session, clock)
    clock.dt = now + timedelta(days=3)
    await mkgame(session, clock.dt + timedelta(minutes=10), ext="2")
    n, notifier = await run(session, clock)
    assert n == 1 and "1 game " in notifier.sent[0][2]


async def test_no_reminder_when_nothing_is_owed(client, session, clock, now):
    h = await device(client)
    await make_user(client, "maria")  # no device
    picked = await mkgame(session, now + timedelta(minutes=30))
    await mkgame(session, now + timedelta(hours=3), ext="later")
    await mkgame(session, now - timedelta(minutes=5), ext="started")
    off = await mkgame(session, now + timedelta(minutes=20), ext="off")
    await session.execute(update(Game).where(Game.id == off.id).values(status="postponed"))
    await session.commit()
    await gql(client, SAVE, {"g": str(picked.id), "h": 24, "a": 17}, h)
    n, notifier = await run(session, clock)
    assert n == 0 and notifier.sent == []


async def test_tokens_the_push_service_rejects_are_dropped(client, session, clock, now):
    h = await device(client)
    await gql(client, REGISTER, {"token": "old-phone", "platform": "ios"}, h)
    await mkgame(session, now + timedelta(minutes=30))
    _, notifier = await run(session, clock, FakeNotifier(dead={"old-phone"}))
    assert notifier.sent[0][0] == ["old-phone", "tok-josh"]
    assert [d.token for d in (await session.scalars(select(DeviceToken))).all()] == ["tok-josh"]


def count_deletes(session) -> list[str]:
    """Collects every DELETE sent from here on; the cron must not send one per user."""
    seen: list[str] = []
    event.listen(
        session.bind.sync_engine, "before_cursor_execute",
        lambda *a: seen.append(a[2]) if a[2].startswith("DELETE") else None,
    )
    return seen


async def test_rejected_tokens_are_dropped_in_one_statement_however_many_users(client, session, clock, now):
    for handle in ("josh", "maria", "bob"):
        await device(client, handle, f"old-{handle}")
    await mkgame(session, now + timedelta(minutes=30))
    deletes = count_deletes(session)
    n, _ = await run(session, clock, FakeNotifier(dead={"old-josh", "old-maria", "old-bob"}))
    assert n == 3
    assert len(deletes) == 1, deletes
    assert (await session.scalars(select(DeviceToken))).all() == []


async def test_deleting_the_account_removes_its_devices(client, session):
    h = await device(client)
    await gql(client, "mutation { deleteAccount }", headers=h)
    assert (await session.scalars(select(DeviceToken))).all() == []


async def test_the_sync_cron_sends_reminders_and_survives_a_push_failure(client, session, clock, now):
    from app.sync.espn import get_scoreboard_client

    await device(client)
    await mkgame(session, now + timedelta(minutes=30))
    notifier = FakeNotifier()
    app = client._transport.app
    app.dependency_overrides[get_scoreboard_client] = lambda: FakeClient(pl(1, type=4))
    app.dependency_overrides[get_notifier] = lambda: notifier
    secret = {"X-Sync-Secret": "test-sync-secret-0123456789"}
    r = await client.post("/internal/sync", headers=secret)
    assert r.status_code == 200 and len(notifier.sent) == 1

    class Broken:
        async def send(self, *a):
            raise RuntimeError("push service down")

    clock.dt = now + timedelta(days=3)
    await mkgame(session, clock.dt + timedelta(minutes=10), ext="2")
    app.dependency_overrides[get_notifier] = lambda: Broken()
    r = await client.post("/internal/sync", headers=secret)
    assert r.status_code == 200 and r.json() == {"nfl": 0, "cfb": 0}  # scores still sync


async def test_the_app_shell_may_call_the_api_cross_origin(client):
    pre = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization,content-type"}
    for origin in ("capacitor://localhost", "https://localhost"):
        r = await client.options("/graphql", headers={"Origin": origin, **pre})
        assert r.status_code == 200 and r.headers["access-control-allow-origin"] == origin
        assert "authorization" in r.headers["access-control-allow-headers"].lower()
        assert "access-control-allow-credentials" not in r.headers  # bearer token only, never the cookie
    r = await client.options("/graphql", headers={"Origin": "https://evil.example", **pre})
    assert "access-control-allow-origin" not in r.headers
