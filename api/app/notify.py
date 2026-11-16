import logging
from typing import Protocol

from fastapi import Request

log = logging.getLogger("uvicorn.error")


class Notifier(Protocol):
    async def send(self, tokens: list[str], title: str, body: str) -> list[str]:
        """Push one message to these devices. Returns the tokens the push service says no longer exist."""
        ...


class LogNotifier:
    """Writes the push to the server log instead of sending it."""

    async def send(self, tokens: list[str], title: str, body: str) -> list[str]:
        log.warning("PUSH NOT SENT (no provider configured) devices=%d title=%r body=%r", len(tokens), title, body)
        return []


def get_notifier(request: Request) -> Notifier:
    # ponytail: no real sender until there is a Firebase project; add an FcmNotifier here, chosen by settings
    return LogNotifier()
