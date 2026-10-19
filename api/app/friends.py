import uuid

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock
from app.errors import Conflict, Forbidden, Invalid, NotFound
from app.models import Friendship, User


def _pair(a: uuid.UUID, b: uuid.UUID):
    return or_(
        and_(Friendship.requester_id == a, Friendship.addressee_id == b),
        and_(Friendship.requester_id == b, Friendship.addressee_id == a),
    )


async def send_request(session: AsyncSession, clock: Clock, me: uuid.UUID, handle: str) -> Friendship:
    other = await session.scalar(select(User).where(User.handle == handle.strip().lower()))
    if other is None:
        raise NotFound("No such user")
    if other.id == me:
        raise Invalid("You can't friend yourself")
    f = await session.scalar(select(Friendship).where(_pair(me, other.id)))
    if f is None:
        f = Friendship(requester_id=me, addressee_id=other.id, status="pending")
        try:
            async with session.begin_nested():  # savepoint: a lost race must not poison the outer transaction
                session.add(f)
                await session.flush()
        except IntegrityError as e:  # concurrent request for the same pair hit the unique index
            raise Conflict("Request already exists") from e
        return f
    elif f.status == "pending" and f.addressee_id == me:
        f.status, f.accepted_at = "accepted", clock.now()
    else:
        raise Conflict("Already friends" if f.status == "accepted" else "Request already sent")
    await session.flush()
    return f


async def respond(session: AsyncSession, clock: Clock, me: uuid.UUID, friendship_id: uuid.UUID, accept: bool) -> None:
    f = await session.get(Friendship, friendship_id)
    if f is None:
        raise NotFound("No such request")
    if f.addressee_id != me:
        raise Forbidden("Not your request")
    if f.status != "pending":
        raise Conflict("Already accepted")
    if accept:
        f.status, f.accepted_at = "accepted", clock.now()
    else:
        await session.delete(f)
    await session.flush()


async def remove(session: AsyncSession, me: uuid.UUID, friend_id: uuid.UUID) -> None:
    res = await session.execute(
        delete(Friendship).where(_pair(me, friend_id), Friendship.status == "accepted")
    )
    if res.rowcount == 0:
        raise NotFound("Not friends")


async def are_friends(session: AsyncSession, a: uuid.UUID, b: uuid.UUID) -> bool:
    return await session.scalar(
        select(Friendship.id).where(_pair(a, b), Friendship.status == "accepted")
    ) is not None


async def list_friends(session: AsyncSession, me: uuid.UUID) -> list[User]:
    other = or_(
        and_(Friendship.requester_id == me, User.id == Friendship.addressee_id),
        and_(Friendship.addressee_id == me, User.id == Friendship.requester_id),
    )
    q = select(User).join(Friendship, other).where(Friendship.status == "accepted").order_by(User.handle)
    return list((await session.scalars(q)).all())


async def pending_incoming(session: AsyncSession, me: uuid.UUID) -> list[tuple[Friendship, User]]:
    q = (
        select(Friendship, User)
        .join(User, User.id == Friendship.requester_id)
        .where(Friendship.addressee_id == me, Friendship.status == "pending")
        .order_by(Friendship.created_at)
    )
    return [(f, u) for f, u in (await session.execute(q)).all()]
