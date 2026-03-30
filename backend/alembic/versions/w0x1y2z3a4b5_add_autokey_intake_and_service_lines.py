"""add customer_intake_token and additional_services_json to autokeyjob

Revision ID: w0x1y2z3a4b5
Revises: v9w0x1y2z3a4
Create Date: 2026-03-30

"""
from alembic import op
import sqlalchemy as sa

revision = "w0x1y2z3a4b5"
down_revision = "v9w0x1y2z3a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("autokeyjob", sa.Column("customer_intake_token", sa.Text(), nullable=True))
    op.add_column("autokeyjob", sa.Column("additional_services_json", sa.Text(), nullable=True))
    op.create_index(
        "ix_autokeyjob_customer_intake_token",
        "autokeyjob",
        ["customer_intake_token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_autokeyjob_customer_intake_token", table_name="autokeyjob")
    op.drop_column("autokeyjob", "additional_services_json")
    op.drop_column("autokeyjob", "customer_intake_token")
