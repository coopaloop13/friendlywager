import asyncio
import enum
import inspect
import uuid
from datetime import datetime
from dataclasses import dataclass, field

import strawberry
from fastapi import Depends, Request, Response
from graphql import GraphQLError
from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.extensions import MaskErrors, SchemaExtension
from strawberry.fastapi import BaseContext, GraphQLRouter
from strawberry.types import Info

from app import auth, friends, picks, results
from app.clock import Clock
from app.config import Settings
from app.db import get_session
from app.errors import DomainError, Forbidden, NotFound, Unauthenticated
from app.models import Game as GameModel
from app.models import Pick as PickModel
from app.models import User as UserModel
from app.sync.espn import WeekKey

COOKIE = "fw_session"
COOKIE_MAX_AGE = auth.SESSION_DAYS * 24 * 3600


@dataclass
class Context(BaseContext):
    session: AsyncSession
    clock: Clock
    settings: Settings
    user_id: uuid.UUID | None
    response: Response
    # sibling fields resolve concurrently, but one AsyncSession allows one operation at a time
    db_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


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
            if not inspect.isawaitable(result):
                return result
            async with info.context.db_lock:
                return await result
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


@strawberry.enum
class League(enum.Enum):
    NFL = "nfl"
    CFB = "cfb"


@strawberry.type
class PickView:
    home: int
    away: int


@strawberry.type
class GameView:
    id: strawberry.ID
    home_name: str
    home_abbr: str
    away_name: str
    away_abbr: str
    home_logo: str | None
    away_logo: str | None
    home_rank: int | None
    away_rank: int | None
    home_record: str | None
    away_record: str | None
    kickoff_at: datetime
    status: str
    home_score: int | None
    away_score: int | None
    spread: str | None
    locked: bool
    my_pick: PickView | None


@strawberry.type
class Week:
    league: League
    season: int
    season_type: int
    week: int
    games: list[GameView]


def _to_pick(p: PickModel | None) -> PickView | None:
    return PickView(home=p.pred_home, away=p.pred_away) if p else None


def _to_game(g: GameModel, p: PickModel | None, now: datetime) -> GameView:
    return GameView(
        id=strawberry.ID(str(g.id)), home_name=g.home_name, home_abbr=g.home_abbr,
        away_name=g.away_name, away_abbr=g.away_abbr, home_logo=g.home_logo, away_logo=g.away_logo,
        home_rank=g.home_rank, away_rank=g.away_rank, home_record=g.home_record, away_record=g.away_record,
        kickoff_at=g.kickoff_at, status=g.status, home_score=g.home_score, away_score=g.away_score,
        spread=g.spread_text, locked=picks.is_locked(g, now), my_pick=_to_pick(p),
    )


async def _week(ctx: Context, key: WeekKey) -> Week:
    rows = await picks.week_games(ctx.session, require_user(ctx), key)
    now = ctx.clock.now()
    return Week(
        league=League(key.league), season=key.season, season_type=key.season_type, week=key.week,
        games=[_to_game(g, p, now) for g, p in rows],
    )


def _game_id(value: strawberry.ID) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except ValueError:
        raise NotFound("No such game") from None


@strawberry.type
class MatchupGame:
    game: GameView
    mine: PickView | None
    theirs: PickView | None
    my_points: int
    their_points: int


@strawberry.type
class Matchup:
    games: list[MatchupGame]
    my_points: int
    their_points: int


@strawberry.type
class HeadToHead:
    points_for: int
    points_against: int
    weeks_won: int
    weeks_lost: int
    weeks_tied: int


@strawberry.type
class LeaderboardRow(HeadToHead):
    user_id: strawberry.ID
    handle: str


def _score_view(s) -> PickView | None:
    return PickView(home=s.home, away=s.away) if s else None


def _friend_id(value: strawberry.ID) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except ValueError:
        raise Forbidden("Not friends") from None


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

    @strawberry.field
    async def current_week(self, info: Info[Context, None], league: League) -> Week | None:
        ctx = info.context
        require_user(ctx)
        key = await picks.current_week(ctx.session, league.value)
        return await _week(ctx, key) if key else None

    @strawberry.field
    async def week(
        self, info: Info[Context, None], league: League, season: int, season_type: int, week: int
    ) -> Week:
        return await _week(info.context, WeekKey(league.value, season, season_type, week))

    @strawberry.field
    async def matchup(
        self, info: Info[Context, None], friend_id: strawberry.ID, league: League, season: int,
        season_type: int, week: int,
    ) -> Matchup:
        ctx = info.context
        me = require_user(ctx)
        m = await results.matchup(
            ctx.session, ctx.clock, me, _friend_id(friend_id), WeekKey(league.value, season, season_type, week)
        )
        now = ctx.clock.now()
        games = []
        for mg in m.games:
            gv = _to_game(mg.game, None, now)
            gv.my_pick = _score_view(mg.mine)
            games.append(MatchupGame(game=gv, mine=gv.my_pick, theirs=_score_view(mg.theirs),
                                     my_points=mg.my_points, their_points=mg.their_points))
        return Matchup(games=games, my_points=m.my_points, their_points=m.their_points)

    @strawberry.field
    async def head_to_head(
        self, info: Info[Context, None], friend_id: strawberry.ID, league: League, season: int
    ) -> HeadToHead:
        ctx = info.context
        h = await results.head_to_head(ctx.session, ctx.clock, require_user(ctx), _friend_id(friend_id), league.value, season)
        return HeadToHead(**vars(h))

    @strawberry.field
    async def leaderboard(self, info: Info[Context, None], league: League, season: int) -> list[LeaderboardRow]:
        ctx = info.context
        rows = await results.leaderboard(ctx.session, ctx.clock, require_user(ctx), league.value, season)
        return [LeaderboardRow(**{**vars(r), "user_id": strawberry.ID(str(r.user_id))}) for r in rows]


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

    @strawberry.mutation
    async def save_pick(self, info: Info[Context, None], game_id: strawberry.ID, home: int, away: int) -> PickView:
        ctx = info.context
        me = require_user(ctx)
        p = await picks.save_pick(ctx.session, ctx.clock, me, _game_id(game_id), home, away)
        await ctx.session.commit()
        return _to_pick(p)

    @strawberry.mutation
    async def delete_pick(self, info: Info[Context, None], game_id: strawberry.ID) -> bool:
        ctx = info.context
        me = require_user(ctx)
        await picks.delete_pick(ctx.session, ctx.clock, me, _game_id(game_id))
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


def make_graphql_router(ide: bool) -> GraphQLRouter:
    return GraphQLRouter(schema, context_getter=get_context, graphql_ide="graphiql" if ide else None)
