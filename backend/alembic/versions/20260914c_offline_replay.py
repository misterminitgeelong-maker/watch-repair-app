"""add mutation idempotency keys and autokeyjob.updated_at

Revision ID: 20260914c_offline_replay
Revises: 20260914b_notification_retry
Create Date: 2026-09-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260914c_offline_replay"
down_revision: Union[str, None] = "20260914b_notification_retry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mutationidempotencykey",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "key", name="uq_mutation_idempotency_tenant_key"),
    )
    op.create_index("ix_mutationidempotencykey_tenant_id", "mutationidempotencykey", ["tenant_id"])
    op.create_index("ix_mutationidempotencykey_key", "mutationidempotencykey", ["key"])
    op.add_column(
        "autokeyjob",
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_column("autokeyjob", "updated_at")
    op.drop_index("ix_mutationidempotencykey_key", table_name="mutationidempotencykey")
    op.drop_index("ix_mutationidempotencykey_tenant_id", table_name="mutationidempotencykey")
    op.drop_table("mutationidempotencykey")
