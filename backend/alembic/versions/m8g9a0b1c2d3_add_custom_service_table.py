"""add_custom_service_table

Revision ID: m8g9a0b1c2d3
Revises: l7f8a9b0c1d2
Create Date: 2026-03-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m8g9a0b1c2d3"
down_revision: Union[str, None] = "l7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customservice",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("service_type", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("group_id", sa.String(), nullable=False, server_default="custom"),
        sa.Column("group_label", sa.String(), nullable=False, server_default="Custom"),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("pricing_type", sa.String(), nullable=False, server_default="fixed"),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customservice_tenant_id", "customservice", ["tenant_id"])
    op.create_index("ix_customservice_service_type", "customservice", ["service_type"])


def downgrade() -> None:
    op.drop_index("ix_customservice_service_type", table_name="customservice")
    op.drop_index("ix_customservice_tenant_id", table_name="customservice")
    op.drop_table("customservice")
