"""result pushes can be muted per user

Revision ID: 0009
"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"


def upgrade() -> None:
    op.add_column("users", sa.Column("result_pushes", sa.Boolean, nullable=False, server_default=sa.true()))


def downgrade() -> None:
    op.drop_column("users", "result_pushes")
