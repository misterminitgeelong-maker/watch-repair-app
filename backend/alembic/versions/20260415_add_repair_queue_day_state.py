"""add repairqueuedaystate for per-user daily queue progress

Revision ID: 20260415_queue_day
Revises: 20260414_add_claimed_by
Create Date: 2026-04-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260415_queue_day"
down_revision: Union[str, None] = "20260414_add_claimed_by"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "repairqueuedaystate",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(length=8), nullable=False),
        sa.Column("shop_date", sa.String(length=10), nullable=False),
        sa.Column("done_ids_json", sa.String(), nullable=False, server_default="[]"),
        sa.Column("stats_json", sa.String(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "user_id", "mode", "shop_date", name="uq_repair_queue_day_state_scope"),
    )
    op.create_index(op.f("ix_repairqueuedaystate_tenant_id"), "repairqueuedaystate", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_repairqueuedaystate_user_id"), "repairqueuedaystate", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_repairqueuedaystate_user_id"), table_name="repairqueuedaystate")
    op.drop_index(op.f("ix_repairqueuedaystate_tenant_id"), table_name="repairqueuedaystate")
    op.drop_table("repairqueuedaystate")
