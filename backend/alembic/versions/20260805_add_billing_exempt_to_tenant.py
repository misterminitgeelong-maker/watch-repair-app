"""add tenant.billing_exempt for platform-admin comp accounts

Revision ID: 20260805_billing_exempt
Revises: 20260805_seed_new_makes
Create Date: 2026-08-05

"""
from alembic import op
import sqlalchemy as sa

revision = "20260805_billing_exempt"
down_revision = "20260805_seed_new_makes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant",
        sa.Column(
            "billing_exempt",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("tenant", "billing_exempt")
