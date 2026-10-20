import re
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import Conflict, Forbidden, Invalid, Unauthenticated
from app.models import User

# ponytail: stateless JWT, no server-side revocation; add a sessions table if logout-everywhere is needed
SESSION_DAYS = 30
_ph = PasswordHasher()
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_HANDLE = re.compile(r"^[a-z0-9_]{3,20}$")


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(hash: str, pw: str) -> bool:
    try:
        return _ph.verify(hash, pw)
    except (VerifyMismatchError, InvalidHashError):
        return False


def issue_token(user_id: uuid.UUID, secret: str) -> str:
    exp = datetime.now(UTC) + timedelta(days=SESSION_DAYS)
    return jwt.encode({"sub": str(user_id), "exp": exp}, secret, algorithm="HS256")


def read_token(token: str, secret: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(jwt.decode(token, secret, algorithms=["HS256"])["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


async def sign_up(
    session: AsyncSession, *, email: str, password: str, handle: str, invite_code: str, expected_invite: str
) -> User:
    if invite_code.strip().lower() != expected_invite.strip().lower():  # phones auto-capitalize
        raise Forbidden("Invalid invite code")
    email, handle = email.strip().lower(), handle.strip().lower()
    if len(password) < 8:
        raise Invalid("Password must be at least 8 characters")
    if not _EMAIL.match(email):
        raise Invalid("Invalid email")
    if not _HANDLE.match(handle):
        raise Invalid("Handle must be 3-20 characters: a-z, 0-9, _")
    taken = await session.scalar(select(User.id).where((User.email == email) | (User.handle == handle)))
    if taken:
        raise Conflict("Email or handle already taken")
    user = User(email=email, handle=handle, password_hash=hash_password(password))
    session.add(user)
    try:
        await session.flush()  # DB unique constraints are the source of truth
    except IntegrityError as e:
        raise Conflict("Email or handle already taken") from e
    return user


async def log_in(session: AsyncSession, *, email: str, password: str) -> User:
    user = await session.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or not verify_password(user.password_hash, password):
        raise Unauthenticated("Invalid email or password")
    return user
