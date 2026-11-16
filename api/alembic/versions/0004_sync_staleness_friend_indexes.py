"""last_synced_at for health checks; friendships indexed by each side

Revision ID: 0004
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"


def upgrade() -> None:
    op.add_column("league_state", sa.Column("last_synced_at", sa.DateTime(timezone=True)))
    op.create_index("ix_friendships_requester_id", "friendships", ["requester_id"])
    op.create_index("ix_friendships_addressee_id", "friendships", ["addressee_id"])


def downgrade() -> None:
    op.drop_index("ix_friendships_addressee_id", "friendships")
    op.drop_index("ix_friendships_requester_id", "friendships")
    op.drop_column("league_state", "last_synced_at")
