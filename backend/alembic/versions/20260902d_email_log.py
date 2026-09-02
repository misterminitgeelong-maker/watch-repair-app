"""add emaillog table (audit trail for operator dispatch alert emails)

Revision ID: 20260902d_email_log
Revises: 20260902c_prospect_lead_source
Create Date: 2026-09-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260902d_email_log"
down_revision: Union[str, None] = "20260902c_prospect_lead_source"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "emaillog",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("to_email", sa.String(), nullable=False),
        sa.Column("event", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_emaillog_tenant_id"), "emaillog", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_emaillog_created_at"), "emaillog", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_emaillog_created_at"), table_name="emaillog")
    op.drop_index(op.f("ix_emaillog_tenant_id"), table_name="emaillog")
    op.drop_table("emaillog")
