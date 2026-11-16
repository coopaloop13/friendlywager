"""push reminders: device tokens and the last reminder time

Revision ID: 0007
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0007"
down_revision = "0006"

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "device_tokens",
        sa.Column("token", sa.String, primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String, nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("platform IN ('ios','android')", name="ck_device_tokens_platform"),
    )
    op.create_index("ix_device_tokens_user_id", "device_tokens", ["user_id"])
    op.add_column("users", sa.Column("reminded_at", TS))


def downgrade() -> None:
    op.drop_column("users", "reminded_at")
    op.drop_table("device_tokens")
