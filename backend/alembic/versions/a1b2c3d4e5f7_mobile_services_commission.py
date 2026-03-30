"""mobile services technician commission rules and job lead source

Revision ID: a1b2c3d4e5f7
Revises: z1a2b3c4d5e6
Create Date: 2026-03-30

"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f7"
down_revision = "z1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("mobile_commission_rules_json", sa.Text(), nullable=True),
    )
    op.add_column(
        "autokeyjob",
        sa.Column(
            "commission_lead_source",
            sa.String(length=64),
            nullable=False,
            server_default="shop_referred",
        ),
    )


def downgrade() -> None:
    op.drop_column("autokeyjob", "commission_lead_source")
    op.drop_column("user", "mobile_commission_rules_json")
