"""team logos

Revision ID: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade() -> None:
    op.add_column("games", sa.Column("home_logo", sa.String()))
    op.add_column("games", sa.Column("away_logo", sa.String()))


def downgrade() -> None:
    op.drop_column("games", "away_logo")
    op.drop_column("games", "home_logo")
