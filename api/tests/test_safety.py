import uuid

import httpx
import pytest
from sqlalchemy import func, select

from app import friends
from app.config import Settings
from app.db import get_session
from app.main import MAX_BODY, create_app
from app.models import Block, Friendship
from conftest import TEST_DATABASE_URL, TEST_SECRET
from test_auth import CHANGE_HANDLE, code, gql, join, request_code, verify
from test_friends import FRIENDS, PENDING, RESPOND, SEND, make_user, two

BLOCK = "mutation($u: ID!) { blockUser(userId: $u) }"
# the exact string web/src/routes/friends sends
PAGE = "{ friends { id handle } pendingRequests { id from { id handle } } sentRequests { id to { id handle } } }"


async def rows(session, model):
    return await session.scalar(select(func.count()).select_from(model))


async def test_block_removes_friendship_and_drops_later_requests_silently(client, session):
    a, aid, b, bid = await two(client)
    await gql(client, SEND, {"h": "maria"}, a)
    await gql(client, SEND, {"h": "josh"}, b)  # reverse request: now friends
    _, r = await gql(client, BLOCK, {"u": aid}, b)
    assert r["data"]["blockUser"] is True
    assert await rows(session, Friendship) == 0
    _, fa = await gql(client, FRIENDS, headers=a)
    assert fa["data"]["friends"] == []
    for _ in range(2):  # the blocked user can't tell: it "works" every time and nothing arrives
        _, r = await gql(client, SEND, {"h": "maria"}, a)
        assert r["data"]["sendFriendRequest"] is True
    assert await rows(session, Friendship) == 0
    _, p = await gql(client, PENDING, headers=b)
    assert p["data"]["pendingRequests"] == []


async def test_block_removes_a_pending_request_and_is_repeatable(client, session):
    a, aid, b, bid = await two(client)
    await gql(client, SEND, {"h": "maria"}, a)
    await gql(client, BLOCK, {"u": aid}, b)
    _, r = await gql(client, BLOCK, {"u": aid}, b)
    assert "errors" not in r and await rows(session, Friendship) == 0 and await rows(session, Block) == 1


async def test_block_rejects_self_unknown_and_anonymous(client):
    a, aid, b, bid = await two(client)
    assert code((await gql(client, BLOCK, {"u": aid}, a))[1]) == "INVALID"
    assert code((await gql(client, BLOCK, {"u": str(uuid.uuid4())}, a))[1]) == "NOT_FOUND"
    assert code((await gql(client, BLOCK, {"u": "nope"}, a))[1]) == "NOT_FOUND"
    assert code((await gql(client, BLOCK, {"u": bid}))[1]) == "UNAUTHENTICATED"


async def test_requesting_someone_you_blocked_unblocks_them(client, session):
    a, aid, b, bid = await two(client)
    await gql(client, BLOCK, {"u": aid}, b)
    await gql(client, SEND, {"h": "josh"}, b)
    assert await rows(session, Block) == 0
    _, p = await gql(client, PENDING, headers=a)
    assert [x["from"]["handle"] for x in p["data"]["pendingRequests"]] == ["maria"]


async def test_deleting_an_account_removes_its_blocks(client, session):
    a, aid, b, bid = await two(client)
    await gql(client, BLOCK, {"u": aid}, b)
    await gql(client, "mutation { deleteAccount }", headers=a)
    assert await rows(session, Block) == 0


async def test_pending_outgoing_requests_are_capped(client, monkeypatch):
    monkeypatch.setattr(friends, "MAX_PENDING", 2)
    a, _ = await make_user(client, "josh")
    for h in ("maria", "lee", "sam"):
        await make_user(client, h)
    for h in ("maria", "lee"):
        assert "errors" not in (await gql(client, SEND, {"h": h}, a))[1]
    assert code((await gql(client, SEND, {"h": "sam"}, a))[1]) == "RATE_LIMITED"


async def test_sender_sees_and_can_cancel_a_sent_request(client, session):
    a, aid, b, bid = await two(client)
    await gql(client, SEND, {"h": "maria"}, a)
    _, r = await gql(client, PAGE, headers=a)
    assert "errors" not in r, r
    sent = r["data"]["sentRequests"]
    assert [s["to"]["handle"] for s in sent] == ["maria"] and r["data"]["pendingRequests"] == []
    _, r = await gql(client, PAGE, headers=b)
    assert r["data"]["sentRequests"] == []
    _, r = await gql(client, RESPOND, {"i": sent[0]["id"], "a": False}, a)
    assert r["data"]["respondToFriendRequest"] is True and await rows(session, Friendship) == 0


async def test_a_third_user_cannot_cancel_someone_elses_request(client):
    a, aid, b, bid = await two(client)
    c, _ = await make_user(client, "lee")
    await gql(client, SEND, {"h": "maria"}, a)
    fid = (await gql(client, PAGE, headers=a))[1]["data"]["sentRequests"][0]["id"]
    assert code((await gql(client, RESPOND, {"i": fid, "a": False}, c))[1]) == "FORBIDDEN"


@pytest.mark.parametrize("handle", ["admin", "Support", "pickems", "xx_fuck_xx"])
async def test_reserved_and_offensive_handles_are_refused(client, handle):
    c = await request_code(client)
    assert code((await verify(client, c=c, handle=handle))[1]) == "INVALID"
    _, ok = await verify(client, c=c, handle="josh")  # the code survives the refusal
    assert "errors" not in ok
    assert code((await gql(client, CHANGE_HANDLE, {"handle": handle}))[1]) == "INVALID"


async def test_too_many_aliases_rejected(client):
    q = "{" + " ".join(f"a{i}: me {{ id }}" for i in range(30)) + "}"
    r = await client.post("/graphql", json={"query": q})
    assert "errors" in r.json() and "data" not in {k for k, v in r.json().items() if v}


async def test_oversized_body_rejected(client):
    r = await client.post("/graphql", json={"query": "{ me { id } } #" + "x" * MAX_BODY})
    assert r.status_code == 413 and r.json()["errors"][0]["extensions"]["code"] == "INVALID"


async def test_introspection_is_off_in_production_only(client, session, clock):
    q = "{ __schema { types { name } } }"
    assert "errors" not in (await client.post("/graphql", json={"query": q})).json()
    settings = Settings(database_url=TEST_DATABASE_URL, session_secret=TEST_SECRET,
                        sync_secret="test-sync-secret-0123456789", cookie_secure=True)
    app = create_app(settings, clock)

    async def _session():
        yield session

    app.dependency_overrides[get_session] = _session
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as prod:
        body = (await prod.post("/graphql", json={"query": q})).json()
        assert "errors" in body and not body.get("data")
        assert (await prod.post("/graphql", json={"query": "{ me { id } }"})).json() == {"data": {"me": None}}
