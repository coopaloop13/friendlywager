import json

import httpx
import pytest

from app.config import Settings
from app.email import CloudflareEmailSender, LogEmailSender, sender_for
from app.errors import Invalid, Unavailable


def settings(**kw):
    return Settings(database_url="x", session_secret="s" * 32, sync_secret="s" * 16, **kw)


def cf(handler):
    return CloudflareEmailSender("tok", "acct", "signin@pickem.cc", "Pick'ems", httpx.MockTransport(handler))


async def test_cloudflare_sender_posts_the_message():
    seen = {}

    def handler(req: httpx.Request):
        seen.update(url=str(req.url), auth=req.headers["authorization"], body=json.loads(req.content))
        return httpx.Response(200, json={"success": True, "result": {"delivered": ["a@x.com"], "permanent_bounces": [], "queued": []}})

    await cf(handler).send("a@x.com", "123456 is your code", "Your code is 123456\n\nIt expires soon. <ok>")
    assert seen["url"] == "https://api.cloudflare.com/client/v4/accounts/acct/email/sending/send"
    assert seen["auth"] == "Bearer tok"
    b = seen["body"]
    assert b["to"] == "a@x.com" and b["subject"] == "123456 is your code"
    assert b["from"] == {"address": "signin@pickem.cc", "name": "Pick'ems"}
    assert b["text"].startswith("Your code is 123456") and "&lt;ok&gt;" in b["html"] and "<br>" in b["html"]


async def test_cloudflare_failure_is_a_plain_retry_message():
    for resp in (httpx.Response(500, text="boom secret"), httpx.Response(200, json={"success": False, "errors": [{"code": 1000, "message": "Sender domain not verified"}]})):
        with pytest.raises(Unavailable) as e:
            await cf(lambda req, r=resp: r).send("a@x.com", "s", "t")
        assert "secret" not in e.value.message and "verified" not in e.value.message


async def test_cloudflare_network_error_is_unavailable():
    def handler(req):
        raise httpx.ConnectError("no route")

    with pytest.raises(Unavailable):
        await cf(handler).send("a@x.com", "s", "t")


async def test_permanent_bounce_tells_the_user_the_address_is_bad():
    ok = httpx.Response(200, json={"success": True, "result": {"delivered": [], "permanent_bounces": ["a@x.com"], "queued": []}})
    with pytest.raises(Invalid):
        await cf(lambda req: ok).send("a@x.com", "s", "t")


def test_sender_is_cloudflare_only_when_configured():
    assert isinstance(sender_for(settings()), LogEmailSender)
    s = sender_for(settings(email_api_token="tok", cloudflare_account_id="acct"))
    assert isinstance(s, CloudflareEmailSender) and s.from_address == "signin@pickem.cc"
