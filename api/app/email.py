import html
import logging
from typing import Protocol

import httpx
from fastapi import Request

from app.config import Settings
from app.errors import Invalid, Unavailable

log = logging.getLogger("uvicorn.error")


class EmailSender(Protocol):
    async def send(self, to: str, subject: str, text: str) -> None: ...


class LogEmailSender:
    """Development only: writes the message to the server log instead of sending it."""

    async def send(self, to: str, subject: str, text: str) -> None:
        log.warning("EMAIL NOT SENT (no provider configured) to=%s subject=%r text=%r", to, subject, text)


class CloudflareEmailSender:
    """Cloudflare Email Service over REST (the API runs in a container, so there is no Worker binding)."""

    def __init__(self, token: str, account_id: str, from_address: str, from_name: str,
                 transport: httpx.AsyncBaseTransport | None = None):
        self.token, self.from_address, self.from_name, self.transport = token, from_address, from_name, transport
        self.url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/email/sending/send"

    async def send(self, to: str, subject: str, text: str) -> None:
        body = {
            "to": to,
            "from": {"address": self.from_address, "name": self.from_name},
            "subject": subject,
            "text": text,
            "html": "<p>" + html.escape(text).replace("\n", "<br>") + "</p>",
        }
        try:
            async with httpx.AsyncClient(timeout=15, transport=self.transport) as http:
                r = await http.post(self.url, json=body, headers={"Authorization": f"Bearer {self.token}"})
            data = r.json() if r.status_code == 200 else {}
        except (httpx.HTTPError, ValueError):
            log.exception("email send failed")
            raise Unavailable("We couldn't send the email. Try again in a minute.") from None
        if not data.get("success"):
            log.error("email send refused: %s %s", r.status_code, r.text[:500])
            raise Unavailable("We couldn't send the email. Try again in a minute.")
        if to in (data.get("result") or {}).get("permanent_bounces", []):
            raise Invalid("That email address can't receive mail")


def sender_for(settings: Settings) -> EmailSender:
    if settings.email_api_token and settings.cloudflare_account_id:
        return CloudflareEmailSender(
            settings.email_api_token, settings.cloudflare_account_id, settings.email_from, settings.email_from_name
        )
    return LogEmailSender()


def get_email_sender(request: Request) -> EmailSender:
    return sender_for(request.app.state.settings)
