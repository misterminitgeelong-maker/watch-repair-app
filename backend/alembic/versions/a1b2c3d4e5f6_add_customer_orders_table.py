"""add customer_orders table

Revision ID: a1b2c3d4e5f6
Revises: z1a2b3c4d5e6
Create Date: 2026-05-03

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a1b2c3d4e5f6"
down_revision = "z1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customerorder",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("supplier", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="to_order"),
        sa.Column("priority", sa.String(), nullable=False, server_default="normal"),
        sa.Column("estimated_cost_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customer.id"]),
    )


def downgrade() -> None:
    op.drop_table("customerorder")
