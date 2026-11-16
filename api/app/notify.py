import json
import logging
import time
from functools import lru_cache
from typing import Protocol

import httpx
import jwt
from fastapi import Request

from app.config import Settings

log = logging.getLogger("uvicorn.error")
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


class Notifier(Protocol):
    async def send(self, tokens: list[str], title: str, body: str) -> list[str]:
        """Push one message to these devices. Returns the tokens the push service says no longer exist."""
        ...


class LogNotifier:
    """Writes the push to the server log instead of sending it."""

    async def send(self, tokens: list[str], title: str, body: str) -> list[str]:
        log.warning("PUSH NOT SENT (no provider configured) devices=%d title=%r body=%r", len(tokens), title, body)
        return []


class FcmNotifier:
    """Firebase Cloud Messaging (HTTP v1), which delivers to both iOS and Android."""

    def __init__(self, service_account_json: str, transport: httpx.AsyncBaseTransport | None = None):
        self.account, self.transport = json.loads(service_account_json), transport
        self.url = f"https://fcm.googleapis.com/v1/projects/{self.account['project_id']}/messages:send"
        self._access, self._expires = "", 0.0

    async def _access_token(self, http: httpx.AsyncClient) -> str:
        if time.time() > self._expires - 60:
            now = int(time.time())
            claims = {"iss": self.account["client_email"], "scope": SCOPE, "aud": TOKEN_URL, "iat": now, "exp": now + 3600}
            assertion = jwt.encode(claims, self.account["private_key"], algorithm="RS256")
            r = await http.post(
                TOKEN_URL, data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion}
            )
            r.raise_for_status()
            self._access, self._expires = r.json()["access_token"], time.time() + r.json()["expires_in"]
        return self._access

    async def send(self, tokens: list[str], title: str, body: str) -> list[str]:
        dead = []
        async with httpx.AsyncClient(timeout=15, transport=self.transport) as http:
            headers = {"Authorization": f"Bearer {await self._access_token(http)}"}
            # ponytail: one request per device, in turn; fine for a handful of phones per user
            for token in tokens:
                message = {"message": {"token": token, "notification": {"title": title, "body": body}}}
                r = await http.post(self.url, json=message, headers=headers)
                if r.status_code == 404 or "UNREGISTERED" in r.text:
                    dead.append(token)
                elif r.status_code != 200:
                    log.error("push refused: %s %s", r.status_code, r.text[:300])
        return dead


@lru_cache(maxsize=1)  # one sender per process, so the Google access token is reused across cron runs
def _fcm(service_account_json: str) -> FcmNotifier:
    return FcmNotifier(service_account_json)


def notifier_for(settings: Settings) -> Notifier:
    return _fcm(settings.fcm_service_account) if settings.fcm_service_account else LogNotifier()


def get_notifier(request: Request) -> Notifier:
    return notifier_for(request.app.state.settings)
