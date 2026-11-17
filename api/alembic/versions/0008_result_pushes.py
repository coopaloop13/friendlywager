"""result pushes: remember which final games have been announced

Revision ID: 0008
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"


def upgrade() -> None:
    op.add_column("games", sa.Column("result_pushed_at", sa.DateTime(timezone=True)))
    # games that finished before this feature existed are old news
    op.execute("UPDATE games SET result_pushed_at = now() WHERE status = 'final'")


def downgrade() -> None:
    op.drop_column("games", "result_pushed_at")
