import json

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import Settings
from app.notify import FcmNotifier, LogNotifier, notifier_for

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
ACCOUNT = json.dumps({
    "project_id": "proj",
    "client_email": "push@proj.iam.gserviceaccount.com",
    "private_key": KEY.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode(),
})


def fcm(replies, seen):
    """replies: device token -> (status, body). Anything not listed is delivered."""

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "ya29.test", "expires_in": 3600})
        token = json.loads(request.content)["message"]["token"]
        status, body = replies.get(token, (200, {"name": "projects/proj/messages/1"}))
        return httpx.Response(status, json=body)

    return FcmNotifier(ACCOUNT, httpx.MockTransport(handler))


async def test_sends_one_message_per_device_with_a_google_access_token():
    seen = []
    n = fcm({}, seen)
    assert await n.send(["a", "b"], "Picks lock soon", "2 games lock within the hour.") == []
    auth, *sends = seen
    assertion = dict(x.split("=") for x in auth.content.decode().split("&"))["assertion"]
    claims = jwt.decode(assertion, KEY.public_key(), algorithms=["RS256"], audience="https://oauth2.googleapis.com/token")
    assert claims["iss"] == "push@proj.iam.gserviceaccount.com"
    assert claims["scope"] == "https://www.googleapis.com/auth/firebase.messaging"
    assert [str(r.url) for r in sends] == ["https://fcm.googleapis.com/v1/projects/proj/messages:send"] * 2
    assert all(r.headers["authorization"] == "Bearer ya29.test" for r in sends)
    assert json.loads(sends[0].content) == {
        "message": {"token": "a", "notification": {"title": "Picks lock soon", "body": "2 games lock within the hour."}}
    }


async def test_reports_only_unregistered_devices_as_dead():
    gone = {"error": {"status": "NOT_FOUND", "details": [{"errorCode": "UNREGISTERED"}]}}
    n = fcm({"gone": (404, gone), "flaky": (503, {"error": {"status": "UNAVAILABLE"}})}, [])
    assert await n.send(["ok", "gone", "flaky"], "t", "b") == ["gone"]


async def test_reuses_the_access_token_between_sends():
    seen = []
    n = fcm({}, seen)
    await n.send(["a"], "t", "b")
    await n.send(["a"], "t", "b")
    assert [r.url.host for r in seen].count("oauth2.googleapis.com") == 1


def test_real_sender_only_when_a_service_account_is_configured():
    base = dict(database_url="x", session_secret="s" * 32, sync_secret="s" * 16)
    assert isinstance(notifier_for(Settings(**base)), LogNotifier)
    assert isinstance(notifier_for(Settings(**base, fcm_service_account="")), LogNotifier)
    assert isinstance(notifier_for(Settings(**base, fcm_service_account=ACCOUNT)), FcmNotifier)
