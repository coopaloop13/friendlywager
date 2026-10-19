import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, SmallInteger, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import DateTime

TS = DateTime(timezone=True)
UUID_PK = dict(primary_key=True, server_default=text("gen_random_uuid()"))


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="ck_users_email_lower"),
        CheckConstraint("handle ~ '^[a-z0-9_]{3,20}$'", name="ck_users_handle_format"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **UUID_PK)
    email: Mapped[str] = mapped_column(String, unique=True)
    handle: Mapped[str] = mapped_column(String, unique=True)
    password_hash: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())


class Friendship(Base):
    __tablename__ = "friendships"
    __table_args__ = (
        CheckConstraint("status IN ('pending','accepted')", name="ck_friendships_status"),
        CheckConstraint("requester_id <> addressee_id", name="ck_friendships_not_self"),
        Index(
            "uq_friendships_pair",
            func.least(text("requester_id"), text("addressee_id")),
            func.greatest(text("requester_id"), text("addressee_id")),
            unique=True,
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **UUID_PK)
    requester_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    addressee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())
    accepted_at: Mapped[datetime | None] = mapped_column(TS)


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (
        CheckConstraint("league IN ('nfl','cfb')", name="ck_games_league"),
        CheckConstraint(
            "status IN ('scheduled','in_progress','final','postponed','canceled')",
            name="ck_games_status",
        ),
        CheckConstraint("season_type IN (1,2,3)", name="ck_games_season_type"),
        Index("uq_games_league_external", "league", "external_id", unique=True),
        Index("ix_games_week", "league", "season", "season_type", "week"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **UUID_PK)
    league: Mapped[str] = mapped_column(String)
    season: Mapped[int] = mapped_column(SmallInteger)
    season_type: Mapped[int] = mapped_column(SmallInteger)
    week: Mapped[int] = mapped_column(SmallInteger)
    external_id: Mapped[str] = mapped_column(String)
    home_name: Mapped[str] = mapped_column(String)
    home_abbr: Mapped[str] = mapped_column(String)
    away_name: Mapped[str] = mapped_column(String)
    away_abbr: Mapped[str] = mapped_column(String)
    home_rank: Mapped[int | None] = mapped_column(SmallInteger)
    away_rank: Mapped[int | None] = mapped_column(SmallInteger)
    kickoff_at: Mapped[datetime] = mapped_column(TS)
    status: Mapped[str] = mapped_column(String)
    home_score: Mapped[int | None] = mapped_column(SmallInteger)
    away_score: Mapped[int | None] = mapped_column(SmallInteger)
    spread_text: Mapped[str | None] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())


class Pick(Base):
    __tablename__ = "picks"
    __table_args__ = (
        CheckConstraint("pred_home BETWEEN 0 AND 200", name="ck_picks_home_range"),
        CheckConstraint("pred_away BETWEEN 0 AND 200", name="ck_picks_away_range"),
        CheckConstraint("pred_home <> pred_away", name="ck_picks_no_tie"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    game_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), primary_key=True
    )
    pred_home: Mapped[int] = mapped_column(SmallInteger)
    pred_away: Mapped[int] = mapped_column(SmallInteger)
    updated_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())


class LeagueState(Base):
    __tablename__ = "league_state"
    __table_args__ = (CheckConstraint("league IN ('nfl','cfb')", name="ck_league_state_league"),)
    league: Mapped[str] = mapped_column(String, primary_key=True)
    season: Mapped[int] = mapped_column(SmallInteger)
    season_type: Mapped[int] = mapped_column(SmallInteger)
    week: Mapped[int] = mapped_column(SmallInteger)
