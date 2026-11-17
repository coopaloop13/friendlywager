import logging
import uuid
from datetime import timedelta

from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock
from app.errors import Invalid
from app.models import DeviceToken, Friendship, Game, Pick, User
from app.notify import Notifier
from app.scoring import Score, game_points

log = logging.getLogger(__name__)
WINDOW = timedelta(hours=1)  # remind when an unpicked game locks this soon
QUIET = timedelta(hours=12)  # then leave the user alone: at most one reminder per slate
NAMED = 3  # friends spelled out in a result push; the rest are counted


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


async def send_results(session: AsyncSession, notifier: Notifier, clock: Clock) -> int:
    """Push each newly final game to the players who picked it: their points against each friend.

    Games that went final in the same run share one push per player. Each game is announced once.
    """
    finals = list(await session.scalars(
        select(Game).where(
            Game.status == "final", Game.home_score.is_not(None), Game.away_score.is_not(None),
            Game.result_pushed_at.is_(None),
        ).order_by(Game.kickoff_at, Game.id)
    ))
    if not finals:
        return 0
    # at most once: a game is marked even if a push below fails, so nobody is told twice
    for g in finals:
        g.result_pushed_at = clock.now()
    picks: dict[uuid.UUID, dict[uuid.UUID, Score]] = {}  # game -> player -> pick
    for p in await session.scalars(select(Pick).where(Pick.game_id.in_([g.id for g in finals]))):
        picks.setdefault(p.game_id, {})[p.user_id] = Score(p.pred_home, p.pred_away)
    players = {u for by_user in picks.values() for u in by_user}
    if not players:
        return 0
    tokens: dict[uuid.UUID, list[str]] = {}
    for d in await session.scalars(select(DeviceToken).where(DeviceToken.user_id.in_(players))):
        tokens.setdefault(d.user_id, []).append(d.token)
    friends: dict[uuid.UUID, set[uuid.UUID]] = {}
    pairs = await session.execute(
        select(Friendship.requester_id, Friendship.addressee_id).where(
            Friendship.status == "accepted",
            or_(Friendship.requester_id.in_(tokens), Friendship.addressee_id.in_(tokens)),
        )
    )
    for a, b in pairs.all():
        friends.setdefault(a, set()).add(b)
        friends.setdefault(b, set()).add(a)
    everyone = {f for u in tokens for f in friends.get(u, ())}
    handles = dict((await session.execute(select(User.id, User.handle).where(User.id.in_(everyone)))).all())

    sent = 0
    # ponytail: every final game, no opt-out; add a setting when someone asks to mute these
    for user, devices in tokens.items():
        mine = [g for g in finals if user in picks.get(g.id, {})]
        lines = []
        for friend in sorted(friends.get(user, ()), key=handles.__getitem__):
            a = b = 0
            for g in mine:
                pa, pb = game_points(Score(g.home_score, g.away_score), picks[g.id][user], picks[g.id].get(friend))
                a, b = a + pa, b + pb
            lines.append(f"You {a}, @{handles[friend]} {b}")
        if not lines:
            continue
        g = mine[0]
        title = f"{len(mine)} games final"
        if len(mine) == 1:
            title = f"Final: {g.away_abbr} {g.away_score}, {g.home_abbr} {g.home_score}"
        body = " · ".join(lines[:NAMED]) + (f" +{len(lines) - NAMED} more" if len(lines) > NAMED else "")
        try:
            dead = await notifier.send(devices, title, body)
        except Exception:  # one bad push must not stop the rest
            log.exception("result push failed for user %s", user)
            continue
        if dead:
            await session.execute(delete(DeviceToken).where(DeviceToken.token.in_(dead)))
        sent += 1
    return sent
