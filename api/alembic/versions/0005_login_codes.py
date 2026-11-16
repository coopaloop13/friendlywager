"""emailed sign-in codes; passwords become optional

Revision ID: 0005
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "login_codes",
        sa.Column("email", sa.String, primary_key=True),
        sa.Column("code_hash", sa.String, nullable=False),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("attempts", sa.SmallInteger, nullable=False, server_default="0"),
        sa.CheckConstraint("email = lower(email)", name="ck_login_codes_email_lower"),
        sa.CheckConstraint("attempts BETWEEN 0 AND 5", name="ck_login_codes_attempts"),
    )
    # kept (nullable) so a rollback to password login is possible; drop once code sign-in has settled
    op.alter_column("users", "password_hash", nullable=True)


def downgrade() -> None:
    op.execute("UPDATE users SET password_hash = '' WHERE password_hash IS NULL")
    op.alter_column("users", "password_hash", nullable=False)
    op.drop_table("login_codes")
