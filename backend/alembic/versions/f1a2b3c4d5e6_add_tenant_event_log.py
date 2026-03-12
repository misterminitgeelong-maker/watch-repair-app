"""add tenant event log

Revision ID: f1a2b3c4d5e6
Revises: e7f1a2b3c4d5
Create Date: 2026-03-12 01:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e7f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenanteventlog",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_email", sa.String(), nullable=True),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("event_summary", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tenanteventlog_tenant_id"), "tenanteventlog", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_tenanteventlog_actor_user_id"), "tenanteventlog", ["actor_user_id"], unique=False)
    op.create_index(op.f("ix_tenanteventlog_entity_type"), "tenanteventlog", ["entity_type"], unique=False)
    op.create_index(op.f("ix_tenanteventlog_entity_id"), "tenanteventlog", ["entity_id"], unique=False)
    op.create_index(op.f("ix_tenanteventlog_event_type"), "tenanteventlog", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tenanteventlog_event_type"), table_name="tenanteventlog")
    op.drop_index(op.f("ix_tenanteventlog_entity_id"), table_name="tenanteventlog")
    op.drop_index(op.f("ix_tenanteventlog_entity_type"), table_name="tenanteventlog")
    op.drop_index(op.f("ix_tenanteventlog_actor_user_id"), table_name="tenanteventlog")
    op.drop_index(op.f("ix_tenanteventlog_tenant_id"), table_name="tenanteventlog")
    op.drop_table("tenanteventlog")
