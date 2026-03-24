"""add parent account event log

Revision ID: e7f1a2b3c4d5
Revises: d4e6f8a1b2c3
Create Date: 2026-03-12 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e7f1a2b3c4d5"
down_revision: Union[str, None] = "d4e6f8a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "parentaccounteventlog",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("parent_account_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("actor_email", sa.String(), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("event_summary", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parent_account_id"], ["parentaccount.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_parentaccounteventlog_parent_account_id"),
        "parentaccounteventlog",
        ["parent_account_id"],
        unique=False,
    )
    op.create_index(op.f("ix_parentaccounteventlog_tenant_id"), "parentaccounteventlog", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_parentaccounteventlog_actor_user_id"), "parentaccounteventlog", ["actor_user_id"], unique=False)
    op.create_index(op.f("ix_parentaccounteventlog_event_type"), "parentaccounteventlog", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_parentaccounteventlog_event_type"), table_name="parentaccounteventlog")
    op.drop_index(op.f("ix_parentaccounteventlog_actor_user_id"), table_name="parentaccounteventlog")
    op.drop_index(op.f("ix_parentaccounteventlog_tenant_id"), table_name="parentaccounteventlog")
    op.drop_index(op.f("ix_parentaccounteventlog_parent_account_id"), table_name="parentaccounteventlog")
    op.drop_table("parentaccounteventlog")
