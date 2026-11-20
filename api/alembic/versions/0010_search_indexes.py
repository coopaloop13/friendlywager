"""picks indexed by game; games indexed by status and kickoff

Revision ID: 0010
"""
from alembic import op

revision = "0010"
down_revision = "0009"


def upgrade() -> None:
    op.create_index("ix_picks_game_id", "picks", ["game_id"])
    op.create_index("ix_games_status_kickoff_at", "games", ["status", "kickoff_at"])


def downgrade() -> None:
    op.drop_index("ix_games_status_kickoff_at", "games")
    op.drop_index("ix_picks_game_id", "picks")
