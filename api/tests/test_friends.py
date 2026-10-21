import uuid

import pytest

from sqlalchemy import select

from app import friends
from app.models import Friendship
from test_auth import SIGN_UP, code, gql, su

SEND = "mutation($h:String!){sendFriendRequest(handle:$h)}"
RESPOND = "mutation($i:ID!,$a:Boolean!){respondToFriendRequest(id:$i,accept:$a)}"
REMOVE = "mutation($u:ID!){removeFriend(userId:$u)}"
FRIENDS = "{ friends { id handle } }"
PENDING = "{ pendingRequests { id from { handle } } }"


async def make_user(client, handle):
    _, b = await gql(client, SIGN_UP, su(email=f"{handle}@x.com", handle=handle))
    d = b["data"]["signUp"]
    client.cookies.clear()
    return {"Authorization": f"Bearer {d['token']}"}, d["user"]["id"]


async def two(client):
    a, aid = await make_user(client, "josh")
    b, bid = await make_user(client, "maria")
    return a, aid, b, bid


async def test_request_and_accept_makes_friends(client, session):
    a, aid, b, bid = await two(client)
    _, r = await gql(client, SEND, {"h": "maria"}, a)
    assert "errors" not in r
    _, p = await gql(client, PENDING, headers=b)
    reqs = p["data"]["pendingRequests"]
    assert [x["from"]["handle"] for x in reqs] == ["josh"]
    _, ok = await gql(client, RESPOND, {"i": reqs[0]["id"], "a": True}, b)
    assert ok["data"]["respondToFriendRequest"] is True
    _, fa = await gql(client, FRIENDS, headers=a)
    _, fb = await gql(client, FRIENDS, headers=b)
    assert [f["handle"] for f in fa["data"]["friends"]] == ["maria"]
    assert [f["handle"] for f in fb["data"]["friends"]] == ["josh"]
    f = await session.scalar(select(Friendship))
    assert f.status == "accepted" and f.accepted_at is not None
    assert await friends.are_friends(session, uuid.UUID(aid), uuid.UUID(bid))


async def test_request_by_handle_is_case_insensitive(client):
    a, *_ = await two(client)
    _, r = await gql(client, SEND, {"h": "MARIA"}, a)
    assert "errors" not in r


async def test_cannot_request_self(client):
    a, *_ = await two(client)
    _, r = await gql(client, SEND, {"h": "josh"}, a)
    assert code(r) == "INVALID"


async def test_unknown_handle_not_found(client):
    a, *_ = await two(client)
    _, r = await gql(client, SEND, {"h": "nobody"}, a)
    assert code(r) == "NOT_FOUND"


async def test_duplicate_request_conflict(client):
    a, *_ = await two(client)
    await gql(client, SEND, {"h": "maria"}, a)
    _, r = await gql(client, SEND, {"h": "maria"}, a)
    assert code(r) == "CONFLICT"


async def test_reverse_request_auto_accepts(client, session):
    a, _, b, _ = await two(client)
    await gql(client, SEND, {"h": "maria"}, a)
    _, r = await gql(client, SEND, {"h": "josh"}, b)
    assert "errors" not in r
    f = await session.scalar(select(Friendship))
    assert f.status == "accepted" and f.accepted_at is not None
    _, again = await gql(client, SEND, {"h": "josh"}, b)
    assert code(again) == "CONFLICT"


async def test_only_addressee_can_respond(client):
    a, _, b, _ = await two(client)
    await gql(client, SEND, {"h": "maria"}, a)
    _, p = await gql(client, PENDING, headers=b)
    fid = p["data"]["pendingRequests"][0]["id"]
    _, r = await gql(client, RESPOND, {"i": fid, "a": True}, a)
    assert code(r) == "FORBIDDEN"
    _, r = await gql(client, RESPOND, {"i": "00000000-0000-0000-0000-000000000000", "a": True}, b)
    assert code(r) == "NOT_FOUND"


async def test_decline_deletes_request(client, session):
    a, _, b, _ = await two(client)
    await gql(client, SEND, {"h": "maria"}, a)
    _, p = await gql(client, PENDING, headers=b)
    await gql(client, RESPOND, {"i": p["data"]["pendingRequests"][0]["id"], "a": False}, b)
    assert await session.scalar(select(Friendship)) is None


async def test_remove_friend(client, session):
    a, _, b, bid = await two(client)
    _, nf = await gql(client, REMOVE, {"u": bid}, a)
    assert code(nf) == "NOT_FOUND"
    await gql(client, SEND, {"h": "maria"}, a)
    _, p = await gql(client, PENDING, headers=b)
    await gql(client, RESPOND, {"i": p["data"]["pendingRequests"][0]["id"], "a": True}, b)
    _, r = await gql(client, REMOVE, {"u": bid}, a)
    assert r["data"]["removeFriend"] is True
    assert await session.scalar(select(Friendship)) is None


async def test_concurrent_send_race_is_conflict(client, session, monkeypatch):
    a, aid, b, bid = await two(client)
    await gql(client, SEND, {"h": "josh"}, b)  # reverse row exists, but the pre-check will miss it
    real, calls = session.scalar, []

    async def blind(stmt, *args, **kw):
        calls.append(1)
        return None if len(calls) == 2 else await real(stmt, *args, **kw)

    monkeypatch.setattr(session, "scalar", blind)
    _, r = await gql(client, SEND, {"h": "maria"}, a)
    assert code(r) == "CONFLICT"
    assert len(calls) == 2


@pytest.mark.parametrize(
    "query,vars",
    [
        (SEND, {"h": "maria"}),
        (RESPOND, {"i": "00000000-0000-0000-0000-000000000000", "a": True}),
        (REMOVE, {"u": "00000000-0000-0000-0000-000000000000"}),
        (FRIENDS, None),
        (PENDING, None),
    ],
)
async def test_requires_login(client, query, vars):
    _, r = await gql(client, query, vars)
    assert code(r) == "UNAUTHENTICATED"


async def test_friends_page_query_resolves_sibling_fields(client):
    # web/src/routes/friends asks for both in one query; sibling resolvers share one AsyncSession
    a, aid, b, bid = await two(client)
    await gql(client, SEND, {"h": "maria"}, a)
    _, r = await gql(client, "{ friends { id handle } pendingRequests { id from { id handle } } }", headers=b)
    assert "errors" not in r, r
    assert [x["from"]["handle"] for x in r["data"]["pendingRequests"]] == ["josh"]
