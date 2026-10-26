"""team records

Revision ID: 0003
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"


def upgrade() -> None:
    op.add_column("games", sa.Column("home_record", sa.String()))
    op.add_column("games", sa.Column("away_record", sa.String()))


def downgrade() -> None:
    op.drop_column("games", "away_record")
    op.drop_column("games", "home_record")
