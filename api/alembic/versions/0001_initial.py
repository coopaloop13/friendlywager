"""initial schema

Revision ID: 0001
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0001"
down_revision = None

PK = dict(primary_key=True, server_default=sa.text("gen_random_uuid()"))
TS = sa.DateTime(timezone=True)
NOW = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), **PK),
        sa.Column("email", sa.String, nullable=False, unique=True),
        sa.Column("handle", sa.String, nullable=False, unique=True),
        sa.Column("password_hash", sa.String, nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.CheckConstraint("email = lower(email)", name="ck_users_email_lower"),
        sa.CheckConstraint("handle ~ '^[a-z0-9_]{3,20}$'", name="ck_users_handle_format"),
    )
    op.create_table(
        "friendships",
        sa.Column("id", UUID(as_uuid=True), **PK),
        sa.Column("requester_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("addressee_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.Column("accepted_at", TS),
        sa.CheckConstraint("status IN ('pending','accepted')", name="ck_friendships_status"),
        sa.CheckConstraint("requester_id <> addressee_id", name="ck_friendships_not_self"),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_friendships_pair ON friendships "
        "(LEAST(requester_id, addressee_id), GREATEST(requester_id, addressee_id))"
    )
    op.create_table(
        "games",
        sa.Column("id", UUID(as_uuid=True), **PK),
        sa.Column("league", sa.String, nullable=False),
        sa.Column("season", sa.SmallInteger, nullable=False),
        sa.Column("season_type", sa.SmallInteger, nullable=False),
        sa.Column("week", sa.SmallInteger, nullable=False),
        sa.Column("external_id", sa.String, nullable=False),
        sa.Column("home_name", sa.String, nullable=False),
        sa.Column("home_abbr", sa.String, nullable=False),
        sa.Column("away_name", sa.String, nullable=False),
        sa.Column("away_abbr", sa.String, nullable=False),
        sa.Column("home_rank", sa.SmallInteger),
        sa.Column("away_rank", sa.SmallInteger),
        sa.Column("kickoff_at", TS, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("home_score", sa.SmallInteger),
        sa.Column("away_score", sa.SmallInteger),
        sa.Column("spread_text", sa.String),
        sa.Column("updated_at", TS, nullable=False, server_default=NOW),
        sa.CheckConstraint("league IN ('nfl','cfb')", name="ck_games_league"),
        sa.CheckConstraint(
            "status IN ('scheduled','in_progress','final','postponed','canceled')",
            name="ck_games_status",
        ),
        sa.CheckConstraint("season_type IN (1,2,3)", name="ck_games_season_type"),
    )
    op.create_index("uq_games_league_external", "games", ["league", "external_id"], unique=True)
    op.create_index("ix_games_week", "games", ["league", "season", "season_type", "week"])
    op.create_table(
        "picks",
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("game_id", UUID(as_uuid=True), sa.ForeignKey("games.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("pred_home", sa.SmallInteger, nullable=False),
        sa.Column("pred_away", sa.SmallInteger, nullable=False),
        sa.Column("updated_at", TS, nullable=False, server_default=NOW),
        sa.CheckConstraint("pred_home BETWEEN 0 AND 200", name="ck_picks_home_range"),
        sa.CheckConstraint("pred_away BETWEEN 0 AND 200", name="ck_picks_away_range"),
        sa.CheckConstraint("pred_home <> pred_away", name="ck_picks_no_tie"),
    )
    op.create_table(
        "league_state",
        sa.Column("league", sa.String, primary_key=True),
        sa.Column("season", sa.SmallInteger, nullable=False),
        sa.Column("season_type", sa.SmallInteger, nullable=False),
        sa.Column("week", sa.SmallInteger, nullable=False),
        sa.CheckConstraint("league IN ('nfl','cfb')", name="ck_league_state_league"),
    )


def downgrade() -> None:
    for t in ("league_state", "picks", "games", "friendships", "users"):
        op.drop_table(t)
