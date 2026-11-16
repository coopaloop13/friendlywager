import logging
import uuid
from datetime import timedelta

from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock
from app.errors import Invalid
from app.models import DeviceToken, Game, Pick, User
from app.notify import Notifier

log = logging.getLogger(__name__)
WINDOW = timedelta(hours=1)  # remind when an unpicked game locks this soon
QUIET = timedelta(hours=12)  # then leave the user alone: at most one reminder per slate


async def register_device(session: AsyncSession, user_id: uuid.UUID, token: str, platform: str) -> None:
    if platform not in ("ios", "android") or not 0 < len(token) <= 4096:
        raise Invalid("Invalid device")
    row = insert(DeviceToken).values(token=token, user_id=user_id, platform=platform)
    await session.execute(
        row.on_conflict_do_update(index_elements=["token"], set_={"user_id": user_id, "platform": platform})
    )


async def unregister_device(session: AsyncSession, user_id: uuid.UUID, token: str) -> None:
    await session.execute(delete(DeviceToken).where(DeviceToken.token == token, DeviceToken.user_id == user_id))


async def send_reminders(session: AsyncSession, notifier: Notifier, clock: Clock) -> int:
    """Push "picks lock soon" to every user with a device and an unpicked game about to kick off."""
    now = clock.now()
    soon = list(await session.scalars(
        select(Game.id).where(Game.status == "scheduled", Game.kickoff_at > now, Game.kickoff_at <= now + WINDOW)
    ))
    if not soon:
        return 0
    picked = select(func.count()).where(Pick.user_id == User.id, Pick.game_id.in_(soon)).scalar_subquery()
    # ponytail: every league, no opt-out; add a per-league setting when someone asks to mute one
    rows = await session.execute(
        select(User, func.array_agg(DeviceToken.token), picked)
        .join(DeviceToken, DeviceToken.user_id == User.id)
        .where(or_(User.reminded_at.is_(None), User.reminded_at < now - QUIET))
        .group_by(User.id)
    )
    sent = 0
    for user, tokens, n_picked in rows.all():
        owed = len(soon) - n_picked
        if owed <= 0:
            continue
        what = "1 game locks" if owed == 1 else f"{owed} games lock"
        try:
            dead = await notifier.send(tokens, "Picks lock soon", f"{what} within the hour. Get your picks in.")
        except Exception:  # one bad push must not stop the rest; this user is tried again next run
            log.exception("reminder failed for user %s", user.id)
            continue
        user.reminded_at = now
        if dead:
            await session.execute(delete(DeviceToken).where(DeviceToken.token.in_(dead)))
        sent += 1
    return sent
