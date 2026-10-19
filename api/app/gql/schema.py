import inspect
import uuid
from dataclasses import dataclass

import strawberry
from fastapi import Depends, Request, Response
from graphql import GraphQLError
from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.extensions import MaskErrors, SchemaExtension
from strawberry.fastapi import BaseContext, GraphQLRouter
from strawberry.types import Info

from app import auth, friends
from app.clock import Clock
from app.config import Settings
from app.db import get_session
from app.errors import DomainError, NotFound, Unauthenticated
from app.models import User as UserModel

COOKIE = "fw_session"
COOKIE_MAX_AGE = auth.SESSION_DAYS * 24 * 3600


@dataclass
class Context(BaseContext):
    session: AsyncSession
    clock: Clock
    settings: Settings
    user_id: uuid.UUID | None
    response: Response


def require_user(ctx: Context) -> uuid.UUID:
    if ctx.user_id is None:
        raise Unauthenticated("Log in required")
    return ctx.user_id


async def get_context(
    request: Request, response: Response, session: AsyncSession = Depends(get_session)
) -> Context:
    settings: Settings = request.app.state.settings
    header = request.headers.get("authorization", "")
    token = header[7:] if header.lower().startswith("bearer ") else request.cookies.get(COOKIE)
    user_id = auth.read_token(token, settings.session_secret) if token else None
    return Context(session, request.app.state.clock, settings, user_id, response)


class DomainErrors(SchemaExtension):
    """DomainError -> GraphQL error with extensions.code; always roll back leftovers after the operation."""

    async def resolve(self, _next, root, info, *args, **kwargs):
        try:
            result = _next(root, info, *args, **kwargs)
            return await result if inspect.isawaitable(result) else result
        except DomainError as e:
            raise GraphQLError(e.message, extensions={"code": e.code}) from e

    async def on_operation(self):
        yield
        # mutations commit themselves; this discards anything uncommitted (e.g. after an error)
        await self.execution_context.context.session.rollback()


@strawberry.type
class User:
    id: strawberry.ID
    handle: str


@strawberry.type
class FriendRequest:
    id: strawberry.ID
    from_: User = strawberry.field(name="from")


@strawberry.type
class AuthPayload:
    user: User
    token: str


def _to_user(u: UserModel) -> User:
    return User(id=strawberry.ID(str(u.id)), handle=u.handle)


def _start_session(ctx: Context, u: UserModel) -> AuthPayload:
    token = auth.issue_token(u.id, ctx.settings.session_secret)
    ctx.response.set_cookie(
        COOKIE, token, max_age=COOKIE_MAX_AGE, httponly=True, samesite="lax", secure=ctx.settings.cookie_secure
    )
    return AuthPayload(user=_to_user(u), token=token)


@strawberry.type
class Query:
    @strawberry.field
    async def me(self, info: Info[Context, None]) -> User | None:
        ctx = info.context
        if ctx.user_id is None:
            return None
        u = await ctx.session.get(UserModel, ctx.user_id)
        return _to_user(u) if u else None

    @strawberry.field
    async def friends(self, info: Info[Context, None]) -> list[User]:
        ctx = info.context
        return [_to_user(u) for u in await friends.list_friends(ctx.session, require_user(ctx))]

    @strawberry.field
    async def pending_requests(self, info: Info[Context, None]) -> list[FriendRequest]:
        ctx = info.context
        rows = await friends.pending_incoming(ctx.session, require_user(ctx))
        return [FriendRequest(id=strawberry.ID(str(f.id)), from_=_to_user(u)) for f, u in rows]


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def sign_up(
        self, info: Info[Context, None], email: str, password: str, handle: str, invite_code: str
    ) -> AuthPayload:
        ctx = info.context
        u = await auth.sign_up(
            ctx.session,
            email=email,
            password=password,
            handle=handle,
            invite_code=invite_code,
            expected_invite=ctx.settings.invite_code,
        )
        await ctx.session.commit()
        return _start_session(ctx, u)

    @strawberry.mutation
    async def log_in(self, info: Info[Context, None], email: str, password: str) -> AuthPayload:
        ctx = info.context
        return _start_session(ctx, await auth.log_in(ctx.session, email=email, password=password))

    @strawberry.mutation
    async def log_out(self, info: Info[Context, None]) -> bool:
        info.context.response.delete_cookie(COOKIE, httponly=True, samesite="lax")
        return True

    @strawberry.mutation
    async def send_friend_request(self, info: Info[Context, None], handle: str) -> bool:
        ctx = info.context
        await friends.send_request(ctx.session, ctx.clock, require_user(ctx), handle)
        await ctx.session.commit()
        return True

    @strawberry.mutation
    async def respond_to_friend_request(self, info: Info[Context, None], id: strawberry.ID, accept: bool) -> bool:
        ctx = info.context
        me = require_user(ctx)
        try:
            fid = uuid.UUID(str(id))
        except ValueError:
            raise NotFound("No such request") from None
        await friends.respond(ctx.session, ctx.clock, me, fid, accept)
        await ctx.session.commit()
        return True

    @strawberry.mutation
    async def remove_friend(self, info: Info[Context, None], user_id: strawberry.ID) -> bool:
        ctx = info.context
        me = require_user(ctx)
        try:
            uid = uuid.UUID(str(user_id))
        except ValueError:
            raise NotFound("Not friends") from None
        await friends.remove(ctx.session, me, uid)
        await ctx.session.commit()
        return True


def _mask_unexpected(error: GraphQLError) -> bool:
    # DomainErrors carry extensions.code; GraphQL syntax/validation errors have no original_error
    return error.original_error is not None and "code" not in (error.extensions or {})


schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=[DomainErrors, lambda: MaskErrors(should_mask_error=_mask_unexpected, error_message="Internal error")],
)
graphql_router = GraphQLRouter(schema, context_getter=get_context)
