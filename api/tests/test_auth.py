import time
import uuid

import jwt
from sqlalchemy.exc import OperationalError

from conftest import TEST_SECRET

SIGN_UP = """mutation($e:String!,$p:String!,$h:String!,$i:String!){
  signUp(email:$e,password:$p,handle:$h,inviteCode:$i){token user{id handle}}}"""
LOG_IN = "mutation($e:String!,$p:String!){logIn(email:$e,password:$p){token user{handle}}}"
ME = "{ me { id handle } }"


async def gql(client, query, variables=None, headers=None):
    r = await client.post("/graphql", json={"query": query, "variables": variables}, headers=headers)
    assert r.status_code == 200, r.text
    return r, r.json()


def su(email="a@x.com", handle="josh", invite="test-invite", pw="password1"):
    return {"e": email, "p": pw, "h": handle, "i": invite}


def code(body):
    return body["errors"][0]["extensions"]["code"]


async def test_sign_up_sets_cookie_and_me_works(client):
    r, body = await gql(client, SIGN_UP, su(email="A@X.com", handle="Josh"))
    assert body["data"]["signUp"]["user"]["handle"] == "josh"
    cookie = r.headers["set-cookie"]
    assert "fw_session=" in cookie and "HttpOnly" in cookie
    assert "samesite=lax" in cookie.lower() and "Max-Age=2592000" in cookie
    assert "Secure" not in cookie
    _, me = await gql(client, ME)  # httpx keeps the cookie jar
    assert me["data"]["me"]["handle"] == "josh"


async def test_sign_up_bad_invite_forbidden(client):
    _, body = await gql(client, SIGN_UP, su(invite="nope"))
    assert code(body) == "FORBIDDEN"


async def test_sign_up_invite_ignores_case_and_spaces(client):
    _, body = await gql(client, SIGN_UP, su(invite=" Test-Invite "))
    assert body["data"]["signUp"]["user"]["handle"] == "josh"


async def test_sign_up_duplicate_handle_any_case_conflict(client):
    await gql(client, SIGN_UP, su())
    _, body = await gql(client, SIGN_UP, su(email="b@x.com", handle="Josh"))
    assert code(body) == "CONFLICT"


async def test_sign_up_invalid_inputs(client):
    for kw in ({"pw": "short"}, {"handle": "a!"}, {"email": "nope"}):
        _, body = await gql(client, SIGN_UP, su(**kw))
        assert code(body) == "INVALID", kw


async def test_log_in_wrong_password_unauthenticated(client):
    await gql(client, SIGN_UP, su())
    _, bad = await gql(client, LOG_IN, {"e": "a@x.com", "p": "wrongpass1"})
    _, unknown = await gql(client, LOG_IN, {"e": "z@x.com", "p": "wrongpass1"})
    assert code(bad) == code(unknown) == "UNAUTHENTICATED"
    assert bad["errors"][0]["message"] == unknown["errors"][0]["message"]
    _, ok = await gql(client, LOG_IN, {"e": "A@x.com", "p": "password1"})
    assert ok["data"]["logIn"]["user"]["handle"] == "josh"


async def test_bearer_token_auth_works(client):
    _, body = await gql(client, SIGN_UP, su())
    token = body["data"]["signUp"]["token"]
    client.cookies.clear()
    _, anon = await gql(client, ME)
    assert anon["data"]["me"] is None
    _, me = await gql(client, ME, headers={"Authorization": f"Bearer {token}"})
    assert me["data"]["me"]["handle"] == "josh"


async def test_log_out_clears_cookie(client):
    await gql(client, SIGN_UP, su())
    r, body = await gql(client, "mutation{logOut}")
    assert body["data"]["logOut"] is True
    assert "fw_session=" in r.headers["set-cookie"] and "Max-Age=0" in r.headers["set-cookie"]
    _, me = await gql(client, ME)
    assert me["data"]["me"] is None


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
    _, body = await gql(client, SIGN_UP, su())
    uid = jwt.decode(body["data"]["signUp"]["token"], TEST_SECRET, algorithms=["HS256"])["sub"]
    client.cookies.clear()
    for name, tok in _bad_tokens(uuid.UUID(uid)).items():
        for headers, cookies in (({"Authorization": f"Bearer {tok}"}, None), ({}, {"fw_session": tok})):
            client.cookies.clear()
            if cookies:
                client.cookies.update(cookies)
            _, me = await gql(client, ME, headers=headers)
            assert me["data"]["me"] is None, name


async def test_unexpected_errors_are_masked(client, session, monkeypatch):
    async def boom():
        raise OperationalError("SELECT secret FROM pg", {}, Exception("driver detail"))

    monkeypatch.setattr(session, "commit", boom)
    r, body = await gql(client, SIGN_UP, su())
    assert body["errors"][0]["message"] == "Internal error"
    assert "secret" not in r.text and "driver" not in r.text
