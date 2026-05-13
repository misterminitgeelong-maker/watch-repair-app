"""add tenant.twilio_messaging_service_sid for per-tenant SMS sender name

Revision ID: a2b3c4d5e6f7
Revises: z1a2b3c4d5e6
Create Date: 2026-05-13

"""
from alembic import op
import sqlalchemy as sa

revision = "a2b3c4d5e6f7"
down_revision = "z1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant",
        sa.Column(
            "twilio_messaging_service_sid",
            sa.String(length=64),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("tenant", "twilio_messaging_service_sid")
