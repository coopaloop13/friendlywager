import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import Clock
from app.email import EmailSender
from app.errors import Conflict, HandleRequired, Invalid, RateLimited, Unauthenticated
from app.models import LoginCode, User

# ponytail: stateless JWT, no server-side revocation; add a sessions table if logout-everywhere is needed
SESSION_DAYS = 30
CODE_MINUTES = 10
RESEND_SECONDS = 60
MAX_ATTEMPTS = 5  # also a CHECK on login_codes.attempts
_ph = PasswordHasher()
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_HANDLE = re.compile(r"^[a-z0-9_]{3,20}$")
# Handles are the only text users write, so this short list is all the moderation there is.
# Checked at sign-up and rename only; nobody who already has a handle is affected.
_RESERVED = frozenset(
    "admin administrator anonymous deleted everyone friendlywager help here mod moderator null official "
    "pickem pickems root sportspicks staff support system undefined".split()
)
_BANNED = ("cunt", "faggot", "fuck", "hitler", "nazi", "nigg", "retard", "shit")


def issue_token(user_id: uuid.UUID, secret: str) -> str:
    exp = datetime.now(UTC) + timedelta(days=SESSION_DAYS)
    return jwt.encode({"sub": str(user_id), "exp": exp}, secret, algorithm="HS256")


def read_token(token: str, secret: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(jwt.decode(token, secret, algorithms=["HS256"])["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def _handle(raw: str) -> str:
    handle = raw.strip().lower()
    if not _HANDLE.match(handle):
        raise Invalid("Handle must be 3-20 characters: a-z, 0-9, _")
    if handle in _RESERVED or any(b in handle for b in _BANNED):
        raise Invalid("That handle isn't available")
    return handle


async def request_login_code(session: AsyncSession, sender: EmailSender, clock: Clock, *, email: str) -> None:
    """Store a fresh code for the email (replacing any earlier one) and send it. Same for known and new emails."""
    email = email.strip().lower()
    if not _EMAIL.match(email):
        raise Invalid("Invalid email")
    now = clock.now()
    # ponytail: one code a minute per email, no table of sends; per-IP limits live at the edge
    last = await session.get(LoginCode, email, with_for_update=True, populate_existing=True)
    if last and last.expires_at - timedelta(minutes=CODE_MINUTES) > now - timedelta(seconds=RESEND_SECONDS):
        raise RateLimited("We just sent a code. Give it a minute before asking for another.")
    code = f"{secrets.randbelow(10**6):06d}"
    row = insert(LoginCode).values(
        email=email, code_hash=_ph.hash(code), expires_at=now + timedelta(minutes=CODE_MINUTES), attempts=0
    )
    await session.execute(
        row.on_conflict_do_update(
            index_elements=["email"], set_={c: row.excluded[c] for c in ("code_hash", "expires_at", "attempts")}
        )
    )
    await sender.send(
        email,
        f"{code} is your Pick'ems sign-in code",
        f"Your Pick'ems sign-in code is {code}\n\nIt expires in {CODE_MINUTES} minutes. "
        "If you didn't ask for it, ignore this email.",
    )


async def verify_login_code(
    session: AsyncSession, clock: Clock, *, email: str, code: str, handle: str | None = None
) -> User:
    """Sign in with an emailed code. A new email also needs a handle; until it has one the code stays usable."""
    email = email.strip().lower()
    bad = Unauthenticated("Invalid or expired code")
    row = await session.get(LoginCode, email, with_for_update=True, populate_existing=True)
    if row is None or row.expires_at <= clock.now() or row.attempts >= MAX_ATTEMPTS:
        raise bad
    try:
        _ph.verify(row.code_hash, code.strip())
    except (VerifyMismatchError, InvalidHashError):
        row.attempts += 1
        await session.commit()  # the caller rolls back on errors, and this count must survive
        raise bad from None

    user = await session.scalar(select(User).where(User.email == email))
    if user is None:
        if handle is None:
            raise HandleRequired("Pick a handle to finish signing up")
        user = User(email=email, handle=_handle(handle))
        try:
            async with session.begin_nested():  # a taken handle must not lose the row lock or the code
                session.add(user)
        except IntegrityError as e:
            raise Conflict("Handle already taken") from e
    await session.delete(row)
    return user


async def change_handle(session: AsyncSession, user_id: uuid.UUID, handle: str) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise Unauthenticated("Log in required")
    user.handle = _handle(handle)
    try:
        await session.flush()  # DB unique constraint is the source of truth
    except IntegrityError as e:
        raise Conflict("Handle already taken") from e
    return user


async def delete_account(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Remove the user for good. Their picks and friendships go with them (ON DELETE CASCADE)."""
    user = await session.get(User, user_id)
    if user is None:
        raise Unauthenticated("Log in required")
    await session.execute(delete(LoginCode).where(LoginCode.email == user.email))
    await session.delete(user)
