import re
import time
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.models import Friendship, Game, LoginCode, Pick, User
from conftest import TEST_SECRET

# the exact strings web/src/lib/account.ts sends
REQUEST = "mutation($email: String!) { requestLoginCode(email: $email) }"
VERIFY = ("mutation($email: String!, $code: String!, $handle: String) "
          "{ verifyLoginCode(email: $email, code: $code, handle: $handle) { token user { id handle } } }")
CHANGE_HANDLE = "mutation($handle: String!) { changeHandle(handle: $handle) { id handle } }"
DELETE_ACCOUNT = "mutation { deleteAccount }"
ME = "{ me { id handle } }"


async def gql(client, query, variables=None, headers=None):
    r = await client.post("/graphql", json={"query": query, "variables": variables}, headers=headers)
    assert r.status_code == 200, r.text
    return r, r.json()


def code(body):
    return body["errors"][0]["extensions"]["code"]


async def request_code(client, email="a@x.com") -> str:
    _, body = await gql(client, REQUEST, {"email": email})
    assert body["data"]["requestLoginCode"] is True, body
    return re.search(r"\b\d{6}\b", client.outbox[-1][2]).group()


async def verify(client, email="a@x.com", c="", handle=None):
    return await gql(client, VERIFY, {"email": email, "code": c, "handle": handle})


async def join(client, email="a@x.com", handle="josh"):
    """Request a code and sign in with it; creates the account when the email is new."""
    return await verify(client, email, await request_code(client, email), handle)


async def test_code_is_emailed_and_signs_a_new_user_up(client):
    c = await request_code(client, " A@X.com ")
    to, subject, text = client.outbox[-1]
    assert to == "a@x.com" and c in text and "10 minutes" in text and subject
    r, body = await verify(client, "A@X.com", c, "Josh")
    assert body["data"]["verifyLoginCode"]["user"]["handle"] == "josh"
    cookie = r.headers["set-cookie"]
    assert "fw_session=" in cookie and "HttpOnly" in cookie
    assert "samesite=lax" in cookie.lower() and "Max-Age=2592000" in cookie
    assert "Secure" not in cookie
    _, me = await gql(client, ME)  # httpx keeps the cookie jar
    assert me["data"]["me"]["handle"] == "josh"


async def test_existing_user_signs_in_without_a_handle(client, session):
    _, first = await join(client)
    client.cookies.clear()
    _, again = await verify(client, c=await request_code(client))
    assert again["data"]["verifyLoginCode"]["user"] == first["data"]["verifyLoginCode"]["user"]
    assert await session.scalar(select(func.count()).select_from(User)) == 1


async def test_user_from_the_password_era_signs_in_by_code(client, session):
    session.add(User(email="old@x.com", handle="oldtimer", password_hash="$argon2id$whatever"))
    await session.flush()
    _, body = await verify(client, "old@x.com", await request_code(client, "old@x.com"))
    assert body["data"]["verifyLoginCode"]["user"]["handle"] == "oldtimer"


async def test_new_email_is_asked_for_a_handle_and_the_code_survives(client):
    c = await request_code(client)
    _, body = await verify(client, c=c)
    assert code(body) == "HANDLE_REQUIRED"
    _, taken_or_bad = await verify(client, c=c, handle="a!")
    assert code(taken_or_bad) == "INVALID"
    _, ok = await verify(client, c=c, handle="josh")
    assert ok["data"]["verifyLoginCode"]["user"]["handle"] == "josh"


async def test_taken_handle_conflicts_and_another_handle_still_works(client):
    await join(client)
    client.cookies.clear()
    c = await request_code(client, "b@x.com")
    _, body = await verify(client, "b@x.com", c, "Josh")
    assert code(body) == "CONFLICT"
    _, ok = await verify(client, "b@x.com", c, "maria")
    assert ok["data"]["verifyLoginCode"]["user"]["handle"] == "maria"


async def test_wrong_code_and_no_code_look_the_same(client):
    c = await request_code(client)
    _, wrong = await verify(client, c="000000" if c != "000000" else "111111")
    _, none = await verify(client, "nobody@x.com", "123456")
    assert code(wrong) == code(none) == "UNAUTHENTICATED"
    assert wrong["errors"][0]["message"] == none["errors"][0]["message"]


async def test_code_locks_after_five_wrong_attempts(client, clock):
    c = await request_code(client)
    bad = "000000" if c != "000000" else "111111"
    for _ in range(5):
        _, body = await verify(client, c=bad, handle="josh")
        assert code(body) == "UNAUTHENTICATED"
    _, body = await verify(client, c=c, handle="josh")
    assert code(body) == "UNAUTHENTICATED"
    clock.dt += timedelta(seconds=61)
    _, ok = await verify(client, c=await request_code(client), handle="josh")  # a fresh code resets it
    assert ok["data"]["verifyLoginCode"]["user"]["handle"] == "josh"


async def test_code_expires_after_ten_minutes(client, clock):
    c = await request_code(client)
    clock.dt += timedelta(minutes=10, seconds=1)
    _, body = await verify(client, c=c, handle="josh")
    assert code(body) == "UNAUTHENTICATED"


async def test_code_is_single_use(client):
    c = await request_code(client)
    await verify(client, c=c, handle="josh")
    client.cookies.clear()
    _, body = await verify(client, c=c)
    assert code(body) == "UNAUTHENTICATED"


async def test_new_code_replaces_the_old_one(client, clock):
    old = await request_code(client)
    clock.dt += timedelta(seconds=61)
    new = await request_code(client)
    if old != new:
        _, body = await verify(client, c=old, handle="josh")
        assert code(body) == "UNAUTHENTICATED"
    _, ok = await verify(client, c=new, handle="josh")
    assert "errors" not in ok


async def test_second_request_within_a_minute_is_refused_and_keeps_the_first_code(client, clock):
    c = await request_code(client)
    clock.dt += timedelta(seconds=59)
    _, body = await gql(client, REQUEST, {"email": "A@x.com"})
    assert code(body) == "RATE_LIMITED" and len(client.outbox) == 1
    await request_code(client, "other@x.com")  # the wait is per email
    _, ok = await verify(client, c=c, handle="josh")
    assert "errors" not in ok


async def test_code_is_stored_hashed(client, session):
    c = await request_code(client)
    row = await session.scalar(select(LoginCode))
    assert row.email == "a@x.com" and c not in row.code_hash


async def test_request_rejects_a_malformed_email(client):
    _, body = await gql(client, REQUEST, {"email": "nope"})
    assert code(body) == "INVALID" and client.outbox == []


async def test_bearer_token_auth_works(client):
    _, body = await join(client)
    token = body["data"]["verifyLoginCode"]["token"]
    client.cookies.clear()
    _, anon = await gql(client, ME)
    assert anon["data"]["me"] is None
    _, me = await gql(client, ME, headers={"Authorization": f"Bearer {token}"})
    assert me["data"]["me"]["handle"] == "josh"


async def test_log_out_clears_cookie(client):
    await join(client)
    r, body = await gql(client, "mutation{logOut}")
    assert body["data"]["logOut"] is True
    assert "fw_session=" in r.headers["set-cookie"] and "Max-Age=0" in r.headers["set-cookie"]
    _, me = await gql(client, ME)
    assert me["data"]["me"] is None


async def test_change_handle(client):
    await join(client)
    _, body = await gql(client, CHANGE_HANDLE, {"handle": " Josh_2 "})
    assert body["data"]["changeHandle"]["handle"] == "josh_2"
    _, me = await gql(client, ME)
    assert me["data"]["me"]["handle"] == "josh_2"
    _, bad = await gql(client, CHANGE_HANDLE, {"handle": "no"})
    assert code(bad) == "INVALID"
    token = (await join(client, "b@x.com", "maria"))[1]["data"]["verifyLoginCode"]["token"]
    client.cookies.clear()
    _, taken = await gql(client, CHANGE_HANDLE, {"handle": "josh_2"}, {"Authorization": f"Bearer {token}"})
    assert code(taken) == "CONFLICT"
    _, anon = await gql(client, CHANGE_HANDLE, {"handle": "whoever"})
    assert code(anon) == "UNAUTHENTICATED"


async def test_delete_account_removes_the_user_their_picks_and_friendships(client, session):
    _, a = await join(client, "a@x.com", "josh")
    aid = a["data"]["verifyLoginCode"]["user"]["id"]
    token = a["data"]["verifyLoginCode"]["token"]
    _, b = await join(client, "b@x.com", "maria")
    bid = b["data"]["verifyLoginCode"]["user"]["id"]
    game = Game(league="nfl", season=2026, season_type=2, week=1, external_id="1", home_name="H", home_abbr="H",
                away_name="A", away_abbr="A", kickoff_at=datetime.now(UTC), status="scheduled")
    session.add(game)
    await session.flush()
    session.add_all([
        Pick(user_id=uuid.UUID(aid), game_id=game.id, pred_home=21, pred_away=17),
        Pick(user_id=uuid.UUID(bid), game_id=game.id, pred_home=10, pred_away=3),
        Friendship(requester_id=uuid.UUID(aid), addressee_id=uuid.UUID(bid), status="accepted"),
    ])
    await session.flush()
    await request_code(client, "a@x.com")  # a pending code must go too
    client.cookies.clear()
    auth = {"Authorization": f"Bearer {token}"}

    r, body = await gql(client, DELETE_ACCOUNT, headers=auth)
    assert body["data"]["deleteAccount"] is True and "Max-Age=0" in r.headers["set-cookie"]
    assert list(await session.scalars(select(User.handle))) == ["maria"]
    assert list(await session.scalars(select(Pick.pred_home))) == [10]  # the friend's own picks stay
    assert await session.scalar(select(func.count()).select_from(Friendship)) == 0
    assert await session.scalar(select(func.count()).select_from(LoginCode)) == 0
    _, me = await gql(client, ME, headers=auth)  # the old token no longer names anyone
    assert me["data"]["me"] is None
    _, anon = await gql(client, DELETE_ACCOUNT)
    assert code(anon) == "UNAUTHENTICATED"


# --- token security: every bad token means "not logged in" ---

def _bad_tokens(uid):
    claims = {"sub": str(uid), "exp": int(time.time()) + 3600}
    good = jwt.encode(claims, TEST_SECRET, algorithm="HS256")
    return {
        "expired": jwt.encode({**claims, "exp": int(time.time()) - 10}, TEST_SECRET, algorithm="HS256"),
        "wrong_secret": jwt.encode(claims, "x" * 40, algorithm="HS256"),
        "tampered": good[:-3] + ("AAA" if not good.endswith("AAA") else "BBB"),
        "alg_none": jwt.encode(claims, None, algorithm="none"),
        "garbage": "not-a-jwt",
    }


async def test_bad_tokens_are_unauthenticated(client):
    _, body = await join(client)
    uid = jwt.decode(body["data"]["verifyLoginCode"]["token"], TEST_SECRET, algorithms=["HS256"])["sub"]
    client.cookies.clear()
    for name, tok in _bad_tokens(uuid.UUID(uid)).items():
        for headers, cookies in (({"Authorization": f"Bearer {tok}"}, None), ({}, {"fw_session": tok})):
            client.cookies.clear()
            if cookies:
                client.cookies.update(cookies)
            _, me = await gql(client, ME, headers=headers)
            assert me["data"]["me"] is None, name


async def test_unexpected_errors_are_masked(client, session, monkeypatch):
    c = await request_code(client)

    async def boom():
        raise OperationalError("SELECT secret FROM pg", {}, Exception("driver detail"))

    monkeypatch.setattr(session, "commit", boom)
    r, body = await verify(client, c=c, handle="josh")
    assert body["errors"][0]["message"] == "Internal error"
    assert "secret" not in r.text and "driver" not in r.text
